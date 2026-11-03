"""Descriptive paired review of frozen offline predictions, never changes production."""
import math
import random
from collections import defaultdict
from opponent_benchmark import instant
from tracking import resolve

MARKETS = ('over_1_5', 'over_2_5', 'under_1_5', 'under_2_5',
           'btts', 'btts_no', 'home_or_draw', 'away_or_draw')
REPETITIONS = 1000
SEED = 1729


def paired_interval(rows):
    """Resample ISO weeks together across leagues; correlated fixtures stay grouped."""
    blocks = defaultdict(list)
    for date, delta in rows:
        year, week, _ = instant(date).isocalendar()
        blocks[(year, week)].append(delta)
    if len(blocks) < 8:
        return dict(weeks=len(blocks), interval_95=None, evidence='insufficient_weeks')
    sums = [(sum(values), len(values)) for values in blocks.values()]
    rng = random.Random(SEED)
    means = []
    for _ in range(REPETITIONS):
        selected = [rng.choice(sums) for _ in sums]
        means.append(sum(v for v, _ in selected) / sum(n for _, n in selected))
    means.sort()
    return dict(weeks=len(blocks), interval_95=[round(means[24], 6), round(means[974], 6)],
                evidence='descriptive_week_block_bootstrap')


def review(rows):
    output = {}
    for market in MARKETS:
        scores = {'baseline': [], 'candidate': []}
        predicted = {'baseline': [], 'candidate': []}
        outcomes = []; paired = []
        seen = set()
        for row in rows:
            identity = (row['league'], row['id'])
            if identity in seen:
                raise ValueError('Duplicate prediction')
            seen.add(identity)
            h, a = row['score']
            outcome = int(resolve(market, h, a))
            probabilities = {model: row[model]['markets'][market] / 100 for model in scores}
            if any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities.values()):
                raise ValueError('Invalid probability')
            outcomes.append(outcome)
            for model, p in probabilities.items():
                predicted[model].append(p)
                scores[model].append((p-outcome)**2)
            paired.append((row['date'], scores['candidate'][-1]-scores['baseline'][-1]))
        n = len(outcomes)
        result = dict(count=n, observed_pct=round(100*sum(outcomes)/n, 3) if n else None)
        for model in scores:
            mean = sum(predicted[model])/n if n else None
            result[model] = dict(brier=round(sum(scores[model])/n, 6) if n else None,
                                predicted_pct=round(100*mean, 3) if n else None,
                                calibration_gap_pp=round(100*(sum(outcomes)/n-mean), 3) if n else None)
        result['delta_candidate_minus_baseline'] = round(sum(v for _, v in paired)/n, 6) if n else None
        result['uncertainty'] = paired_interval(paired)
        output[market] = result
    return output


def extended_review(report):
    rows = report['predictions']
    test = [r for r in rows if r['split'] == 'test']
    return dict(version='paired-special-markets-review-v1',
                validation=review([r for r in rows if r['split'] == 'validation']),
                test=review(test),
                by_competition={league: review([r for r in test if r['league']==league])
                                for league in sorted({r['league'] for r in test})},
                uncertainty_method=dict(block='ISO calendar week across all competitions',
                                        repetitions=REPETITIONS, seed=SEED, minimum_weeks=8),
                decision='experimental_only_no_automatic_promotion',
                limitations=['Intervals are descriptive, not proof of generalization or profitability.',
                             'Teams also recur across weeks; week blocks do not remove all dependence.',
                             'Eight correlated markets are examined; intervals are not multiplicity-adjusted.',
                             'Retrospective availability is assumed; no prospective validation is claimed.',
                             'The historical replay reference is not every live production collection path.'])
