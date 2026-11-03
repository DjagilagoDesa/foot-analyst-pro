"""Frozen venue-specific forecasts, evaluated against the same official selections."""
import copy
import math
from collections import Counter
from datetime import datetime,timedelta,timezone
from evaluation import evaluate

VERSION='venue-daily10-shadow-v1'
MIN_VENUE_MATCHES=4
WINDOW_DAYS=90


def instant(value):
    date=datetime.fromisoformat(value.replace('Z','+00:00'))
    if date.tzinfo is None:raise ValueError('timezone_required')
    return date


def build(server,result,now):
    """Reuse the same ten observations and scoring function; change venue grouping only."""
    samples={}; stats={}
    try:
        errors=result.get('source_errors')
        if not isinstance(errors,dict) or any(side not in errors or errors[side] for side in ('home','away')):
            return dict(status='unavailable',reason='partial_source')
        for side in ('home','away'):
            team=str(result['match'][side]['id']);games=result['history'][side]
            if len(games)!=10:return dict(status='unavailable',reason='insufficient_history')
            ids=set(); selected=[]
            for game in games:
                played=instant(game['date'])
                if not game.get('id') or str(game['id']) in ids or team not in (str(game['home_id']),str(game['away_id'])):
                    raise ValueError('invalid_history')
                ids.add(str(game['id']))
                if not 3*3600 <= (now-played).total_seconds() <= 180*86400:
                    return dict(status='unavailable',reason='history_outside_180_days')
                if any(isinstance(game[k],bool) or not isinstance(game[k],int) or game[k]<0 for k in ('home_goals','away_goals')):
                    raise ValueError('invalid_score')
                if str(game[side+'_id'])==team:selected.append(game)
            samples[side]=len(selected)
            if len(selected)<MIN_VENUE_MATCHES:
                return dict(status='unavailable',reason='insufficient_venue_history',samples=samples)
            stats[side]=server.summary(selected,team)
        prediction=server.probabilities(stats['home'],stats['away'])
        if any(isinstance(p,bool) or not isinstance(p,(int,float)) or not math.isfinite(p) or not 0<=p<=100 for p in prediction['markets'].values()):
            raise ValueError('invalid_prediction')
        return dict(status='ready',samples=samples,statistics=stats,prediction=prediction)
    except (KeyError,ValueError,TypeError,AttributeError,OverflowError):
        return dict(status='unavailable',reason='invalid_inputs')


def freeze(result,now):
    snapshot=copy.deepcopy(result.get('venue_test') or dict(status='unavailable',reason='not_calculated'))
    snapshot.update(version=VERSION,recorded_at=now.isoformat())
    return snapshot


def report(picks,as_of=None):
    as_of=as_of or datetime.now(timezone.utc)
    rows=[];seen=set();excluded=Counter()
    for pick in picks:
        test=pick.get('venue_test') or {}
        if test.get('version')!=VERSION:
            excluded['not_recorded_prospectively']+=1;continue
        try:
            recorded=instant(test['recorded_at']);kickoff=instant(pick['match']['date'])
            if recorded>=kickoff or recorded>as_of or recorded!=instant(pick['published_at']):raise ValueError('late_record')
            identity=(pick['match']['league'],pick['match']['id'],pick['market'])
            if identity in seen:excluded['duplicate']+=1;continue
            seen.add(identity);rows.append((recorded,kickoff,pick))
        except (KeyError,ValueError,TypeError,AttributeError):excluded['invalid_snapshot']+=1
    start=min((r[0] for r in rows),default=None)
    end=start+timedelta(days=WINDOW_DAYS) if start else None
    cohort=[p for recorded,kickoff,p in rows if recorded<end and kickoff<end]
    baseline=[];candidate=[];unavailable=Counter()
    for pick in cohort:
        test=pick['venue_test']
        p=(test.get('prediction') or {}).get('markets',{}).get(pick['market'])
        if test.get('status')!='ready':unavailable[test.get('reason','unknown')]+=1;continue
        values=[p,pick.get('probability')]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=100 for v in values):
            unavailable['market_missing_or_invalid']+=1;continue
        baseline.append(pick)
        candidate.append(dict(pick,probability=p,model_version=VERSION))
    original=evaluate(baseline,as_of=as_of);variant=evaluate(candidate,as_of=as_of)
    b=original['overall']['brier'];c=variant['overall']['brier']
    return dict(experiment=VERSION,status='waiting_for_new_choices' if not start else 'window_complete' if as_of>=end else 'collecting',
                registered=len(cohort),paired=len(baseline),coverage_pct=round(100*len(baseline)/len(cohort),1) if cohort else None,
                unavailable=dict(unavailable),excluded=dict(excluded),baseline=original,candidate=variant,
                brier_difference=round(c-b,6) if b is not None and c is not None else None,
                window=dict(days=WINDOW_DAYS,start=start.isoformat() if start else None,end=end.isoformat() if end else None),
                rules=dict(history_size=10,min_venue_matches=MIN_VENUE_MATCHES,max_history_days=180,scoring='same_poisson_function_as_baseline'),
                policy='same_selections_same_outcomes_paired_probability_comparison_no_automatic_activation',
                note='The market and result are identical in each pair; success rates therefore match. Compare Brier and calibration on the same pairs, with coverage. Negative Brier difference favours the venue variant; small samples do not establish improvement.')
