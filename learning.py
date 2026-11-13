"""Conservative selection feedback from frozen, verified editorial outcomes.

Penalties affect future ranking only, never displayed Poisson probabilities.
No causal explanation is inferred from a lost bet. No account data is pooled.
"""
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from accounts import configured, database, DAILY_OPINION_SCHEMA
from tracking import resolve, valid_market

VERSION = 'selection-feedback-v1'
MIN_EVENTS = 30
WINDOW_DAYS = 180
MAX_PENALTY = 10


def instant(value):
    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('timezone_required')
    return value


def build(picks, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('timezone_required')
    buckets = defaultdict(list)
    excluded = defaultdict(int)
    seen = set()
    losses = []
    for pick in picks:
        try:
            if pick.get('status') not in ('won', 'lost'):
                excluded['unsettled_or_void'] += 1
                continue
            match = pick['match']
            kickoff, published = instant(match['date']), instant(pick['published_at'])
            # Legacy outcomes without a recorded observation time cannot train a policy.
            settled = instant(pick['settled_at'])
            if not published < kickoff < settled <= now or kickoff < now - timedelta(days=WINDOW_DAYS):
                raise ValueError('outside_training_window')
            market, probability = pick['market'], pick['probability']
            model = pick['model_version']
            if not model or not isinstance(model, str) or not valid_market(market) or market.startswith('scorer:'):
                raise ValueError('invalid_market_or_model')
            if type(probability) not in (int, float) or not math.isfinite(probability) or not 0 < probability < 100:
                raise ValueError('invalid_probability')
            hg, ag = pick['home_score'], pick['away_score']
            if any(type(v) is not int or v < 0 for v in (hg, ag)):
                raise ValueError('missing_scores')
            won = int(pick['status'] == 'won')
            if resolve(market, hg, ag) != bool(won):
                raise ValueError('inconsistent_result')
            league, event = match['league'], match['id']
            if not all(isinstance(v, str) and v for v in (league, event)):
                raise ValueError('invalid_identity')
            identity = (league, event, market)
            if identity in seen:
                excluded['duplicate'] += 1
                continue
            seen.add(identity)
            value = (probability / 100, won, (league, event))
            # Same model and confidence band; do not pool unlike versions/profiles.
            band = str(int(probability // 10) * 10)
            buckets[(model, market, band, '*')].append(value)
            buckets[(model, market, band, league)].append(value)
            if not won:
                losses.append(dict(match=match, market=market, probability=probability,
                                   home_score=hg, away_score=ag, settled_at=pick['settled_at']))
        except (KeyError, ValueError, TypeError, AttributeError):
            excluded['invalid_or_unobserved'] += 1
    rules = []
    for (model, market, band, league), values in sorted(buckets.items()):
        n = len({event for _, _, event in values})
        predicted = sum(p for p, _, _ in values) / len(values)
        actual = sum(y for _, y, _ in values) / len(values)
        # Shrink toward zero; require a gap beyond sampling uncertainty first.
        uncertainty = 1.96 * math.sqrt(max(.01, predicted * (1 - predicted)) / n)
        penalty = min(MAX_PENALTY, max(0, predicted - actual - uncertainty) * n / (n + 50) * 100) if n >= MIN_EVENTS else 0
        rules.append(dict(model=model, market=market, band=band, league=league, count=n,
                          won=sum(y for _, y, _ in values), predicted_pct=round(predicted*100, 1),
                          success_pct=round(actual*100, 1), penalty=round(penalty, 2)))
    return dict(version=VERSION, as_of=now.isoformat(), window_days=WINDOW_DAYS,
                minimum_events=MIN_EVENTS, status='active' if any(r['penalty'] for r in rules) else 'collecting',
                eligible=len(seen), losses=len(losses), rules=rules, excluded=dict(excluded),
                recent_losses=sorted(losses, key=lambda p: p['settled_at'], reverse=True)[:10],
                scope='verified_daily_opinion', probabilities_changed=False)


def penalties(report, league, model, markets):
    output = {}
    for market, probability in markets.items():
        if type(probability) not in (int, float) or not math.isfinite(probability):
            continue
        band = str(int(probability // 10) * 10)
        rules = [r for r in report['rules'] if r['model'] == model and r['market'] == market
                 and r['band'] == band and r['league'] in ('*', league)]
        # Never stack overlapping league/global samples.
        output[market] = max((r['penalty'] for r in rules), default=0)
    return output


def current(now=None, user_id=None):
    if not configured():
        result=build([], now)
        result['scorer']=scorer_report([],now)
        return result
    with database() as db:
        db.execute(DAILY_OPINION_SCHEMA)
        rows = db.execute('SELECT payload FROM daily_opinion_boards WHERE day>=? ORDER BY day',
                          (((now or datetime.now(timezone.utc))-timedelta(days=WINDOW_DAYS+1)).date().isoformat(),)).fetchall()
    picks = [p for row in rows for p in json.loads(row['payload']).get('picks', [])]
    if user_id:
        picks.extend(personal_picks(user_id, now))
    result = build(picks, now)
    boards=[json.loads(row['payload']) for row in rows]
    scorers=[p for board in boards for p in (board.get('scorers') if isinstance(board.get('scorers'),list) else [board['scorer']] if board.get('scorer') else [])]
    result['scorer']=scorer_report(scorers,now)
    if any(r['factor'] < 1 for r in result['scorer']['rules']):result['status']='active'
    if user_id:result['scope'] = 'verified_daily_and_own_predictions'
    return result


def personal_picks(user_id, now=None):
    # Only the caller's own settled selections; never aggregate other accounts.
    cutoff=int(((now or datetime.now(timezone.utc))-timedelta(days=WINDOW_DAYS+1)).timestamp())
    with database() as db:
        rows = db.execute("SELECT * FROM account_predictions WHERE user_id=? AND status IN ('won','lost') AND settled_at IS NOT NULL AND starts_at>=?", (user_id,cutoff)).fetchall()
        snapshots = db.execute("SELECT result,created_at FROM account_analyses WHERE user_id=? AND status='complete' AND created_at>=? ORDER BY created_at DESC", (user_id,cutoff)).fetchall()
    analyses = [(json.loads(r['result']), r['created_at']) for r in snapshots]
    output = []
    for row in rows:
        if str(row['market']).startswith('scorer:'):continue
        original = next((a for a, date in analyses if date <= row['created_at'] and str(a.get('event_id')) == str(row['event_id'])
                         and a.get('league') == row['league'] and str(a.get('home_id')) == row['home_id'] and str(a.get('away_id')) == row['away_id']
                         and (a.get('prediction') or {}).get('markets', {}).get(row['market']) == row['probability']), None)
        if not original or not original.get('model'):continue
        output.append(dict(match=dict(id=row['event_id'], league=row['league'],
                          date=datetime.fromtimestamp(row['starts_at'], timezone.utc).isoformat(),
                          home=dict(name=original.get('home_name')), away=dict(name=original.get('away_name'))),
                          market=row['market'], probability=row['probability'], status=row['status'],
                          published_at=datetime.fromtimestamp(row['created_at'], timezone.utc).isoformat(),
                          settled_at=datetime.fromtimestamp(row['settled_at'], timezone.utc).isoformat(),
                          home_score=row['home_score'], away_score=row['away_score'], model_version=original['model']))
    return output


def scorer_report(picks, now=None):
    """Compare observed availability groups; never invent player probabilities."""
    now = now or datetime.now(timezone.utc)
    groups = defaultdict(list)
    seen = set()
    for pick in picks:
        try:
            match = pick['match']
            if pick['status'] not in ('won', 'lost'):continue
            kickoff, published, settled = instant(match['date']), instant(pick['published_at']), instant(pick['settled_at'])
            if not published < kickoff < settled <= now or kickoff < now-timedelta(days=WINDOW_DAYS):continue
            goals = pick['goals_scored']
            if type(goals) is not int or goals < 0 or (goals > 0) != (pick['status'] == 'won'):continue
            identity = (match['league'], str(match['id']), str(pick['player']['id']))
            if identity in seen:continue
            seen.add(identity)
            category = pick['player']['competition_category']
            model = pick['model_version']
            availability = pick['availability']
            if availability not in ('reported_starter','unconfirmed'):continue
            groups[(model, category, availability)].append((identity[:2], int(goals > 0)))
        except (KeyError, ValueError, TypeError, AttributeError):continue
    rules = []
    for (model, category, availability), values in sorted(groups.items()):
        # One observation per event in each group; no duplicate player inflation.
        observations = {}
        for event, won in values:observations.setdefault(event, won)
        other = {}
        for (m, c, a), rows in groups.items():
            if m == model and c == category and a != availability:
                for event, won in rows:
                    if event not in observations:other.setdefault(event, won)
        n, k = len(observations), len(other)
        rate = sum(observations.values())/n
        baseline = sum(other.values())/k if k else None
        factor = 1.0
        if n >= MIN_EVENTS and k >= MIN_EVENTS:
            uncertainty = 1.96*math.sqrt(max(.01,rate*(1-rate))/n + max(.01,baseline*(1-baseline))/k)
            factor -= min(.2, max(0,baseline-rate-uncertainty)*n/(n+50))
        rules.append(dict(model=model, category=category, availability=availability, count=n,
                          success_pct=round(rate*100,1), comparison_count=k, factor=round(factor,4)))
    return dict(eligible=len(seen), rules=rules, probabilities_available=False)


def scorer_factor(report, pick):
    return min((r['factor'] for r in report.get('scorer',{}).get('rules',[])
                if r['model'] == pick.get('model_version') and r['category'] == pick.get('player',{}).get('competition_category')
                and r['availability'] == pick.get('availability')), default=1.0)
