"""One frozen daily scorer, selected from observed ESPN player and fixture data.

The ranking is an uncalibrated comparison, not a scoring probability. Match
results use player match statistics, never the team score or season totals.
"""
import copy
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from tracking import fixture_info

MODEL = 'scorer-international-usage-v4'
from competitions import WOMENS_LEAGUES, national_group, representative_fixtures
MAX_FIXTURES = 48


def instant(value):
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None: raise ValueError('timezone_required')
    return date


def number(value):
    if isinstance(value,bool): return None
    try:
        n=float(value)
        return n if math.isfinite(n) and 0<=n<=10000 else None
    except (TypeError,ValueError): return None


def stats(rows):
    return {row['name']:number(row.get('value')) for row in rows if isinstance(row,dict) and isinstance(row.get('name'),str)} if isinstance(rows,list) else {}


def verified(data,match,check_date=True):
    competition=(data.get('header',{}).get('competitions') or [{}])[0]
    if str(competition.get('id',''))!=str(match['id']):raise ValueError('event_mismatch')
    info=fixture_info(data)
    if (info['home_id'],info['away_id'])!=(str(match['home']['id']),str(match['away']['id'])):raise ValueError('team_mismatch')
    if check_date and info['date']!=instant(match['date']):raise ValueError('kickoff_changed')
    return info


def form(data,team_id,now,window_days=90):
    games=[]
    for block in data.get('lastFiveGames') or []:
        if str(block.get('team',{}).get('id'))!=team_id:continue
        for game in block.get('events') or []:
            try:
                home,away=str(game['homeTeamId']),str(game['awayTeamId'])
                age=(now-instant(game['gameDate'])).total_seconds()
                hg,ag=number(game.get('homeTeamScore')),number(game.get('awayTeamScore'))
                if team_id not in (home,away) or not 3*3600<=age<=window_days*86400 or game.get('gameResult') not in ('W','L','D'):continue
                if hg is None or ag is None or not hg.is_integer() or not ag.is_integer():continue
                games.append(dict(id=str(game['id']),date=game['gameDate'],scored=int(hg if home==team_id else ag),conceded=int(ag if home==team_id else hg),home_id=home,away_id=away))
            except (KeyError,ValueError,TypeError,AttributeError):continue
    games=list({g['id']:g for g in games}.values())
    games.sort(key=lambda g:instant(g['date']),reverse=True)
    return games[:5]


def roster(data,team_id):
    return next((r.get('roster') or [] for r in data.get('rosters') or [] if str(r.get('team',{}).get('id'))==team_id),[])


def availability(data,team_id,pid):
    for block in data.get('injuries') or []:
        if str(block.get('team',{}).get('id'))!=team_id:continue
        for row in block.get('injuries') or []:
            if str(row.get('athlete',{}).get('id'))==pid and str(row.get('status','')).lower() in ('out','injured','suspended','suspension','doubtful','questionable','day-to-day'):
                return 'unavailable'
    rows=roster(data,team_id)
    player=next((r for r in rows if str(r.get('athlete',{}).get('id'))==pid),None)
    if player:
        if player.get('active') is False:return 'unavailable'
        if player.get('starter') is True:return 'reported_starter'
        if player.get('starter') is False:return 'bench'
    if rows:return 'not_listed'
    return 'unconfirmed'


def domestic_evidence(server, data, match, team_ids, now):
    """Supplement short cup leader lists with current, identity-checked domestic stats."""
    enriched=copy.deepcopy(data);failures=0
    female=match['league'] in WOMENS_LEAGUES
    allowed=set(getattr(server,'LEAGUES',()))
    for team_id in team_ids:
        try:
            info=server.fetch(f"{server.ESPN}/{match['league']}/teams/{team_id}",ttl=3600).get('team') or {}
            league=info.get('defaultLeague') or {};code=league.get('slug')
            if str(info.get('id'))!=str(team_id) or code not in allowed or (code in WOMENS_LEAGUES)!=female:continue
            source=server.fetch(f"{server.ESPN}/{code}/teams/{team_id}/roster",ttl=300)
            season=source.get('season') or {}
            if str((source.get('team') or {}).get('id'))!=str(team_id) or season.get('year') not in (now.year,now.year-1):continue
            leaders=[]
            for athlete in source.get('athletes') or []:
                if not isinstance(athlete,dict):continue
                home=athlete.get('defaultTeam') or {}
                if home.get('id') is not None and str(home['id'])!=str(team_id):continue
                if athlete.get('gender') and str(athlete['gender']).upper()!=('FEMALE' if female else 'MALE'):continue
                categories=((athlete.get('statistics') or {}).get('splits') or {}).get('categories') or []
                values=[stat for category in categories if isinstance(category,dict) for stat in category.get('stats') or []]
                leaders.append(dict(athlete=athlete,statistics=values))
            enriched.setdefault('leaders',[]).append(dict(team={'id':str(team_id)},
                statistics_competition=code,statistics_label=league.get('name') or code,statistics_season=season,
                leaders=[dict(name='goalsLeaders',leaders=leaders)]))
        except Exception:
            failures+=1
    return enriched,failures


