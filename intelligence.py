"""V40: transparent statistical multi-market analysis, no bookmaker odds."""
import math
from itertools import product

def poisson(lam, k):
    return math.exp(-lam) * lam**k / math.factorial(k)

def deep_analysis(home, away, home_name='Home', away_name='Away'):
    for team in (home,away):
        if team.get('matches',0)<5 or any(not isinstance(team.get(k),(float,int)) for k in ('goals_for_avg','goals_against_avg')):
            return {'status':'insufficient_data','reason':'At least five completed games and verified goal averages per team are required.'}
    h=max(.2,min(4,(home['goals_for_avg']+away['goals_against_avg'])/2*1.07))
    a=max(.2,min(4,(away['goals_for_avg']+home['goals_against_avg'])/2*.93))
    matrix={(i,j):poisson(h,i)*poisson(a,j) for i,j in product(range(16),repeat=2)}
    total=sum(matrix.values())
    matrix={k:v/total for k,v in matrix.items()}
    conditions={
        'home_win':lambda i,j:i>j,'draw':lambda i,j:i==j,'away_win':lambda i,j:i<j,
        'double_chance_1x':lambda i,j:i>=j,'double_chance_x2':lambda i,j:i<=j,
        'over_0_5':lambda i,j:i+j>=1,'over_1_5':lambda i,j:i+j>=2,
        'over_2_5':lambda i,j:i+j>=3,'over_3_5':lambda i,j:i+j>=4,
        'under_2_5':lambda i,j:i+j<=2,'under_3_5':lambda i,j:i+j<=3,
        'btts_yes':lambda i,j:i>0 and j>0,'btts_no':lambda i,j:i==0 or j==0,
        'home_scores':lambda i,j:i>=1,'away_scores':lambda i,j:j>=1,
    }
    markets={name:round(100*sum(p for (i,j),p in matrix.items() if fn(i,j)),2) for name,fn in conditions.items()}
    scores=sorted(matrix.items(),key=lambda x:x[1],reverse=True)[:5]
    n=min(home['matches'],away['matches'])
    quality='moderate' if n>=10 else 'limited'
    return {'status':'ok','teams':{'home':home_name,'away':away_name},'expected_goals':{'home':round(h,3),'away':round(a,3)},'markets_pct':markets,
      'likely_scores':[{'score':f'{i}-{j}','probability_pct':round(100*p,2)} for (i,j),p in scores],
      'data_quality':{'level':quality,'home_matches':home['matches'],'away_matches':away['matches']},
      'method':'Independent Poisson baseline from completed-match goal averages; no bookmaker odds',
      'not_available':['xG','injuries','lineups','corners','cards','goalscorers'],
      'limitations':'Not calibrated against out-of-sample results; no player availability or opponent strength adjustment. Predictions are uncertain.'}

def build_ticket_profiles(analyses):
    """One selection per distinct match; never multiply correlated legs from the same match."""
    valid=[(a['teams']['home']+' - '+a['teams']['away'],a) for a in analyses if a.get('status')=='ok']
    profiles=[]
    for name,min_p,max_legs in [('conservative',75,3),('balanced',60,4),('speculative',45,6)]:
        candidates=[]
        for match,a in valid:
            options=[(k,v) for k,v in a['markets_pct'].items() if k in ('double_chance_1x','double_chance_x2','over_1_5','over_2_5','under_3_5','btts_yes') and v>=min_p]
            if options:
                k,p=max(options,key=lambda x:x[1])
                candidates.append({'match':match,'market':k,'probability_pct':p})
        candidates.sort(key=lambda x:x['probability_pct'],reverse=True)
        legs=candidates[:max_legs]
        profiles.append({'profile':name,'legs':legs,'indicative_joint_probability_pct':round(math.prod(l['probability_pct']/100 for l in legs)*100,2) if legs else None,'note':'Joint estimate assumes independence between distinct matches; shared competition/team factors can invalidate it.'})
    return profiles
