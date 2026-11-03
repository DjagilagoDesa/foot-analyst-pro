import copy
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from match_availability import collect, refresh_cached, section

NOW = datetime(2026,11,2,12,tzinfo=timezone.utc)


def payload():
    return dict(header=dict(id='123',competitions=[dict(date=(NOW+timedelta(hours=8)).isoformat(),
        status=dict(type=dict(state='pre',completed=False,name='STATUS_SCHEDULED')),
        competitors=[dict(homeAway='home',team=dict(id='1')),dict(homeAway='away',team=dict(id='2'))])]),
        rosters=[dict(team=dict(id='1'), roster=[dict(starter=True,athlete=dict(id=str(i),displayName='Joueur '+str(i)),position=dict(abbreviation='M')) for i in range(1,12)]),
                 dict(team=dict(id='2'), roster=[dict(starter=False,athlete=dict(id='99',displayName='Remplaçant'))])],
        injuries=[dict(team=dict(id='1'),injuries=[dict(athlete=dict(id='50',displayName='Gardien',position=dict(abbreviation='GK')),status='Out',date=NOW.isoformat()),
                  dict(athlete=dict(id='51',displayName='Défenseur'),status='Doubtful',date=NOW.isoformat()),
                  dict(athlete=dict(id='52',displayName='Milieu'),status='Suspended',date=NOW.isoformat())])])