def supplement_form(server, data, match, now):
    history = getattr(server, 'expanded_history', None)
    if not history: return data
    window = 540 if national_group(match['league']) else 90
    enriched = copy.deepcopy(data)
    for side in ('home', 'away'):
        team_id = str(match[side]['id'])
        if len(form(enriched, team_id, now, window)) >= 3: continue
        try:
            games, _ = history(match['league'], team_id, limit=10, regulation_only=True)
            rows = []
            for game in games:
                home, away = str(game['home_id']), str(game['away_id'])
                hg, ag = game['home_goals'], game['away_goals']
                if team_id not in (home, away): continue
                own, other = (hg, ag) if home == team_id else (ag, hg)
                rows.append(dict(id=game['id'], gameDate=game['date'], homeTeamId=home,
                    awayTeamId=away, homeTeamScore=hg, awayTeamScore=ag,
                    gameResult='W' if own > other else 'L' if own < other else 'D'))
            enriched.setdefault('lastFiveGames', []).append(dict(team={'id':team_id}, events=rows))
        except Exception:
            continue
    return enriched


def candidates(data,match,now,allow_live=False):
    info=verified(data,match)
    live = allow_live and info['state'] == 'in'
    if (not live and (info['state']!='pre' or info['date']<=now)) or info['completed'] or any(s in info['name'] for s in ('POSTPON','CANCEL','ABANDON','SUSPEND')):return []
    output=[]
    for side,other in [('home','away'),('away','home')]:
        team,opponent=match[side],match[other];team_id=str(team['id'])
        window=540 if national_group(match['league']) else 90
        own_games,other_games=form(data,team_id,now,window),form(data,str(opponent['id']),now,window)
        if min(len(own_games),len(other_games))<3:continue
        own_avg=sum(g['scored'] for g in own_games)/len(own_games)
        conceded=sum(g['conceded'] for g in other_games)
        opponent_avg=conceded/len(other_games)
        for block in data.get('leaders') or []:
            if str(block.get('team',{}).get('id'))!=team_id:continue
            for category in block.get('leaders') or []:
                if category.get('name')!='goalsLeaders':continue
                for lead in category.get('leaders') or []:
                    athlete=lead.get('athlete') or {};pid=str(athlete.get('id',''));name=athlete.get('displayName')
                    observed=stats(lead.get('statistics'));goals,apps=observed.get('totalGoals'),observed.get('appearances')
                    if not pid.isdigit() or not isinstance(name,str) or not name.strip():continue
                    if goals is None or apps is None or apps<5 or goals<2 or not goals.is_integer() or not apps.is_integer() or goals>apps*6:continue
                    player_status=athlete.get('status') or {}
                    state=str(player_status.get('type','active')).lower()
                    labels={str(player_status.get(k,'')).lower() for k in ('type','name','abbreviation')}
                    if state not in ('active','') or labels & {'inactive','out','injured','suspended','doubtful','questionable'}:continue
                    ready=availability(data,team_id,pid)
                    if live:
                        row=next((r for r in roster(data,team_id) if str(r.get('athlete',{}).get('id'))==pid),None)
                        if row and (row.get('subbedOut') is True or row.get('sentOff') is True or (stats(row.get('stats')).get('redCards') or 0)>0):continue
                        if row and row.get('subbedIn') is True:ready='reported_starter'
                    if ready not in ('reported_starter','unconfirmed'):continue
                    # Shrink small samples; temper by observed attack and opposing defence.
                    context=max(.65,min(1.6,(own_avg+opponent_avg)/2/1.4))
                    ranking=(goals+1)/(apps+5)*context*(1 if ready=='reported_starter' else .85)
                    lineup='Titulaire indiqué par la source.' if ready=='reported_starter' else 'La titularisation reste à confirmer.'
                    source_label=block.get('statistics_label') or 'cette compétition'
                    rationale=(f"Je choisis {name} : {int(goals)} buts en {int(apps)} apparitions dans les statistiques de {source_label}. "
                        f"{team['name']} a marqué {sum(g['scored'] for g in own_games)} buts sur ses {len(own_games)} derniers matchs exploitables, "
                        f"et {opponent['name']} en a encaissé {conceded} sur {len(other_games)}. "
                        f"{lineup} Je privilégie son rendement individuel, ajusté au contexte offensif de cette rencontre. "
                        "Le temps de jeu futur et le rôle sur penalties restent à confirmer : une rotation ou une défense plus efficace peut faire échouer ce choix.")
                    output.append(dict(player=dict(id=pid,name=name,team_id=team_id,team_name=team['name'],competition_category='women' if match['league'] in WOMENS_LEAGUES else 'men'),
                        match=copy.deepcopy(match),market='anytime_scorer',market_label='Marque au moins un but',
                        availability=ready,status='pending',home_score=None,away_score=None,
                        rationale=rationale,ranking=round(ranking,6),model_version=MODEL,
                        basis=dict(goals=int(goals),appearances=int(apps),team_form=own_games,opponent_form=other_games,
                            season=block.get('statistics_season') or (data.get('header') or {}).get('season'),
                            statistics_competition=block.get('statistics_competition') or match['league'],observed_at=now.isoformat()),
                        source_url='https://www.espn.com/soccer/match/_/gameId/'+str(match['id'])))
    return output


