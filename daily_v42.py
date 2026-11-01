"""Daily candidate builder. No bookmaker odds, no guaranteed predictions."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from itertools import combinations
import math

MARKETS = {
    'home_or_draw': 'Double chance 1X',
    'away_or_draw': 'Double chance X2',
    'over_1_5': 'Plus de 1,5 but',
    'over_2_5': 'Plus de 2,5 buts',
    'btts': 'Les deux équipes marquent',
    'home': 'Victoire domicile',
    'away': 'Victoire extérieur',
}

def score_options(fixture, markets, quality):
    n=min(quality['home_games'],quality['away_games'])
    if n<5:return []
    options=[]
    for key,label in MARKETS.items():
        p=float(markets.get(key,0))/100
        if p<.35 or p>.94:continue
        # These are *model* probabilities, not calibrated empirical hit rates.
        options.append({'fixture_id':fixture['id'],'league':fixture['league'],
          'kickoff':fixture['date'],'match':fixture['home']['name']+' – '+fixture['away']['name'],
          'market_key':key,'market':label,'probability_pct':round(p*100,1),
          'indicative_fair_decimal':round(1/p,2),
          'data_matches_per_team':n,
          'data_quality':'moderate' if n>=10 else 'limited'})
    return options

def choose_tickets(fixtures_with_markets,day):
    # One selection per match and distinct fixtures across legs; deterministic daily output.
    all_options=[]
    for fixture,markets,quality in fixtures_with_markets:
        all_options.extend(score_options(fixture,markets,quality))
    profiles=[('Prudent',2,.72,.94),('Équilibré',3,.56,.82),('Ambitieux',4,.39,.72)]
    result=[]
    for name,legs,minp,maxp in profiles:
        filtered=[o for o in all_options if minp<=o['probability_pct']/100<=maxp]
        # Rank by closeness to target probability, plus sample-size reward.
        target={'Prudent':.79,'Équilibré':.67,'Ambitieux':.53}[name]
        filtered.sort(key=lambda o:(abs(o['probability_pct']/100-target)-min(o['data_matches_per_team'],12)*.001,o['fixture_id'],o['market_key']))
        picks=[];used=set()
        for o in filtered:
            if o['fixture_id'] not in used:
                picks.append(o);used.add(o['fixture_id'])
            if len(picks)==legs:break
        if len(picks)<legs:
            result.append({'name':name,'status':'insufficient_fixtures','required_legs':legs,'available_legs':len(picks),
              'message':'Pas assez de rencontres distinctes disposant de données suffisantes pour ce profil.'})
            continue
        joint=math.prod(o['probability_pct']/100 for o in picks)
        result.append({'name':name,'status':'ok','legs':picks,'model_joint_probability_pct':round(joint*100,1),
          'indicative_fair_decimal':round(1/joint,2),
          'warning':'Probabilité combinée approximative : indépendance supposée entre matchs, modèle non calibré. La cote indiquée est théorique, PAS une cote de bookmaker.'})
    return result
