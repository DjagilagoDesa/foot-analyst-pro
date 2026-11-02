"""Observed domestic form for UCL reports; no changes to model probabilities."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

DOMESTIC_LEAGUES = ('eng.1', 'esp.1', 'ita.1', 'ger.1', 'fra.1', 'por.1', 'ned.1', 'tur.1', 'ukr.1', 'nor.1', 'bel.1', 'sco.1', 'aut.1', 'sui.1', 'gre.1', 'den.1', 'cze.1', 'cro.1', 'srb.1', 'pol.1', 'swe.1')
CONTEXT_VERSION = 1


def instant(value):
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('missing_timezone')
    return date


def collect(server, home_id, away_id, event_id='', now=None):
    now = now or datetime.now(timezone.utc)
    ids = (str(home_id), str(away_id))
    result = dict(version=CONTEXT_VERSION, observed_at=now.isoformat(), fixture_verified=False,
                  kickoff=None, coverage=list(DOMESTIC_LEAGUES), failed_leagues=[], teams={},
                  note='Forme nationale limitée aux cinq résultats disponibles sur 180 jours. Repos observé entre coups d’envoi dans les championnats couverts et la Ligue des champions ; coupes nationales, sélections et autres compétitions non couvertes. Ce n’est pas une mesure complète de fatigue.')
    if str(event_id).isdigit():
        try:
            from tracking import fixture_info
            info = fixture_info(server.fetch(f'{server.ESPN}/uefa.champions/summary', {'event':str(event_id)}, ttl=120))
            if (info['home_id'], info['away_id']) == ids and info['state'] == 'pre' and info['date'] > now and not any(x in info['name'] for x in ('POSTPON', 'CANCEL', 'ABANDON', 'SUSPEND')):
                result.update(fixture_verified=True, kickoff=info['date'].isoformat())
        except Exception:
            pass  # Context remains explicitly incomplete; never invent fixture dates.
    membership = {team: [] for team in ids}

    def roster(league):
        data = server.fetch(f'{server.ESPN}/{league}/teams', ttl=86400)
        teams = {str(entry['team']['id']) for sport in data.get('sports', [])
                 for group in sport.get('leagues', []) for entry in group.get('teams', [])
                 if entry.get('team', {}).get('id') is not None}
        return teams

    with ThreadPoolExecutor(max_workers=12) as pool:
        jobs = {pool.submit(roster, league):league for league in DOMESTIC_LEAGUES}
        for job in as_completed(jobs):
            league = jobs[job]
            try:
                members = job.result()
                for team in ids:
                    if team in members: membership[team].append(league)
            except Exception:
                result['failed_leagues'].append(league)
    result['failed_leagues'].sort()

    def team_context(team):
        found = sorted(membership[team])
        if len(found) != 1:
            return dict(status='unavailable', reason='ambiguous_league' if found else 'league_not_found',
                        games=[], sample=0, rest_hours=None)
        league = found[0]
        rows, errors = server.history(league, team, limit=20, regulation_only=True)
        def recent(rows):
            eligible = []
            for match in rows:
                try:
                    age = (now-instant(match['date'])).total_seconds()
                    if 3*3600 <= age <= 180*86400 and team in (str(match['home_id']), str(match['away_id'])):
                        eligible.append(match)
                except (KeyError, TypeError, ValueError, AttributeError):
                    continue
            return sorted(eligible, key=lambda m:instant(m['date']), reverse=True)
        games = recent(rows)[:5]
        # Rest includes observed European games as well as the domestic sample.
        european, european_errors = server.history('uefa.champions', team, regulation_only=False)
        observed = recent(rows + european)
        last = observed[0] if observed else None
        rest = None
        if last and result['fixture_verified']:
            rest = round((instant(result['kickoff'])-instant(last['date'])).total_seconds()/3600, 1)
        return dict(status='partial' if errors or european_errors or len(games)<5 else 'ok',
                    league=league, sample=len(games), games=games,
                    model_games=rows,
                    record=server.summary(games, team) if games else None,
                    rest_hours=rest, last_observed_match=last,
                    source_errors={'domestic':errors, 'european':european_errors})

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {pool.submit(team_context, team):team for team in ids}
        for job in as_completed(jobs):
            team = jobs[job]
            try: result['teams'][team] = job.result()
            except Exception:
                result['teams'][team] = dict(status='unavailable', reason='source_error', games=[], sample=0, rest_hours=None)
    return result