def recent_player_match(data, game, team_id, player_id, now):
    """Accept only completed, matching fixtures and explicit player match stats."""
    competition=(data.get('header',{}).get('competitions') or [{}])[0]
    info=fixture_info(data)
    if str(competition.get('id',''))!=str(game['id']):return None
    if (info['home_id'],info['away_id'])!=(game.get('home_id'),game.get('away_id')):return None
    if not info['completed'] or info['state']!='post' or not 3*3600<=(now-info['date']).total_seconds()<=90*86400:return None
    if (info['period'] is not None and int(info['period'])>2) or any(s in info['name'] for s in ('PENALT','EXTRA','ABANDON','CANCEL')):return None
    player=next((r for r in roster(data,team_id) if str(r.get('athlete',{}).get('id'))==player_id),None)
    if not player:return None
    values=stats(player.get('stats'));apps=values.get('appearances');goals=values.get('totalGoals')
    if apps not in (0,1) or goals is None or not goals.is_integer() or goals>6:return None
    if apps==0 and goals!=0:return None
    minutes=values.get('minutesPlayed')
    if minutes is not None and (minutes>100 or (apps==0 and minutes!=0)):minutes=None
    shots=values.get('shotsOnTarget')
    if shots is not None and (not shots.is_integer() or shots>30):shots=None
    penalties=values.get('penaltyGoals')
    if penalties is not None and (not penalties.is_integer() or penalties>goals):penalties=None
    return dict(event_id=str(game['id']),date=info['date'].isoformat(),appearances=int(apps),goals=int(goals),
                starter=player.get('starter') if isinstance(player.get('starter'),bool) else None,
                minutes=minutes,shots_on_target=shots,penalty_goals=penalties,
                source_url='https://www.espn.com/soccer/match/_/gameId/'+str(game['id']))


def apply_recent(pick, records, now):
    basis=pick['basis'];basis['recent_player_matches']=records
    basis['recent_observed_at']=now.isoformat()
    basis['penalty_role']='unconfirmed'
    if len(records)<3:
        pick['rationale']+=' Forme individuelle récente insuffisamment documentée ; aucun ajustement sur des statistiques manquantes.'
        return
    apps=sum(r['appearances'] for r in records);goals=sum(r['goals'] for r in records)
    season_rate=(basis['goals']+1)/(basis['appearances']+5)
    recent_rate=(goals+season_rate*5)/(apps+5)
    factor=max(.8,min(1.2,recent_rate/season_rate))
    starts=[r for r in records if r['starter'] is not None]
    if len(starts)>=3:factor*=.75+.25*sum(r['starter'] for r in starts)/len(starts)
    minutes=[r['minutes'] for r in records if r['minutes'] is not None]
    if len(minutes)>=3:factor*=max(.65,min(1.05,sum(minutes)/len(minutes)/75))
    pick['ranking']=round(pick['ranking']*factor,6)
    detail=f" Sur {len(records)} matchs récents vérifiés : {goals} but(s), {apps} apparition(s)"
    if len(starts)>=3:detail+=f", {sum(r['starter'] for r in starts)} titularisation(s)"
    if len(minutes)>=3:detail+=f", {round(sum(minutes)/len(minutes))} minutes jouées en moyenne"
    else:detail+=", minutes non documentées"
    shots=[r['shots_on_target'] for r in records if r['shots_on_target'] is not None]
    if len(shots)==len(records):detail+=f", {int(sum(shots))} tir(s) cadré(s)"
    penalties=[r['penalty_goals'] for r in records if r['penalty_goals'] is not None]
    if len(penalties)==len(records):detail+=f", {int(sum(penalties))} penalty(s) marqué(s)"
    pick['rationale']+=detail+'. Le tireur de penalty désigné pour le prochain match reste non confirmé. Ces observations ne garantissent pas son temps de jeu futur.'


