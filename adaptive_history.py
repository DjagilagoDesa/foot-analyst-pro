"""Bounded, explicit multi-competition evidence; no invented missing results."""
from collections import Counter
from datetime import datetime, timezone

MODEL_VERSION = 'poisson-adaptive-20-v1'
MIN_SAMPLE = 3
MAX_SAMPLE = 20
WINDOW_DAYS = 540


def combine(team_id, batches, now=None):
    now = now or datetime.now(timezone.utc)
    found = {}
    for league, games in batches:
        for game in games:
            try:
                date = datetime.fromisoformat(game['date'].replace('Z', '+00:00'))
                age = (now-date).total_seconds()
                if date.tzinfo is None or not 3*3600 <= age <= WINDOW_DAYS*86400: continue
                if str(team_id) not in (str(game['home_id']), str(game['away_id'])): continue
                if not game.get('id'): continue
                if any(isinstance(game[k],bool) or not isinstance(game[k],int) or game[k]<0 for k in ('home_goals','away_goals')): continue
                found.setdefault(str(game['id']), dict(game, competition=league))
            except (KeyError, ValueError, TypeError, AttributeError):
                continue
    games = sorted(found.values(),key=lambda g:datetime.fromisoformat(g['date'].replace('Z','+00:00')),reverse=True)[:MAX_SAMPLE]
    competitions = dict(Counter(g['competition'] for g in games))
    return games, dict(sample=len(games), competitions=competitions,
                       mixed_competitions=len(competitions)>1,
                       evidence='very_limited' if len(games)<5 else 'limited' if len(games)<10 else 'descriptive',
                       oldest=games[-1]['date'] if games else None,
                       newest=games[0]['date'] if games else None)
