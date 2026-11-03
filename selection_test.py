"""Prospective filtering of official choices; never changes their selection or result."""
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from evaluation import evaluate

VERSION = 'strict-selection-v1'
WINDOW_DAYS = 90
MIN_GAP = .35
DIRECTIONAL = {'home', 'away', 'home_or_draw', 'away_or_draw'}


def instant(value):
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('timezone_required')
    return date


def decision(pick, now):
    reasons = []
    def reject(reason):
        if reason not in reasons:
            reasons.append(reason)
    try:
        kickoff = instant(pick['match']['date'])
        if now.tzinfo is None or now >= kickoff or pick['status'] != 'pending':
            reject('not_prematch')
        basis = pick.get('selection_basis') or {}
        if instant(basis['captured_at']) != now:
            reject('unverified_snapshot_time')
        errors = basis.get('source_errors')
        if not isinstance(errors, dict) or any(side not in errors or errors[side] for side in ('home','away')):
            reject('source_incomplete')
        for side in ('home','away'):
            team = str(pick['match'][side]['id'])
            games = (basis.get('history') or {}).get(side)
            if not isinstance(games, list) or len(games) != 10:
                reject('insufficient_history')
                continue
            ids = set(); dates = []
            for game in games:
                played = instant(game['date'])
                if not game.get('id') or str(game['id']) in ids:
                    reject('invalid_history')
                ids.add(str(game.get('id')))
                if team not in (str(game['home_id']), str(game['away_id'])):
                    reject('invalid_history')
                if any(isinstance(game[k], bool) or not isinstance(game[k], int) or game[k] < 0
                       for k in ('home_goals','away_goals')):
                    reject('invalid_history')
                if not 3*3600 <= (now-played).total_seconds() <= 180*86400:
                    reject('history_outside_180_days')
                dates.append(played)
            if dates and (now-max(dates)).total_seconds() > 45*86400:
                reject('no_recent_match')
        if pick['market'] in DIRECTIONAL:
            goals = pick['expected_goals']
            values = [goals[side] for side in ('home','away')]
            if any(isinstance(v, bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in values):
                reject('invalid_projection')
            elif abs(values[0]-values[1]) < MIN_GAP - 1e-9:
                reject('balanced_projection')
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        reject('missing_or_invalid_inputs')
    return dict(version=VERSION, recorded_at=now.isoformat(), accepted=not reasons, reasons=reasons)


def report(picks, as_of=None):
    as_of = as_of or datetime.now(timezone.utc)
    eligible = []; seen = set(); excluded = Counter()
    for pick in picks:
        test = pick.get('selection_test') or {}
        if test.get('version') != VERSION:
            excluded['not_recorded_prospectively'] += 1
            continue
        try:
            recorded = instant(test['recorded_at']); kickoff = instant(pick['match']['date'])
            if not recorded < kickoff or recorded > as_of or type(test['accepted']) is not bool:
                raise ValueError('invalid_decision')
            identity = (pick['match']['league'],pick['match']['id'],pick['market'])
            if identity in seen:
                excluded['duplicate'] += 1
                continue
            seen.add(identity); eligible.append((recorded,kickoff,pick))
        except (KeyError,ValueError,TypeError,AttributeError):
            excluded['invalid_decision'] += 1
    start = min((row[0] for row in eligible),default=None)
    end = start + timedelta(days=WINDOW_DAYS) if start else None
    cohort = [p for recorded,kickoff,p in eligible if recorded < end and kickoff < end]
    retained = [p for p in cohort if p['selection_test']['accepted']]
    rejected = [p for p in cohort if not p['selection_test']['accepted']]
    reasons = Counter(reason for p in rejected for reason in p['selection_test']['reasons'])
    return dict(experiment=VERSION, status='waiting_for_new_choices' if not start else 'window_complete' if as_of>=end else 'collecting',
                registered=len(cohort), retained=len(retained), rejected=len(rejected),
                retained_pct=round(100*len(retained)/len(cohort),1) if cohort else None,
                baseline=evaluate(cohort,as_of=as_of), candidate=evaluate(retained,as_of=as_of),
                rejected_results=evaluate(rejected,as_of=as_of), rejection_reasons=dict(reasons), excluded=dict(excluded),
                window=dict(days=WINDOW_DAYS,start=start.isoformat() if start else None,end=end.isoformat() if end else None),
                rules=dict(history_matches_per_team=10,history_max_days=180,newest_match_max_days=45,
                           directional_expected_goal_gap=MIN_GAP,no_source_errors=True),
                policy='prospective_subset_only_no_automatic_activation',
                note='Same official choices, filtered before kickoff. Goals markets are not rejected merely because teams are balanced. Compare success, calibration and retained volume; small samples do not establish improvement.')
