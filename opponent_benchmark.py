"""Experimental opponent-adjusted Poisson, evaluated chronologically, never promoted.

Rating and adjustment constants are hypotheses, not fitted or demonstrated gains.
Only records whose result was available before a prediction enter its state.
"""
import heapq
import math
from collections import defaultdict
from datetime import datetime

from adaptive_history import combine, MIN_SAMPLE
from champions_context import DOMESTIC_LEAGUES

VERSION = 'opponent-normalized-poisson-experiment-v1'
RATING_START = 1500.0
RATING_K = 20.0
RATING_SCALE = 400.0
NORMALIZATION_SCALE = 800.0


def instant(value):
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None: raise ValueError('UTC offset required')
    return date


def validate(records):
    seen = {}; games = []
    for original in records:
        row = dict(original)
        for key in ('id','league','home_id','away_id'):
            if not isinstance(row.get(key), str) or not row[key]: raise ValueError('Missing string '+key)
        if row['home_id'] == row['away_id']: raise ValueError('Identical teams')
        for key in ('home_goals','away_goals'):
            if isinstance(row.get(key),bool) or not isinstance(row.get(key),int) or not 0<=row[key]<=30:
                raise ValueError('Invalid score')
        if row.get('regulation_only') is not True: raise ValueError('90-minute result required')
        kickoff = instant(row['date']); available = instant(row['available_at'])
        if available <= kickoff: raise ValueError('Result cannot be available at kickoff')
        if row['id'] in seen:
            if row != seen[row['id']]: raise ValueError('Conflicting duplicate fixture')
            continue
        seen[row['id']] = row
        games.append(row)
    return sorted(games,key=lambda r:(instant(r['date']),r['id']))


class State:
    def __init__(self):
        self.ratings = defaultdict(lambda:RATING_START)
        self.histories = defaultdict(list)
        self.graph = defaultdict(set)
        self.counts = defaultdict(int)

    def add(self, game):
        home,away = game['home_id'],game['away_id']
        hr = game.get('rating_home_before',self.ratings[home])
        ar = game.get('rating_away_before',self.ratings[away])
        home_snapshot = dict(game,opponent_rating=ar)
        away_snapshot = dict(game,opponent_rating=hr)
        self.histories[home].append(home_snapshot)
        self.histories[away].append(away_snapshot)
        expected = 1/(1+10**((ar-hr)/RATING_SCALE))
        actual = 1 if game['home_goals']>game['away_goals'] else 0 if game['home_goals']<game['away_goals'] else .5
        change = RATING_K*(actual-expected)
        self.ratings[home] += change; self.ratings[away] -= change
        self.counts[home] += 1; self.counts[away] += 1
        self.graph[home].add(away); self.graph[away].add(home)

    def connected(self, home, away):
        seen = {home}; stack = [home]
        while stack:
            for team in self.graph[stack.pop()]-seen:
                if team == away: return True
                seen.add(team); stack.append(team)
        return False

    def sample(self, team, league, at):
        primary = [r for r in self.histories[team] if r['league']==league]
        primary,_ = combine(team,[(league,primary)],now=at)
        covered = {league}
        if league == 'uefa.champions':
            covered.update(DOMESTIC_LEAGUES)
            if len(primary)<10: covered.add('uefa.europa')
        batches = [(lg,[r for r in self.histories[team] if r['league']==lg]) for lg in sorted(covered)]
        return combine(team,batches,now=at)[0]

    def predict(self, home, away, league, at, probabilities, summary):
        # No outcome fields for the target fixture are accepted by this method.
        hm = self.sample(home,league,at); am = self.sample(away,league,at)
        if min(len(hm),len(am))<MIN_SAMPLE: return None,'insufficient_baseline_history'
        baseline = probabilities(summary(hm,home),summary(am,away))
        if not self.connected(home,away): return None,'disconnected_opponent_graph'
        def adjusted(games,team):
            gf = ga = 0.0
            for game in games:
                is_home = game['home_id']==team
                scored = game['home_goals'] if is_home else game['away_goals']
                conceded = game['away_goals'] if is_home else game['home_goals']
                factor = max(.75,min(1.33,10**((game['opponent_rating']-RATING_START)/NORMALIZATION_SCALE)))
                gf += scored*factor; ga += conceded/factor
            return dict(goals_for_avg=gf/len(games),goals_against_avg=ga/len(games))
        candidate = probabilities(adjusted(hm,home),adjusted(am,away))
        return dict(baseline=baseline,candidate=candidate,
                    samples={'home':len(hm),'away':len(am)},
                    ratings={'home':round(self.ratings[home],3),'away':round(self.ratings[away],3)}),None


