"""FOOT ANALYST PRO V35 — statistical engine; no bookmaker odds."""
import math

def poisson(lam, k):
    return math.exp(-lam) * lam**k / math.factorial(k)

def analyse(data):
    required = ['home','away','home_scored_avg','home_conceded_avg','away_scored_avg','away_conceded_avg']
    missing = [k for k in required if k not in data]
    if missing:
        return {'error':'missing_fields','fields':missing}
    for k in required[2:]:
        if not isinstance(data[k], (int,float)) or isinstance(data[k],bool) or not 0 <= data[k] <= 10:
            return {'error':'invalid_stat','field':k}
    h = max(0.05, min(6, (data['home_scored_avg']+data['away_conceded_avg'])/2 * 1.08))
    a = max(0.05, min(6, (data['away_scored_avg']+data['home_conceded_avg'])/2 * 0.94))
    hp = [poisson(h,i) for i in range(13)]
    ap = [poisson(a,i) for i in range(13)]
    p1 = sum(hp[i]*ap[j] for i in range(13) for j in range(13) if i>j)
    px = sum(hp[i]*ap[i] for i in range(13))
    p2 = 1-p1-px
    over15 = 1-math.exp(-(h+a))*(1+h+a)
    over25 = 1-math.exp(-(h+a))*(1+h+a+(h+a)**2/2)
    btts = (1-math.exp(-h))*(1-math.exp(-a))
    best = sorted(((i,j,hp[i]*ap[j]) for i in range(8) for j in range(8)),key=lambda x:x[2],reverse=True)[:3]
    probs = {'home_win':p1,'draw':px,'away_win':p2,'over_1_5':over15,'over_2_5':over25,'both_score':btts,'home_or_draw':p1+px,'away_or_draw':p2+px}
    sample = data.get('sample_matches_per_team')
    quality = 'unknown' if not isinstance(sample,int) else ('low' if sample<5 else 'medium' if sample<10 else 'moderate')
    return {'match':f"{data['home']} - {data['away']}",'expected_goals':{'home':round(h,2),'away':round(a,2)},'probabilities':{k:round(v*100,1) for k,v in probs.items()},'likely_scores':[{'score':f'{i}-{j}','probability_pct':round(p*100,1)} for i,j,p in best],'data_quality':quality,'method':'Independent Poisson approximation; no bookmaker odds','warning':'Estimates, not guarantees. Not adjusted for injuries, lineups or schedule. Use recent, verified statistics.'}
