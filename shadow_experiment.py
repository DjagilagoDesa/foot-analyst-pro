"""Prospective, immutable daily-10 comparison. Never supplies user-facing picks."""
import copy
import gzip
import hashlib
import heapq
import json
import math
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from flask import jsonify
from accounts import database, configured
from daily_opinion import today, upcoming
from opponent_benchmark import State, instant, validate, VERSION as RATING_VERSION
from opponent_review import extended_review, MARKETS
from tracking import fixture_info, score

VERSION = 'opponent-normalized-daily10-shadow-v1'
LEAGUES = ('eng.1','esp.1','ita.1','ger.1','fra.1','por.1','ned.1','uefa.champions')
INTERVAL = 900
DAILY_LIMIT = 12
BATCH_LIMIT = 2
MARGIN_SECONDS = 60
SEED_PATH = Path(__file__).with_name('shadow_seed.json.gz')
SCHEMA = (
    '''CREATE TABLE IF NOT EXISTS shadow_results (
        event_id TEXT PRIMARY KEY, league TEXT NOT NULL, kickoff TEXT NOT NULL,
        available_at TEXT NOT NULL, payload TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS shadow_pairs (
        experiment TEXT NOT NULL, league TEXT NOT NULL, event_id TEXT NOT NULL,
        day TEXT NOT NULL, recorded_at TEXT NOT NULL, starts_at TEXT NOT NULL,
        payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        home_score INTEGER, away_score INTEGER, settled_at TEXT, result_checked_at BIGINT NOT NULL DEFAULT 0,
        PRIMARY KEY(experiment,league,event_id))''',
    '''CREATE TABLE IF NOT EXISTS shadow_attempts (
        experiment TEXT NOT NULL, league TEXT NOT NULL, event_id TEXT NOT NULL,
        attempted_at TEXT NOT NULL, reason TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY(experiment,league,event_id))''',
    '''CREATE TABLE IF NOT EXISTS shadow_control (
        experiment TEXT PRIMARY KEY, checked_at BIGINT NOT NULL DEFAULT 0,
        lease_until BIGINT NOT NULL DEFAULT 0, lease_token TEXT NOT NULL DEFAULT '',
        metadata TEXT NOT NULL DEFAULT '{}')''')


def utcnow():
    return datetime.now(timezone.utc)


def replay(records, at):
    """Recreate kickoff rating snapshots using first observed result availability."""
    state = State(); waiting = []
    for index, game in enumerate(validate(records)):
        kickoff = instant(game['date'])
        if kickoff >= at:
            continue
        while waiting and waiting[0][0] < kickoff:
            _, _, known = heapq.heappop(waiting); state.add(known)
        snapshot = dict(game, rating_home_before=state.ratings[game['home_id']],
                        rating_away_before=state.ratings[game['away_id']])
        heapq.heappush(waiting, (instant(game['available_at']), index, snapshot))
    while waiting and waiting[0][0] < at:
        _, _, known = heapq.heappop(waiting); state.add(known)
    return state


def predict_pair(server, state, match):
    histories = {}; errors = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {side: pool.submit(server.history, match['league'], match[side]['id']) for side in ('home','away')}
        for side, job in jobs.items():
            histories[side], errors[side] = job.result()
    if any(errors.values()):
        return None, 'partial_history'
    if any(len(rows) != 10 for rows in histories.values()):
        return None, 'insufficient_history'
    home, away = str(match['home']['id']), str(match['away']['id'])
    if not state.connected(home, away):
        return None, 'disconnected_ratings'
    adjusted = {}; evidence = {}
    for side, team in (('home', home), ('away', away)):
        known = {row['id']: row for row in state.histories[team]}
        gf = ga = 0.0
        for game in histories[side]:
            old = known.get(game['id'])
            if not old or any(old[key] != game[key] for key in ('home_id','away_id','home_goals','away_goals','date')):
                return None, 'unmatched_history'
            # Same frozen adjustment as v1, on exactly the live daily-10 baseline inputs.
            factor = max(.75, min(1.33, 10**((old['opponent_rating']-1500)/800)))
            is_home = game['home_id'] == team
            gf += game['home_goals' if is_home else 'away_goals'] * factor
            ga += game['away_goals' if is_home else 'home_goals'] / factor
        adjusted[side] = dict(goals_for_avg=gf/10, goals_against_avg=ga/10)
        evidence[side] = [dict(game, opponent_rating=known[game['id']]['opponent_rating']) for game in histories[side]]
    baseline = server.probabilities(server.summary(histories['home'],home), server.summary(histories['away'],away))
    candidate = server.probabilities(adjusted['home'], adjusted['away'])
    for prediction in (baseline, candidate):
        if any(isinstance(prediction['markets'].get(k), bool) or not isinstance(prediction['markets'].get(k),(int,float))
               or not math.isfinite(prediction['markets'][k]) or not 0 <= prediction['markets'][k] <= 100 for k in MARKETS):
            return None, 'invalid_probabilities'
    return dict(match=copy.deepcopy(match), baseline=baseline, candidate=candidate, histories=evidence,
                baseline_version='daily-opinion-poisson-10-live', rating_version=RATING_VERSION,
                candidate_version=VERSION,
                evidence_sha256=hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest()), None