def metrics(rows):
    if not rows: return {'count':0,'baseline':None,'candidate':None}
    result = {'count':len(rows),'evidence':'insufficient' if len(rows)<100 else 'requires_independent_review'}
    for model in ('baseline','candidate'):
        brier = logloss = correct = 0.0
        markets = defaultdict(float)
        for row in rows:
            p = row[model]['markets']; h,a = row['score']
            actual = 'home' if h>a else 'away' if h<a else 'draw'
            brier += sum((p[k]/100-int(k==actual))**2 for k in ('home','draw','away'))
            logloss -= math.log(max(1e-9,p[actual]/100))
            correct += max(('home','draw','away'),key=lambda k:p[k])==actual
            for key,outcome in [('over_2_5',h+a>=3),('btts',h>0 and a>0)]:
                markets[key] += (p[key]/100-int(outcome))**2
        n = len(rows)
        result[model] = dict(brier_1x2=round(brier/n,6),log_loss_1x2=round(logloss/n,6),
                             accuracy_1x2=round(correct/n,6),
                             brier_markets={k:round(v/n,6) for k,v in markets.items()})
    result['brier_delta_candidate_minus_baseline'] = round(result['candidate']['brier_1x2']-result['baseline']['brier_1x2'],6)
    return result


def run(records, validation_from, test_from, probabilities, summary):
    validation_at,test_at = instant(validation_from),instant(test_from)
    if validation_at>=test_at: raise ValueError('Validation must precede held-out test')
    games = validate(records)
    state = State(); waiting = []; rows = []; skipped = defaultdict(int)
    for index,game in enumerate(games):
        at = instant(game['date'])
        while waiting and waiting[0][0] < at:
            _,_,known = heapq.heappop(waiting)
            state.add(known)
        if at>=validation_at:
            prediction,reason = state.predict(game['home_id'],game['away_id'],game['league'],at,probabilities,summary)
            if prediction:
                rows.append(dict(id=game['id'],league=game['league'],date=game['date'],
                    split='test' if at>=test_at else 'validation',score=[game['home_goals'],game['away_goals']],**prediction))
            else: skipped[('test' if at>=test_at else 'validation')+':'+reason] += 1
        snapshot = dict(game,rating_home_before=state.ratings[game['home_id']],rating_away_before=state.ratings[game['away_id']])
        heapq.heappush(waiting,(instant(game['available_at']),index,snapshot))
    return dict(version=VERSION,parameters=dict(rating_k=RATING_K,rating_scale=RATING_SCALE,normalization_scale=NORMALIZATION_SCALE),
                validation_from=validation_from,test_from=test_from,
                validation=metrics([r for r in rows if r['split']=='validation']),
                test=metrics([r for r in rows if r['split']=='test']),
                by_competition={league:metrics([r for r in rows if r['split']=='test' and r['league']==league]) for league in sorted({r['league'] for r in rows})},
                scored_fixtures=len(rows),skipped=dict(skipped),predictions=rows,
                decision='experimental_only_no_automatic_promotion',
                availability_assumed_count=sum(bool(g.get('availability_assumed')) for g in games),
                limitations=['Retrospective archives may include later corrections; result availability must be audited.',
                    'Constants are unvalidated hypotheses; do not tune on held-out test.',
                    'Missing competitions and unobserved results limit opponent ratings.',
                    'Disconnected opponent graphs are excluded; compare coverage as well as scores.',
                    'Accuracy and Brier do not demonstrate profitability; no odds are recorded.'])
