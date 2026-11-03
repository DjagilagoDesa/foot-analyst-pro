"""Read-only evaluation of frozen editorial probabilities; never tunes on outcomes."""
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

MODEL_VERSION = 'poisson-10-v1'


def evaluate(picks, *, as_of=None, window_days=None):
    """Optional rolling window uses kickoff, never publication or settlement time."""
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("as_of must include a timezone")
    if window_days is not None and (isinstance(window_days, bool) or not isinstance(window_days, int) or window_days <= 0):
        raise ValueError("window_days must be a positive integer")
    groups = defaultdict(list)
    excluded = defaultdict(int)
    events = set()
    for pick in picks:
        if pick.get('status') not in ('won', 'lost'):
            excluded[pick.get('status', 'unknown')] += 1
            continue
        probability = pick.get('probability')
        try:
            published = datetime.fromisoformat(pick['published_at'].replace('Z', '+00:00'))
            kickoff = datetime.fromisoformat(pick['match']['date'].replace('Z', '+00:00'))
            valid = (published.tzinfo is not None and kickoff.tzinfo is not None and published < kickoff
                     and isinstance(probability, (int, float)) and not isinstance(probability, bool)
                     and math.isfinite(probability) and 0 <= probability <= 100)
        except (KeyError, TypeError, ValueError, AttributeError):
            valid = False
        if not valid:
            excluded['invalid_snapshot'] += 1
            continue
        if kickoff > as_of:
            excluded['future_fixture'] += 1
            continue
        if window_days is not None and kickoff < as_of - timedelta(days=window_days):
            excluded['outside_window'] += 1
            continue
        match = pick['match']
        if not all(isinstance(value, str) and value.strip() for value in (match.get('league'), match.get('id'), pick.get('market'))):
            excluded['invalid_snapshot'] += 1
            continue
        identity = (match.get('league'), match.get('id'), pick.get('market'))
        if identity in events:
            excluded['duplicate'] += 1
            continue
        events.add(identity)
        value = (probability / 100, int(pick['status'] == 'won'))
        for key in [('overall', 'all'), ('market', pick.get('market', 'unknown')),
                    ('league', match.get('league', 'unknown')),
                    ('model', pick.get('model_version', 'legacy-unversioned')),
                    ('confidence', str(min(int(probability // 10) * 10, 90)))]:
            groups[key].append(value)

    def metrics(values):
        n = len(values)
        if not n:
            return dict(count=0, success_pct=None, predicted_pct=None, brier=None,
                        calibration_gap_pp=None, evidence='insufficient')
        actual = sum(y for _, y in values) / n
        predicted = sum(p for p, _ in values) / n
        return dict(count=n, won=sum(y for _, y in values), success_pct=round(100*actual, 2),
                    predicted_pct=round(100*predicted, 2),
                    brier=round(sum((p-y)**2 for p, y in values)/n, 6),
                    calibration_gap_pp=round(100*(actual-predicted), 2),
                    evidence='insufficient' if n < 100 else 'descriptive_only')
    return dict(overall=metrics(groups.get(('overall', 'all'), [])),
                breakdown={kind: {name: metrics(values) for (k, name), values in sorted(groups.items()) if k == kind}
                           for kind in ('market', 'league', 'model', 'confidence')},
                excluded=dict(excluded), scope='daily_opinion_only',
                window=dict(days=window_days, as_of=as_of.isoformat()),
                roi=None, roi_reason='No bookmaker odds recorded at publication.',
                limitations=['Selected editorial picks only; not all model predictions.',
                             'Markets may be correlated; counts are not independent trials.',
                             'Descriptive evaluation, not an out-of-sample model comparison.',
                             'No automatic probability adjustment or model promotion.'])
