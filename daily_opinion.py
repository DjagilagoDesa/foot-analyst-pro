"""Shared daily editorial board, persisted before kickoff, independent of user quotas."""
import copy
import json
import math
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import jsonify
from accounts import database, configured, DAILY_OPINION_SCHEMA
from tracking import fixture_info, score, resolve

PARIS = ZoneInfo('Europe/Paris')
INTERVAL = 900
LIMIT = 24
SCHEMA = DAILY_OPINION_SCHEMA
GROUPS = [('prudent', 3, 'Mes 3 choix prudents'),
          ('challenge', 2, 'Mes 2 choix plus difficiles'),
          ('surprise', 1, 'Ma surprise du jour')]
LABELS = {'home': 'Victoire domicile', 'away': 'Victoire extérieur', 'draw': 'Match nul',
          'home_or_draw': 'Double chance 1X', 'away_or_draw': 'Double chance X2',
          'over_1_5': 'Plus de 1,5 but', 'over_2_5': 'Plus de 2,5 buts',
          'under_2_5': 'Moins de 2,5 buts', 'btts': 'Les deux équipes marquent',
          'btts_no': 'Les deux équipes ne marquent pas toutes les deux'}


def judgement(result, market):
    m, h, a = result['match'], result['home'], result['away']
    hn, an = m['home']['name'], m['away']['name']
    goals = result['prediction']['expected_goals']
    total = round(goals['home'] + goals['away'], 2)
    if market in ('home', 'home_or_draw'):
        return (f"Mon scénario est favorable à {hn} : {goals['home']} but(s) attendu(s) contre {goals['away']} pour {an}. "
                f"Le point de vigilance est l’attaque de {an}, qui marque {a['goals_for_avg']} but(s) par match ; "
                f"{hn} en concède {h['goals_against_avg']}. Une victoire extérieure ferait perdre ce choix.")
    if market in ('away', 'away_or_draw'):
        return (f"Je retiens le scénario de {an}, dont l’attaque marque {a['goals_for_avg']} but(s) en moyenne "
                f"face à une défense de {hn} qui en concède {h['goals_against_avg']}. "
                f"Le modèle attend {goals['away']} but(s) à l’extérieur contre {goals['home']} à domicile. "
                f"Le risque contraire vient de {hn}, avec {h['wins']} victoires sur ses dix matchs étudiés.")
    if market.startswith('over_') or market.startswith('under_'):
        return (f"Je privilégie ici le total de buts plutôt que le vainqueur : le modèle prévoit {total} buts au total. "
                f"Les défenses de {hn} et {an} concèdent respectivement {h['goals_against_avg']} et {a['goals_against_avg']} but(s) par match. "
                'Un carton rouge, une composition différente ou une efficacité inhabituelle peuvent renverser ce scénario ; ces éléments ne sont pas vérifiés par ce modèle.')
    if market in ('btts', 'btts_no'):
        return (f"Je juge la capacité des deux attaques à marquer : {hn} produit {h['goals_for_avg']} but(s) par match, "
                f"{an} en produit {a['goals_for_avg']}. Le modèle attend {goals['home']} et {goals['away']} buts respectivement. "
                'Le risque dépend notamment de l’efficacité devant le but et des titulaires, dont les compositions ne sont pas vérifiées.')
    return (f"Je retiens le match nul, estimé à {result['prediction']['markets'].get('draw')} %. "
            f"Les projections sont de {goals['home']} but(s) pour {hn} et {goals['away']} pour {an}. "
            'Un écart de niveau offensif réellement supérieur aux moyennes observées peut faire basculer le match.')