class ShadowExperiment:
    def __init__(self, app, server, clock=utcnow):
        self.app, self.server, self.clock = app, server, clock
        self.lock = threading.Lock(); self.started = False

    def initialize(self):
        with database() as db:
            for sql in SCHEMA: db.execute(sql)
            db.execute('INSERT INTO shadow_control(experiment) VALUES(?) ON CONFLICT DO NOTHING',(VERSION,))

    def record(self, pair, token=None):
        """Verify authoritative fixture again, then check clock inside the DB transaction."""
        match = pair['match']
        info = fixture_info(self.server.fetch(f"{self.server.ESPN}/{match['league']}/summary", {'event':match['id']}, ttl=0))
        if (info['home_id'],info['away_id']) != (str(match['home']['id']),str(match['away']['id'])):
            return 'teams_mismatch'
        if info['date'] != instant(match['date']): return 'kickoff_changed'
        with database() as db:
            lock_sql = 'SELECT lease_token,lease_until FROM shadow_control WHERE experiment=?'
            control = db.execute(lock_sql + ('' if db.sqlite else ' FOR UPDATE'), (VERSION,)).fetchone()
            now = self.clock()
            if token and (not control or control['lease_token'] != token or control['lease_until'] <= now.timestamp()):
                return 'expired_lease'
            if not upcoming(match,now,today(now)) or info['state']!='pre' or info['completed']:
                return 'not_prematch'
            if any(x in info['name'] for x in ('CANCEL','POSTPON','ABANDON','SUSPEND')):
                return 'not_prematch'
            if (info['date']-now).total_seconds() <= MARGIN_SECONDS: return 'too_late'
            existing = db.execute('SELECT 1 FROM shadow_pairs WHERE experiment=? AND league=? AND event_id=?',
                                  (VERSION,match['league'],match['id'])).fetchone()
            if existing: return 'already_recorded'
            n = db.execute('SELECT count(*) AS n FROM shadow_pairs WHERE experiment=? AND day=?', (VERSION,today(now))).fetchone()['n']
            if n >= DAILY_LIMIT: return 'daily_limit'
            db.execute('''INSERT INTO shadow_pairs(experiment,league,event_id,day,recorded_at,starts_at,payload)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT DO NOTHING''',
                (VERSION,match['league'],match['id'],today(now),now.isoformat(),match['date'],json.dumps(pair,sort_keys=True)))
        return 'recorded'

    def observe(self, day):
        """Bounded scoreboard catch-up; availability is first actual observation time."""
        fixtures = []; errors = 0; new = []
        for league in LEAGUES:
            for offset in range(3):
                date = (instant(day+'T12:00:00Z')-timedelta(days=offset)).strftime('%Y%m%d')
                try:
                    data = self.server.fetch(f'{self.server.ESPN}/{league}/scoreboard', {'dates':date,'limit':1000}, ttl=120)
                    observed = self.clock()
                    for event in data.get('events',[]):
                        match = self.server._fixture(event,league)
                        if match and upcoming(match,observed,today(observed)): fixtures.append(match)
                        comp = (event.get('competitions') or [{}])[0]
                        if (comp.get('status') or event.get('status') or {}).get('period') != 2: continue
                        for row in self.server.parse_events({'events':[event]}, regulation_only=True):
                            if instant(row['date']) >= observed: continue
                            new.append(dict(row,league=league,regulation_only=True,
                                            available_at=observed.isoformat(),availability_assumed=False,
                                            source_url=f'https://www.espn.com/soccer/match/_/gameId/{row["id"]}'))
                except Exception:
                    errors += 1
        with database() as db:
            for row in new:
                db.execute('''INSERT INTO shadow_results(event_id,league,kickoff,available_at,payload)
                    VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING''',
                    (row['id'],row['league'],row['date'],row['available_at'],json.dumps(row,sort_keys=True)))
        return list({(m['league'],m['id']):m for m in fixtures}.values()), errors

    def state(self, at):
        seed = json.loads(gzip.decompress(SEED_PATH.read_bytes()))
        with database() as db:
            observed = [json.loads(r['payload']) for r in db.execute('SELECT payload FROM shadow_results').fetchall()]
        # Source seed is immutable; a newer observation never rewrites a training result.
        merged = {r['id']:r for r in seed}
        for row in observed: merged.setdefault(row['id'],row)
        return replay(list(merged.values()),at)

    def settle(self):
        with database() as db:
            pending = db.execute("SELECT * FROM shadow_pairs WHERE experiment=? AND status='pending' ORDER BY result_checked_at,starts_at",(VERSION,)).fetchall()
        pending = [row for row in pending if instant(row['starts_at']) < self.clock()][:12]
        for row in pending:
            if instant(row['starts_at']) >= self.clock(): continue
            try:
                pair = json.loads(row['payload']); m = pair['match']
                info = fixture_info(self.server.fetch(f"{self.server.ESPN}/{m['league']}/summary",{'event':m['id']},ttl=60))
                if (info['home_id'],info['away_id']) != (str(m['home']['id']),str(m['away']['id'])): continue
                void = any(x in info['name'] for x in ('CANCEL','POSTPON','ABANDON'))
                void |= info['date'] != instant(row['starts_at']) or info['date'] <= instant(row['recorded_at'])
                if not void and not (info['completed'] and info['state']=='post'): continue
                void |= info['period'] is None or int(info['period']) != 2
                void |= any(x in info['name'] for x in ('EXTRA_TIME','PENALT','FINAL_AET','AFTER_EXTRA'))
                h,a = (None,None) if void else (score(info['home'].get('score')),score(info['away'].get('score')))
                with database() as db:
                    db.execute("UPDATE shadow_pairs SET status=?,home_score=?,away_score=?,settled_at=? WHERE experiment=? AND league=? AND event_id=? AND status='pending'",
                               ('void' if void else 'complete',h,a,self.clock().isoformat(),VERSION,row['league'],row['event_id']))
            except Exception as error:
                self.app.logger.warning('Shadow result source failed (%s)',type(error).__name__)
            finally:
                with database() as db:
                    db.execute('UPDATE shadow_pairs SET result_checked_at=? WHERE experiment=? AND league=? AND event_id=?',
                               (int(self.clock().timestamp()),VERSION,row['league'],row['event_id']))

    def refresh(self):
        self.initialize(); now = self.clock(); epoch = int(now.timestamp()); token=uuid.uuid4().hex
        with database() as db:
            lease = db.execute('''UPDATE shadow_control SET lease_until=?,lease_token=? WHERE experiment=?
                AND lease_until<=? AND checked_at<=? RETURNING experiment''',
                (epoch+600,token,VERSION,epoch,epoch-INTERVAL)).fetchone()
        if not lease: return
        metadata = {'reasons':{}}
        try:
            self.settle()
            fixtures, errors = self.observe(today(now))
            metadata['source_errors']=errors
            with database() as db:
                existing = db.execute('SELECT league,event_id FROM shadow_pairs WHERE experiment=? AND day=?',(VERSION,today(now))).fetchall()
            with database() as db:
                attempts = {(r['league'],r['event_id']):r['attempts'] for r in db.execute('SELECT league,event_id,attempts FROM shadow_attempts WHERE experiment=?',(VERSION,)).fetchall()}
            done = {(r['league'],r['event_id']) for r in existing}
            eligible = sorted([m for m in fixtures if (m['league'],m['id']) not in done],key=lambda m:(attempts.get((m['league'],m['id']),0),m['date'],m['league'],m['id']))
            if len(existing)<DAILY_LIMIT and eligible:
                state_as_of = self.clock()
                state = self.state(state_as_of)
                for match in eligible[:min(BATCH_LIMIT,DAILY_LIMIT-len(existing))]:
                    try:
                        pair,reason = predict_pair(self.server,state,match)
                        if pair:
                            pair.update(rating_as_of=state_as_of.isoformat(),
                                        training_seed_sha256=hashlib.sha256(SEED_PATH.read_bytes()).hexdigest(),
                                        cycle_source_errors=errors)
                            reason = self.record(pair, token=token)
                    except Exception as error:
                        reason = 'source_or_input_error'
                        self.app.logger.warning('Shadow prediction failed (%s)',type(error).__name__)
                    metadata['reasons'][reason]=metadata['reasons'].get(reason,0)+1
                    with database() as db:
                        db.execute('''INSERT INTO shadow_attempts(experiment,league,event_id,attempted_at,reason)
                            VALUES(?,?,?,?,?) ON CONFLICT(experiment,league,event_id) DO UPDATE SET
                            attempted_at=excluded.attempted_at,reason=excluded.reason,attempts=shadow_attempts.attempts+1''',
                            (VERSION,match['league'],match['id'],self.clock().isoformat(),reason))
            metadata['fixtures_found']=len(fixtures)
        except Exception as error:
            metadata['error']=type(error).__name__
            self.app.logger.warning('Shadow cycle failed (%s)',type(error).__name__)
        finally:
            with database() as db:
                db.execute("UPDATE shadow_control SET checked_at=?,lease_until=0,lease_token='',metadata=? WHERE experiment=? AND lease_token=?",
                           (int(self.clock().timestamp()),json.dumps(metadata),VERSION,token))

    def report(self):
        self.initialize()
        with database() as db:
            records = db.execute('SELECT * FROM shadow_pairs WHERE experiment=? ORDER BY recorded_at',(VERSION,)).fetchall()
            control = db.execute('SELECT checked_at,metadata FROM shadow_control WHERE experiment=?',(VERSION,)).fetchone()
            coverage = [dict(r) for r in db.execute('SELECT reason,count(*) AS fixtures,sum(attempts) AS attempts FROM shadow_attempts WHERE experiment=? GROUP BY reason',(VERSION,)).fetchall()]
        counts = dict(Counter(r['status'] for r in records)); rows=[]
        for record in records:
            if record['status']!='complete': continue
            pair=json.loads(record['payload']); m=pair['match']
            if instant(record['recorded_at']) >= instant(record['starts_at']): continue
            rows.append(dict(id=m['id'],league=m['league'],date=m['date'],split='test',
                             baseline=pair['baseline'],candidate=pair['candidate'],
                             score=[record['home_score'],record['away_score']]))
        health = json.loads(control['metadata'])
        status = 'preparing' if not control['checked_at'] else 'degraded' if health.get('error') or health.get('source_errors') else 'collecting'
        return dict(experiment=VERSION,status=status,registered=len(records),counts=counts,
                    checked_at=control['checked_at'],last_cycle=json.loads(control['metadata']),
                    comparison=extended_review({'predictions':rows}),
                    coverage=coverage,
                    scope='bounded_prospective_daily10_shadow_only',
                    note='Actual pre-kickoff snapshots; retrospective training seed. No model promotion or official performance changes. Daily10 variant differs from the historical adaptive20 experiment.')

    def start(self):
        if self.app.testing or not configured(): return
        with self.lock:
            if self.started: return
            self.started=True
        def loop():
            while True:
                with self.app.app_context():
                    try: self.refresh()
                    except Exception as error: self.app.logger.warning('Shadow worker failed (%s)',type(error).__name__)
                time.sleep(60)
        threading.Thread(target=loop,name='shadow-experiment',daemon=True).start()


def init_app(app, server):
    service=ShadowExperiment(app,server); app.extensions['shadow_experiment']=service
    @app.before_request
    def start_shadow_worker(): service.start()
    @app.get('/api/shadow-experiment')
    def shadow_report():
        if not configured(): return jsonify(status='unavailable'),503
        response=jsonify(service.report());response.headers['Cache-Control']='no-store';return response
