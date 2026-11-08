"""One frozen daily scorer, selected from observed ESPN player and fixture data.

The ranking is an uncalibrated comparison, not a scoring probability. Match
results use player match statistics, never the team score or season totals.
"""
import copy
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from tracking import fixture_info

MODEL = 'scorer-season-form-v1'
MAX_FIXTURES = 12


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


def form(data,team_id,now):
    games=[]
    for block in data.get('lastFiveGames') or []:
        if str(block.get('team',{}).get('id'))!=team_id:continue
        for game in block.get('events') or []:
            try:
                home,away=str(game['homeTeamId']),str(game['awayTeamId'])
                age=(now-instant(game['gameDate'])).total_seconds()
                hg,ag=number(game.get('homeTeamScore')),number(game.get('awayTeamScore'))
                if team_id not in (home,away) or not 3*3600<=age<=90*86400 or game.get('gameResult') not in ('W','L','D'):continue
                if hg is None or ag is None or not hg.is_integer() or not ag.is_integer():continue
                games.append(dict(id=str(game['id']),date=game['gameDate'],scored=int(hg if home==team_id else ag),conceded=int(ag if home==team_id else hg)))
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


def candidates(data,match,now):
    info=verified(data,match)
    if info['state']!='pre' or info['completed'] or info['date']<=now or any(s in info['name'] for s in ('POSTPON','CANCEL','ABANDON','SUSPEND')):return []
    output=[]
    for side,other in [('home','away'),('away','home')]:
        team,opponent=match[side],match[other];team_id=str(team['id'])
        own_games,other_games=form(data,team_id,now),form(data,str(opponent['id']),now)
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
                    if ready not in ('reported_starter','unconfirmed'):continue
                    # Shrink small samples; temper by observed attack and opposing defence.
                    context=max(.65,min(1.6,(own_avg+opponent_avg)/2/1.4))
                    ranking=(goals+1)/(apps+5)*context*(1 if ready=='reported_starter' else .85)
                    lineup='Il est indiqué titulaire par la source.' if ready=='reported_starter' else 'Sa titularisation reste à confirmer.'
                    rationale=(f"Je choisis {name} : {int(goals)} buts en {int(apps)} apparitions dans les statistiques de cette compétition. "
                        f"{team['name']} a marqué {sum(g['scored'] for g in own_games)} buts sur ses {len(own_games)} derniers matchs exploitables, "
                        f"et {opponent['name']} en a encaissé {conceded} sur {len(other_games)}. "
                        f"{lineup} Je privilégie son rendement individuel, ajusté au contexte offensif de cette rencontre. "
                        "Ces chiffres ne mesurent pas ses minutes attendues ni son rôle sur penalties : un temps de jeu réduit ou une défense plus efficace peut faire échouer ce choix.")
                    output.append(dict(player=dict(id=pid,name=name,team_id=team_id,team_name=team['name']),
                        match=copy.deepcopy(match),market='anytime_scorer',market_label='Marque au moins un but',
                        availability=ready,status='pending',home_score=None,away_score=None,
                        rationale=rationale,ranking=round(ranking,6),model_version=MODEL,
                        basis=dict(goals=int(goals),appearances=int(apps),team_form=own_games,opponent_form=other_games,
                            season=(data.get('header') or {}).get('season'),observed_at=now.isoformat()),
                        source_url='https://www.espn.com/soccer/match/_/gameId/'+str(match['id'])))
    return output


def select(server,matches,now,day):
    from daily_opinion import upcoming
    eligible=sorted((m for m in matches if upcoming(m,now,day)),key=lambda m:(m['date'],str(m['id'])))
    if len(eligible)>MAX_FIXTURES:eligible=[eligible[round(i*(len(eligible)-1)/(MAX_FIXTURES-1))] for i in range(MAX_FIXTURES)]
    def load(match):
        data=server.fetch(f"{server.ESPN}/{match['league']}/summary",{'event':match['id']},ttl=300)
        return candidates(data,match,now)
    pool=[];errors=0
    with ThreadPoolExecutor(max_workers=4) as executor:
        jobs=[executor.submit(load,m) for m in eligible]
        for job in as_completed(jobs):
            try:pool.extend(job.result())
            except Exception:errors+=1
    # Real time is checked again by the caller before persisting the choice.
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