def enrich_recent(server, pool, now):
    # Bound additional work and share each historical summary between candidates.
    selected=pool[:12];jobs={}
    for pick in selected:
        for game in pick['basis']['team_form'][:3]:jobs[(pick['match']['league'],game['id'])]=game
    summaries={}
    def load(key):return server.fetch(f"{server.ESPN}/{key[0]}/summary",{'event':key[1]},ttl=1800)
    with ThreadPoolExecutor(max_workers=4) as executor:
        pending={executor.submit(load,key):key for key in jobs}
        for future in as_completed(pending):
            try:summaries[pending[future]]=future.result()
            except Exception:pass
    for pick in selected:
        records=[]
        for game in pick['basis']['team_form'][:3]:
            try:
                record=recent_player_match(summaries.get((pick['match']['league'],game['id']),{}),game,pick['player']['team_id'],pick['player']['id'],now)
                if record:records.append(record)
            except (KeyError,ValueError,TypeError,AttributeError):pass
        apply_recent(pick,records,now)
    return selected


def select(server,matches,now,day):
    from daily_opinion import upcoming
    eligible=sorted((m for m in matches if upcoming(m,now,day)),key=lambda m:(m['date'],str(m['id'])))
    eligible=representative_fixtures(eligible,MAX_FIXTURES)
    def load(match):
        data=server.fetch(f"{server.ESPN}/{match['league']}/summary",{'event':match['id']},ttl=300)
        data=supplement_form(server,data,match,now)
        picks=candidates(data,match,now)
        represented={p['player']['team_id'] for p in picks}
        missing=[str(match[side]['id']) for side in ('home','away') if str(match[side]['id']) not in represented]
        failures=0
        if missing:
            data,failures=domestic_evidence(server,data,match,missing,now)
            picks=candidates(data,match,now)
        return picks,failures
    pool=[];errors=0
    with ThreadPoolExecutor(max_workers=4) as executor:
        jobs=[executor.submit(load,m) for m in eligible]
        for job in as_completed(jobs):
            try:
                picks,failures=job.result();pool.extend(picks);errors+=failures
            except Exception:errors+=1
    # Real time is checked again by the caller before persisting the choice.
    pool.sort(key=lambda p:(-p['ranking'],p['match']['date'],str(p['match']['id']),p['player']['id']))
    pool=enrich_recent(server,pool,now)
    pool.sort(key=lambda p:(-p['ranking'],p['match']['date'],str(p['match']['id']),p['player']['id']))
    return pool,dict(fixtures_examined=len(eligible),source_errors=errors)


def settle(server,pick,now):
    """Only explicit per-match player goals/appearances can settle a scorer."""
    if not pick or pick.get('status')!='pending':return
    match=pick['match'];data=server.fetch(f"{server.ESPN}/{match['league']}/summary",{'event':match['id']},ttl=120)
    info=verified(data,match,check_date=False)
    if info['date']!=instant(match['date']):
        pick.update(status='void',settlement_reason='fixture_rescheduled');return
    if any(s in info['name'] for s in ('POSTPON','CANCEL','ABANDON')):
        pick.update(status='void',settlement_reason='fixture_cancelled');return
    if info['state']=='pre' and info['date']>now:
        pick['availability']=availability(data,pick['player']['team_id'],pick['player']['id']);return
    if not info['completed'] or info['state']!='post':return
    if (info['period'] is not None and int(info['period'])>2) or any(s in info['name'] for s in ('EXTRA_TIME','PENALT','FINAL_AET','AFTER_EXTRA')):
        pick.update(status='void',settlement_reason='extra_time_not_supported');return
    player=next((r for r in roster(data,pick['player']['team_id']) if str(r.get('athlete',{}).get('id'))==pick['player']['id']),None)
    if not player:return
    values=stats(player.get('stats'));goals,apps=values.get('totalGoals'),values.get('appearances')
    if apps==0 and goals in (None,0):pick.update(status='void',settlement_reason='did_not_play');return
    if apps!=1 or goals is None or not goals.is_integer():return
    pick.update(status='won' if goals>0 else 'lost',goals_scored=int(goals),settled_at=now.isoformat())