def today(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(PARIS).date().isoformat()


def upcoming(match, now, day):
    try:
        date = datetime.fromisoformat(match['date'].replace('Z', '+00:00'))
        return (date.tzinfo is not None and date > now and today(date) == day
                and match['state'] == 'pre' and not match['completed']
                and not any(x in match.get('status_name', '').upper()
                            for x in ('POSTPON', 'CANCEL', 'ABANDON', 'SUSPEND')))
    except (KeyError, ValueError, TypeError, AttributeError):
        return False


def candidates_for(result, group):
    markets = {key: value for key, value in result['prediction']['markets'].items()
               if isinstance(value, (int, float)) and not isinstance(value, bool)
               and math.isfinite(value) and 0 <= value <= 100}
    if group == 'surprise':
        # Oppose the favourite in the 1X2 model; never relabel a favourite as a surprise.
        keys = [k for k, opposite in [('home', 'away'), ('away', 'home')]
                if markets.get(k, 0) + 5 <= markets.get(opposite, 0)]
        low, high = 25, 45
    else:
        keys = list(LABELS)
        low, high = (75, 95) if group == 'prudent' else (50, 70)
    return sorted([{'market': k, 'probability': markets[k]}
                   for k in keys if isinstance(markets.get(k), (int, float))
                   and math.isfinite(markets[k]) and low <= markets[k] <= high],
                  key=lambda p: (-p['probability'], p['market']))


def choose(results, existing, now, day):
    """Fill vacant slots only; published choices and their probabilities never change."""
    picks = copy.deepcopy(existing)
    used_events = {p['match']['id'] for p in picks}
    used_teams = {str(p['match'][side]['id']) for p in picks for side in ('home', 'away')}
    for group, count, _ in GROUPS:
        pool = []
        for r in results:
            if not upcoming(r['match'], now, day):
                continue
            options = candidates_for(r, group)
            if options:
                pool.append((r, options[0]))
        pool.sort(key=lambda pair: (-pair[1]['probability'], pair[0]['match']['date'], pair[0]['match']['id']))
        missing = count - sum(p['group'] == group for p in picks)
        for r, choice in pool:
            if missing <= 0:
                break
            m = r['match']
            ids = {str(m[s]['id']) for s in ('home', 'away')}
            if m['id'] in used_events or ids & used_teams:
                continue
            home, away = r['home'], r['away']
            hname, aname = m['home']['name'], m['away']['name']
            rationale = (f"{hname} : {home['wins']} victoires, {home['draws']} nuls et {home['losses']} défaites "
                         f"sur {home['matches']} matchs, {home['goals_for_avg']} but(s) marqué(s) et "
                         f"{home['goals_against_avg']} encaissé(s) en moyenne. "
                         f"{aname} : {away['wins']} victoires, {away['draws']} nuls et {away['losses']} défaites "
                         f"sur {away['matches']} matchs, {away['goals_for_avg']} but(s) marqué(s) et "
                         f"{away['goals_against_avg']} encaissé(s) en moyenne.")
            if group == 'surprise':
                rationale += ' Je retiens ici une victoire du côté moins favori selon le modèle : un scénario minoritaire, pas une forte confiance.'
            else:
                rationale += f" Parmi les marchés admissibles pour ce profil, je privilégie {LABELS[choice['market']].lower()}, estimé à {choice['probability']} %."
            rationale += ' ' + judgement(r, choice['market'])
            picks.append(dict(group=group, match=m, **choice, market_label=LABELS[choice['market']],
                              rationale=rationale, expected_goals=r['prediction']['expected_goals'],
                              published_at=now.isoformat(), status='pending', home_score=None, away_score=None))
            used_events.add(m['id'])
            used_teams.update(ids)
            missing -= 1
    return picks


class DailyOpinion:
    def __init__(self, app, server):
        self.app, self.server = app, server
        self.lock = threading.Lock()
        self.started = False

    def read(self, day):
        with database() as db:
            db.execute(SCHEMA)
            row = db.execute('SELECT payload,checked_at FROM daily_opinion_boards WHERE day=?', (day,)).fetchone()
        return (json.loads(row['payload']), row['checked_at']) if row else ({}, 0)

    def performance(self, day):
        # Official app rate: only persisted editorial picks, since the first publication.
        # Personal account_predictions and account_analyses never enter this query.
        with database() as db:
            rows = db.execute('SELECT payload FROM daily_opinion_boards WHERE day<=?', (day,)).fetchall()
        counts = {k: 0 for k in ('won', 'lost', 'pending', 'void')}
        for row in rows:
            for pick in json.loads(row['payload']).get('picks', []):
                counts[pick['status']] += 1
        settled = counts['won'] + counts['lost']
        return dict(**counts, success_pct=round(100 * counts['won'] / settled, 1) if settled else None,
                    scope='daily_opinion_only', period='since_first_publication')

    def refresh(self, now=None):
        now = now or datetime.now(timezone.utc)
        day, epoch = today(now), int(now.timestamp())
        token = uuid.uuid4().hex
        with database() as db:
            db.execute(SCHEMA)
            db.execute("INSERT INTO daily_opinion_boards(day,payload) VALUES(?,'{}') ON CONFLICT(day) DO NOTHING", (day,))
            row = db.execute('''UPDATE daily_opinion_boards SET lease_until=?,lease_token=?
                WHERE day=? AND checked_at<=? AND lease_until<=? RETURNING payload''',
                (epoch + 300, token, day, epoch - INTERVAL, epoch)).fetchone()
        if not row:
            return
        board = json.loads(row['payload'])
        try:
            # Results must progress even when today's fixture feed is unavailable.
            self.settle_previous(day)
            matches, failures = self.fixtures(day)
            if not matches and failures:
                raise RuntimeError('sports_sources_unavailable')
            existing = board.get('picks', [])
            results = []
            eligible = [m for m in matches if upcoming(m, now, day)]
            # Sample across kick-off times rather than only the first games of the day.
            eligible.sort(key=lambda m: (m['date'], m['id']))
            if len(eligible) > LIMIT:
                eligible = [eligible[round(i * (len(eligible) - 1) / (LIMIT - 1))] for i in range(LIMIT)]
            if len(existing) < 6:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    jobs = [pool.submit(self.analyze, m) for m in eligible
                            if m['id'] not in {p['match']['id'] for p in existing}]
                    for job in as_completed(jobs):
                        try:
                            result = job.result()
                            if result:
                                results.append(result)
                        except Exception:
                            failures += 1
            # Re-check the real clock after network calls: never publish a started match.
            publication = datetime.now(timezone.utc) if self.app.testing is False else now
            picks = choose(results, existing, publication, day)
            updated = dict(day=day, picks=picks, generated_at=board.get('generated_at') or publication.isoformat(),
                           checked_at=publication.isoformat(), source_errors=failures,
                           fixtures_found=len(matches), candidates_examined=len(eligible))
            self.settle(updated)
            with database() as db:
                db.execute('''UPDATE daily_opinion_boards SET payload=?,checked_at=?,lease_until=0,lease_token=''
                    WHERE day=? AND lease_token=?''',
                    (json.dumps(updated, ensure_ascii=False), int(publication.timestamp()), day, token))
        except Exception:
            # Keep published choices and their original freshness timestamp, but
            # still settle today's known events independently of the fixture feed.
            if board.get('picks'):
                settled = copy.deepcopy(board)
                self.settle(settled)
                if settled['picks'] != board['picks']:
                    board = settled
            with database() as db:
                db.execute("UPDATE daily_opinion_boards SET payload=?,lease_until=?,lease_token='' WHERE day=? AND lease_token=?",
                           (json.dumps(board, ensure_ascii=False), epoch + 60, day, token))
            raise

    def fixtures(self, day):
        start = datetime.fromisoformat(day).replace(tzinfo=PARIS)
        utc_days = {start.astimezone(timezone.utc).strftime('%Y%m%d'),
                    (start + timedelta(days=1, microseconds=-1)).astimezone(timezone.utc).strftime('%Y%m%d')}
        found, errors = {}, 0
        def load(league, date):
            data = self.server.fetch(f'{self.server.ESPN}/{league}/scoreboard', {'dates': date, 'limit': 200}, ttl=120)
            return [self.server._fixture(e, league) for e in data.get('events', [])]
        with ThreadPoolExecutor(max_workers=8) as pool:
            jobs = [pool.submit(load, league, date) for league in self.server.LEAGUES for date in utc_days]
            for job in as_completed(jobs):
                try:
                    for match in job.result():
                        if match and today(datetime.fromisoformat(match['date'].replace('Z', '+00:00'))) == day:
                            found[match['id']] = match
                except Exception:
                    errors += 1
        return list(found.values()), errors

    def analyze(self, match):
        # Independent of /api/analyze: no account, history, or trial balance is touched.
        home_games, he = self.server.history(match['league'], match['home']['id'])
        away_games, ae = self.server.history(match['league'], match['away']['id'])
        if len(home_games) < 10 or len(away_games) < 10:
            return None
        home = self.server.summary(home_games, match['home']['id'])
        away = self.server.summary(away_games, match['away']['id'])
        return dict(match=match, home=home, away=away, prediction=self.server.probabilities(home, away))

    def settle(self, board):
        errors = 0
        for pick in board.get('picks', []):
            if pick['status'] != 'pending':
                continue
            m = pick['match']
            try:
                info = fixture_info(self.server.fetch(f"{self.server.ESPN}/{m['league']}/summary", {'event': m['id']}, ttl=120))
                if info['home_id'] != str(m['home']['id']) or info['away_id'] != str(m['away']['id']):
                    raise ValueError('teams_mismatch')
                void = any(x in info['name'] for x in ('CANCEL', 'ABANDON', 'POSTPON'))
                if not void and not (info['completed'] and info['state'] == 'post'):
                    continue
                # Refuse extra-time/penalty totals for ordinary 90-minute markets.
                void |= (info['period'] is not None and int(info['period']) > 2)
                void |= any(x in info['name'] for x in ('EXTRA_TIME', 'PENALT', 'FINAL_AET', 'AFTER_EXTRA'))
                if void:
                    pick['status'] = 'void'
                else:
                    h, a = score(info['home'].get('score')), score(info['away'].get('score'))
                    pick.update(status='won' if resolve(pick['market'], h, a) else 'lost', home_score=h, away_score=a)
            except Exception:
                errors += 1
        board['result_source_errors'] = errors

    def settle_previous(self, day):
        with database() as db:
            rows = db.execute('SELECT day,payload FROM daily_opinion_boards WHERE day<? ORDER BY day', (day,)).fetchall()
        for row in rows:
            board = json.loads(row['payload'])
            if not any(p['status'] == 'pending' for p in board.get('picks', [])):
                continue
            self.settle(board)
            with database() as db:
                # A slower worker must never overwrite results saved by another.
                db.execute('UPDATE daily_opinion_boards SET payload=? WHERE day=? AND payload=?',
                           (json.dumps(board, ensure_ascii=False), row['day'], row['payload']))

    def start(self):
        if self.app.testing or not configured():
            return
        with self.lock:
            if self.started:
                return
            self.started = True
        def loop():
            while True:
                with self.app.app_context():
                    try:
                        self.refresh()
                    except Exception as error:
                        self.app.logger.warning('Daily opinion refresh failed (%s)', type(error).__name__)
                time.sleep(60)
        threading.Thread(target=loop, name='daily-opinion', daemon=True).start()


def init_app(app, server):
    service = DailyOpinion(app, server)
    app.extensions['daily_opinion'] = service

    @app.before_request
    def start_daily_worker():
        service.start()

    @app.get('/api/daily-opinion')
    def daily_board():
        day = today()
        if not configured():
            return jsonify(status='unavailable', day=day, message='Les choix du jour sont en cours d’activation.'), 503
        board, checked = service.read(day)
        service.start()
        stale = time.time() - checked > INTERVAL * 2
        status = 'ready' if len(board.get('picks', [])) == 6 else 'partial' if checked else 'preparing'
        groups = [dict(id=key, title=title, target=count,
                       picks=[p for p in board.get('picks', []) if p['group'] == key]) for key, count, title in GROUPS]
        response = jsonify(**{k: v for k, v in board.items() if k not in ('day', 'picks')},
            day=day, status=status, stale=stale, groups=groups,
            performance=service.performance(day),
            refresh_seconds=30 if status == 'preparing' else 120,
            method='Modèle statistique Poisson, 10 matchs terminés par équipe. Pas de cotes bookmaker, compositions ou absences vérifiées. Probabilités non calibrées.',
            scope=f'Compétitions couvertes : {len(server.LEAGUES)}. Au maximum {LIMIT} rencontres étudiées, réparties sur la journée. Ce n’est pas une sélection exhaustive du football mondial.',
            update_note='Nouvelle journée à minuit, heure de Paris. Vérification environ toutes les 15 minutes lorsque le serveur est actif ; reprise à son réveil. Les choix publiés restent figés, les places manquantes peuvent être complétées avant le coup d’envoi.')
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/daily-opinion.js')
    def daily_script():
        from flask import send_from_directory
        return send_from_directory('.', 'daily-opinion.js', mimetype='application/javascript')