class PersonnelTests(unittest.TestCase):
    def source(self, data=None):
        return SimpleNamespace(ESPN='https://source',fetch=Mock(return_value=payload() if data is None else data))

    def test_listed_starters_are_not_official_and_substitutes_not_injured(self):
        context=collect(self.source(),'uefa.champions','1','2','123',now=NOW)
        self.assertTrue(context['fixture_verified'])
        self.assertEqual(context['teams']['1']['lineup_status'],'reported')
        self.assertFalse(context['teams']['1']['officially_verified'])
        self.assertEqual(len(context['teams']['1']['starters']),11)
        self.assertEqual(context['teams']['2']['availability'],[])
        self.assertEqual(context['teams']['2']['lineup_status'],'unavailable')
        states=[r['status'] for r in context['teams']['1']['availability']]
        self.assertEqual(states,['reported_out','doubtful','suspension_unverified_scope'])

    def test_undated_old_future_unknown_and_foreign_team_reports_excluded(self):
        data=payload();injury=data['injuries'][0]['injuries'][0]
        data['injuries'][0]['injuries']=[dict(injury,date='2026-10-01T12:00:00Z'),dict(injury,date='bad'),
              dict(injury,date=(NOW+timedelta(days=1)).isoformat()),dict(injury,status='Active')]
        data['injuries'].append(dict(team=dict(id='999'),injuries=[injury]))
        context=collect(self.source(data),'uefa.champions','1','2','123',now=NOW)
        self.assertEqual(context['teams']['1']['availability'],[])
        self.assertEqual(context['teams']['1']['discarded_reports'],4)

    def test_wrong_event_teams_live_past_and_cancelled_not_applied(self):
        for change in ('event','team','live','past','cancelled'):
            data=payload();comp=data['header']['competitions'][0]
            if change=='event': data['header']['id']='456'
            elif change=='team':comp['competitors'][0]['team']['id']='99'
            elif change=='live':comp['status']['type']['state']='in'
            elif change=='past':comp['date']=NOW.isoformat()
            else:comp['status']['type']['name']='STATUS_POSTPONED'
            context=collect(self.source(data),'uefa.champions','1','2','123',now=NOW)
            self.assertFalse(context['fixture_verified'],change)
            self.assertFalse(context['teams'])

    def test_empty_malformed_and_outage_are_not_healthy_squads(self):
        data=payload();data['rosters']=[dict(team='bad'),dict(team=dict(id='1'),roster=[dict(starter=True,athlete='bad')])];data['injuries']={}
        context=collect(self.source(data),'uefa.champions','1','2','123',now=NOW)
        self.assertEqual(context['teams']['1']['lineup_status'],'unavailable')
        server=self.source();server.fetch.side_effect=TimeoutError()
        context=collect(server,'uefa.champions','1','2','123',now=NOW)
        self.assertEqual(context['reason'],'source_unavailable')
        text=section(dict(personnel_context=context,home_id='1',away_id='2'))['text']
        self.assertIn('effectif complet non confirmé',text)

    def test_refresh_is_throttled_and_preserves_predictions_and_archives(self):
        cached=dict(league='uefa.champions',home_id='1',away_id='2',event_id='123',prediction={'home':75},report={'sections':[]})
        server=self.source()
        self.assertTrue(refresh_cached(server,cached,now=NOW))
        prediction=copy.deepcopy(cached['prediction'])
        self.assertFalse(refresh_cached(server,cached,now=NOW+timedelta(minutes=1)))
        self.assertEqual(server.fetch.call_count,1)
        self.assertTrue(refresh_cached(server,cached,now=NOW+timedelta(minutes=6)))
        self.assertEqual(len(cached['report']['sections']),1)
        frozen=copy.deepcopy(cached)
        self.assertFalse(refresh_cached(server,cached,now=NOW+timedelta(days=1)))
        self.assertEqual(cached,frozen)
        self.assertEqual(cached['prediction'],prediction)

    def test_conflicting_starter_and_absence_are_flagged(self):
        data=payload();data['injuries'][0]['injuries'][0]['athlete']['id']='1'
        context=collect(self.source(data),'uefa.champions','1','2','123',now=NOW)
        self.assertTrue(context['teams']['1']['availability'][0]['conflicts_with_lineup'])
        text=section(dict(personnel_context=context,home_id='1',away_id='2'))['text']
        self.assertIn('Signalements contradictoires pour Gardien',text)
        self.assertNotIn('Si l’absence de Gardien est confirmée',text)

    def test_source_returning_after_kickoff_does_not_update_context(self):
        from unittest.mock import patch
        data=payload();data['header']['competitions'][0]['date']=(NOW+timedelta(seconds=1)).isoformat()
        class Clock(datetime):
            values=iter([NOW,NOW+timedelta(seconds=2)])
            @classmethod
            def now(cls,tz=None): return next(cls.values)
        with patch('match_availability.datetime',Clock):
            context=collect(self.source(data),'fra.1','1','2','123')
        self.assertFalse(context['fixture_verified'])
        self.assertEqual(context['reason'],'fixture_not_upcoming')

    def test_all_supported_leagues_are_accepted_and_unknown_rejected(self):
        import app
        for league in app.LEAGUES:
            with self.subTest(league=league):
                context=collect(self.source(),league,'1','2','123',now=NOW)
                self.assertTrue(context['fixture_verified'])
                self.assertEqual(context['league'],league)
                self.assertEqual(context['event_id'],'123')
        source=self.source()
        self.assertFalse(collect(source,'unsupported','1','2','123',now=NOW)['fixture_verified'])
        source.fetch.assert_not_called()

    def test_repeated_checks_preserve_first_state_and_only_archive_changes(self):
        cached=dict(league='fra.1',home_id='1',away_id='2',event_id='123',prediction={'home':75},generated_at=NOW.isoformat(),report={'sections':[]})
        source=self.source()
        self.assertTrue(refresh_cached(source,cached,now=NOW))
        first=copy.deepcopy(cached['personnel_context'])
        self.assertTrue(refresh_cached(source,cached,now=NOW+timedelta(minutes=6)))
        self.assertEqual(len(cached['personnel_snapshots']),1)
        changed=payload();changed['rosters'][0]['roster'][0]['athlete']['displayName']='Nouveau titulaire'
        source.fetch.return_value=changed
        self.assertTrue(refresh_cached(source,cached,now=NOW+timedelta(minutes=12)))
        self.assertEqual(cached['personnel_snapshots'][0],first)
        self.assertEqual(len(cached['personnel_snapshots']),2)
        self.assertEqual(cached['prediction'],{'home':75})
        self.assertEqual(cached['generated_at'],NOW.isoformat())

    def test_report_explains_conditional_impact_and_suspension_scope(self):
        context=collect(self.source(),'uefa.champions','1','2','123',now=NOW)
        text=section(dict(personnel_context=context,home_id='1',away_id='2',home_name='Paris',away_name='Madrid'))['text']
        self.assertIn('Si l’absence de Gardien est confirmée',text)
        self.assertIn('application à ce match non vérifiée',text)
        self.assertIn('confirmation officielle non vérifiée',text)
        self.assertIn('https://www.espn.com/soccer/match/_/gameId/123',text)

if __name__=='__main__':unittest.main()