def roster_alternatives(server, data, match, team_id, now):
    """Rank real squad members when season totals or team form are missing."""
    rows = list(roster(data, team_id))
    if not rows:
        for block in data.get('leaders') or []:
            if str((block.get('team') or {}).get('id')) != team_id: continue
            for category in block.get('leaders') or []:
                if category.get('name') == 'goalsLeaders':
                    rows.extend(dict(athlete=lead.get('athlete') or {}) for lead in category.get('leaders') or [])
    def eligible(row):
        athlete = row.get('athlete') or {}
        pid = str(athlete.get('id', ''))
        name = athlete.get('displayName') or athlete.get('fullName')
        position = row.get('position') or athlete.get('position') or {}
        role = str(position.get('abbreviation') or position.get('name') or '').upper()
        values = stats(row.get('stats'))
        if not pid.isdigit() or not isinstance(name, str) or not name.strip(): return None
        if role in ('GK', 'G', 'GOALKEEPER') or row.get('active') is False: return None
        if row.get('subbedOut') is True or row.get('sentOff') is True or (values.get('redCards') or 0)>0: return None
        if availability(data, team_id, pid) == 'unavailable': return None
        state = athlete.get('status') or {}
        if str(state.get('type','active')).lower() in ('inactive','out','injured','suspended','doubtful','questionable'): return None
        offensive = role in ('F','FW','ST','CF','LW','RW','FORWARD','STRIKER')
        midfield = role in ('M','MF','AM','CM','LM','RM','DM','AMF','MIDFIELDER')
        goals = None
        for block in data.get('leaders') or []:
            if str((block.get('team') or {}).get('id')) != team_id: continue
            for category in block.get('leaders') or []:
                if category.get('name') != 'goalsLeaders': continue
                for lead in category.get('leaders') or []:
                    if str((lead.get('athlete') or {}).get('id')) == pid:
                        observed = stats(lead.get('statistics'))
                        if observed.get('totalGoals') is not None: goals = observed['totalGoals']
        playing = row.get('starter') is True or row.get('subbedIn') is True
        bench = row.get('starter') is False and row.get('subbedIn') is not True
        # Prefer the actual lineup, then offensive role and observed scoring output.
        score = (100 if playing else -100 if bench else 0) + (30 if offensive else 15 if midfield else 0) + min(goals or 0,25)
        reason = ('Profil offensif' if offensive else 'Profil de milieu' if midfield else 'Choix dans l’effectif disponible')
        reason += (' ; '+str(int(goals))+' buts recensés' if goals is not None else ' ; statistiques de buts incomplètes')
        reason += '. '+('Entrée en jeu nécessaire.' if bench else 'Temps de jeu restant à vérifier.' if match.get('live') else 'Titularisation à confirmer.' if not playing else 'Titulaire annoncé.')
        return dict(player=dict(id=pid,name=name.strip(),team_id=team_id), rationale=reason,
            availability='bench' if bench else 'reported_starter' if playing else 'unconfirmed',
            basis={'selection_method':'squad_role','position':role,'goals':goals}, _score=score)
    # Fetch the team's actual squad only when the fixture roster cannot fill two slots.
    if sum(eligible(row) is not None for row in rows) < 2:
        try:
            squad = server.fetch(f"{server.ESPN}/{match['league']}/teams/{team_id}/roster", ttl=300)
            if str((squad.get('team') or {}).get('id')) == team_id:
                season = squad.get('season') or {}
                if not season.get('year') or season['year'] in (now.year, now.year-1):
                    for athlete in squad.get('athletes') or []:
                        for member in athlete.get('items', [athlete]):
                            # A published match lineup takes precedence over the general squad.
                            if not any(str((r.get('athlete') or {}).get('id')) == str(member.get('id')) for r in rows):
                                rows.append(dict(athlete=member))
        except Exception:
            pass
    choices = [choice for row in rows if (choice := eligible(row)) is not None]
    choices.sort(key=lambda p:(-p['_score'],p['player']['id']))
    for choice in choices: choice.pop('_score')
    return choices


