import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
import app
from competitions import LEAGUES, WOMENS_LEAGUES, national_group

class NationalCompetitionsTests(unittest.TestCase):
    def test_catalog_includes_nations_and_womens_competitions(self):
        for code in ('uefa.nations','uefa.w.nations','fifa.world','caf.nations','conmebol.america','afc.asian.cup','concacaf.nations.league'):
            self.assertIn(code, LEAGUES)
        self.assertIn('uefa.w.nations', WOMENS_LEAGUES)
        self.assertNotIn('chn.1', WOMENS_LEAGUES)
        self.assertNotIn('ind.1', WOMENS_LEAGUES)
        self.assertNotIn('fifa.world', national_group('fifa.wwc'))
        self.assertFalse(national_group('eng.1'))

    def test_nations_calendar_and_search(self):
        def source(url,*args,**kw):
            if '/uefa.nations/teams' in url:
                return {'sports':[{'leagues':[{'teams':[{'team':{'id':'478','displayName':'France'}}]}]}]}
            return {'sports':[]}
        with patch.object(app,'fetch',side_effect=source):
            result=app.app.test_client().get('/api/search-teams?q=france')
        self.assertEqual(result.json['teams'][0]['league'],'uefa.nations')
        with patch.object(app,'fetch',return_value={'events':[]}):
            self.assertEqual(app.app.test_client().get('/api/fixtures?league=uefa.nations').status_code,200)

    def test_national_history_uses_other_senior_international_competitions(self):
        date=(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()
        game=dict(id='99',date=date,home_id='478',away_id='477',home_goals=2,away_goals=1)
        def history(code,*a,**kw):return ([game] if code=='fifa.friendly' else []),[]
        member={'sports':[{'leagues':[{'teams':[{'team':{'id':'478'}}]}]}]}
        with patch.object(app,'history',side_effect=history) as h, patch.object(app,'fetch',return_value=member):
            games,errors=app.expanded_history('uefa.nations','478')
        self.assertEqual(games[0]['competition'],'fifa.friendly')
        self.assertTrue(all(call.args[0] not in WOMENS_LEAGUES for call in h.call_args_list))

class DailyCoverageTests(unittest.TestCase):
    def test_busy_competition_does_not_hide_national_fixture(self):
        from competitions import representative_fixtures
        games=[dict(id=str(i),league='club.friendly',date='2026-11-12T10:00Z') for i in range(50)]
        games.append(dict(id='nation',league='uefa.nations',date='2026-11-12T20:00Z'))
        sampled=representative_fixtures(games,12)
        self.assertEqual(len(sampled),12)
        self.assertIn('nation',[m['id'] for m in sampled])

    def test_missing_national_form_uses_verified_schedule_without_inventing_scorers(self):
        from daily_scorer import supplement_form, form, candidates
        from types import SimpleNamespace
        now=datetime.now(timezone.utc)
        match=dict(id='1',league='uefa.nations',date=(now+timedelta(hours=5)).isoformat(),home={'id':'478'},away={'id':'477'})
        games=[dict(id=str(i),date=(now-timedelta(days=100+i)).isoformat(),home_id='478',away_id='477',home_goals=2,away_goals=1) for i in range(4)]
        server=SimpleNamespace(expanded_history=lambda *a,**kw:(games,[]))
        result=supplement_form(server,{},match,now)
        self.assertEqual(len(form(result,'478',now,540)),4)
        self.assertEqual(form(result,'478',now),[])
        self.assertNotIn('leaders',result)