def match_choices(server, analysis, histories=None, now=None):
    """Two distinct, eligible scorers per team for a single upcoming fixture."""
    now = now or datetime.now(timezone.utc)
    output = {'teams': [], 'observed_at': now.isoformat(), 'model_version': MODEL, 'live_supported': True, 'selection_version': 2}
    for side in ('home', 'away'):
        output['teams'].append(dict(team_id=str(analysis.get(side+'_id', '')),
            team_name=analysis.get(side+'_name') or side, choices=[]))
    event_id = str(analysis.get('event_id', ''))
    if not event_id.isdigit():
        output['status'] = 'unavailable'
        return output
    try:
        data = server.fetch(f"{server.ESPN}/{analysis['league']}/summary", {'event': event_id}, ttl=300)
        info = fixture_info(data)
        match = dict(id=event_id, league=analysis['league'], date=info['date'].isoformat(),
            home=dict(id=analysis['home_id'], name=analysis['home_name']),
            away=dict(id=analysis['away_id'], name=analysis['away_name']))
        verified(data, match)
        for side,team in zip(('home','away'),output['teams']):
            name=info[side].get('team',{}).get('displayName')
            if name:team['team_name']=name;match[side]['name']=name
        if info['state'] not in ('pre', 'in') or info['completed'] or (info['state'] == 'pre' and info['date'] <= now):
            output['status'] = 'closed'
            return output
        output['live'] = info['state'] == 'in'
        data = copy.deepcopy(data)
        # Reuse the histories already fetched by the analysis, without more requests.
        for side in ('home', 'away'):
            team_id = str(analysis[side+'_id'])
            rows = []
            for game in (histories or {}).get(side, []):
                home, away = str(game['home_id']), str(game['away_id'])
                if team_id not in (home, away): continue
                hg, ag = game['home_goals'], game['away_goals']
                own, other = (hg, ag) if team_id == home else (ag, hg)
                rows.append(dict(id=game['id'], gameDate=game['date'], homeTeamId=home,
                    awayTeamId=away, homeTeamScore=hg, awayTeamScore=ag,
                    gameResult='W' if own > other else 'L' if own < other else 'D'))
            if rows: data.setdefault('lastFiveGames', []).append(dict(team={'id': team_id}, events=rows))
        pool = candidates(data, match, now, allow_live=True)
        missing = [t['team_id'] for t in output['teams']
            if len({p['player']['id'] for p in pool if p['player']['team_id'] == t['team_id']}) < 2]
        if missing:
            data, _ = domestic_evidence(server, data, match, missing, now)
            pool = candidates(data, match, now, allow_live=True)
        pool.sort(key=lambda p: (-p['ranking'], p['player']['id']))
        for team in output['teams']:
            seen = set()
            for pick in pool:
                player = pick['player']
                if player['team_id'] != team['team_id'] or player['id'] in seen: continue
                seen.add(player['id'])
                basis = pick['basis']
                team['choices'].append(dict(rank=len(team['choices'])+1, ranking=pick['ranking'], player=player,
                    rationale=f"{basis['goals']} buts en {basis['appearances']} apparitions. "
                        + (('Match en cours : temps de jeu restant à vérifier.') if output['live'] else ('Titulaire annoncé.' if pick['availability'] == 'reported_starter' else 'Titularisation à confirmer.')),
                    availability=pick['availability'], basis=basis))
                if len(team['choices']) == 2: break
        match['live'] = output['live']
        for team in output['teams']:
            if len(team['choices']) >= 2: continue
            seen = {p['player']['id'] for p in team['choices']}
            for choice in roster_alternatives(server, data, match, team['team_id'], now):
                if choice['player']['id'] in seen: continue
                if choice['player']['name'].casefold() == team['team_name'].casefold(): continue
                seen.add(choice['player']['id'])
                choice['player']['team_name'] = team['team_name']
                choice['rank'] = len(team['choices'])+1
                team['choices'].append(choice)
                if len(team['choices']) == 2: break
        output['status'] = 'ok' if all(len(t['choices']) == 2 for t in output['teams']) else 'partial'
    except Exception:
        output['status'] = 'unavailable'
    return output
