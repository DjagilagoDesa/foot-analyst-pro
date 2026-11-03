import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import requests
import app as server
from market_odds import decimal_price, extract, historical_close


def fixture():
    return {'id':'123','date':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),
        'competitions':[{'status':{'type':{'state':'pre','name':'STATUS_SCHEDULED'}},
        'competitors':[{'homeAway':'home','team':{'id':'1'}},{'homeAway':'away','team':{'id':'2'}}],
        'odds':[{'provider':{'name':'Example book'},
            'moneyline':{'home':{'close':{'odds':'+150'}},'draw':{'close':{'odds':'+250'}},'away':{'close':{'odds':'-125'}}},
            'total':{'over':{'close':{'line':'o2.5','odds':'-110'}},'under':{'close':{'line':'u2.5','odds':'+100'}}}}]}]}


class OddsTests(unittest.TestCase):
    def test_decimal_conversion_and_invalid_prices(self):
        self.assertEqual(decimal_price('+150'),2.5)
        self.assertEqual(decimal_price(-125),1.8)
        for invalid in (True,None,0,50,float('nan'),float('inf'),'bad'):
            self.assertIsNone(decimal_price(invalid))

    def test_exact_markets_no_synthetic_double_chance_or_joint_odds(self):
        books=extract(fixture(),'2026-01-01T00:00:00+00:00')
        self.assertEqual(books[0]['markets']['home'],2.5)
        self.assertEqual(books[0]['markets']['draw'],3.5)
        self.assertEqual(books[0]['markets']['over_2_5'],1.91)
        self.assertNotIn('home_or_draw',books[0]['markets'])
        self.assertIsNone(books[0]['source_updated_at'])
        data=fixture();data['competitions'][0]['odds'][0]['moneyline']['home']={'open':{'odds':'+110'}}
        self.assertNotIn('home',extract(data,'observed')[0]['markets'])

    def test_two_way_moneyline_is_not_presented_as_90_minute_odds(self):
        data=fixture();data['competitions'][0]['odds'][0]['moneyline'].pop('draw')
        markets=extract(data,'observed')[0]['markets']
        self.assertNotIn('home',markets)
        self.assertNotIn('away',markets)
        self.assertIn('over_2_5',markets)

    def test_non_prematch_and_missing_providers_not_quoted(self):
        for state in ('in','post'):
            data=fixture();data['competitions'][0]['status']['type']['state']=state
            self.assertEqual(extract(data,'observed'),[])
        data=fixture();data['competitions'][0]['status']['type']['name']='STATUS_POSTPONED'
        self.assertEqual(extract(data,'observed'),[])
        data=fixture();data['date']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        self.assertEqual(extract(data,'observed'),[])
        data=fixture();data['competitions'][0]['odds'][0].pop('provider')
        self.assertEqual(extract(data,'observed'),[])

    def test_route_identity_validation_source_failure_and_observation_time(self):
        client=server.app.test_client();data=fixture()
        query='/api/odds?league=fra.1&event_id=123&home_id=1&away_id=2&date='+data['date'][:10]
        with patch.object(server,'fetch',return_value={'events':[data]}):
            response=client.get(query)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json['books'][0]['bookmaker'],'Example book')
            self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertEqual(client.get(query.replace('home_id=1','home_id=99')).status_code,404)
            self.assertEqual(client.get(query.replace('event_id=123','event_id=456')).status_code,404)
        with patch.object(server,'fetch',side_effect=requests.Timeout()):
            self.assertEqual(client.get(query).status_code,503)
        self.assertEqual(client.get(query.replace('league=fra.1','league=unknown')).status_code,400)
        # A cached feed retains its original observation time.
        url=server.ESPN+'/fra.1/scoreboard';params={'dates':data['date'][:10].replace('-',''),'limit':200}
        key=(url,tuple(sorted(params.items())))
        with patch.dict(server.CACHE,{key:(1000,{'events':[data]})}),patch.object(server,'fetch',return_value={'events':[data]}):
            self.assertEqual(client.get(query).json['observed_at'],datetime.fromtimestamp(1000,timezone.utc).isoformat())

    def test_calendar_includes_the_same_observed_prices(self):
        data=fixture();client=server.app.test_client()
        with patch.object(server,'fetch',return_value={'events':[data]}):
            response=client.get('/api/fixtures?league=fra.1&date='+data['date'][:10])
        self.assertEqual(response.status_code,200)
        snapshot=response.json['events'][0]['market_odds']
        self.assertEqual(snapshot['books'][0]['markets']['home'],2.5)
        self.assertEqual(snapshot['books'][0]['markets']['away'],1.8)
        self.assertEqual(snapshot['books'][0]['observed_at'],snapshot['observed_at'])

    def past_data(self):
        event=fixture();event['date']=(datetime.now(timezone.utc)-timedelta(hours=12)).isoformat()
        comp=event['competitions'][0];comp['date']=event['date']
        comp['status']={'type':{'state':'post','name':'STATUS_FULL_TIME','completed':True},'period':2}
        comp['competitors'][0]['score']='3';comp['competitors'][1]['score']='1'
        data={'header':{'id':'123','competitions':[comp]},'odds':copy.deepcopy(comp['odds'])}
        pick={'match':{'id':'123','date':event['date'],'home':{'id':'1'},'away':{'id':'2'}},'home_score':3,'away_score':1}
        return data,pick

    def test_recovers_only_explicit_closing_prices_with_post_match_provenance(self):
        data,pick=self.past_data();quote=historical_close(data,pick)
        self.assertEqual(quote['markets'],{'home':2.5,'draw':3.5,'away':1.8})
        self.assertEqual(quote['kind'],'historical_close')
        self.assertIsNone(quote['observed_at'])
        self.assertIsNone(quote['source_updated_at'])
        self.assertIn('retrieved_at',quote)
        self.assertTrue(quote['source_url'].endswith('/123'))
        data['header']['competitions'][0]['status'].pop('period')
        self.assertIsNotNone(historical_close(data,pick))
        data['header']['competitions'][0]['status']['type']['name']='STATUS_FINAL'
        self.assertIsNone(historical_close(data,pick))

    def test_rejects_wrong_match_score_time_and_non_closing_or_missing_prices(self):
        for mode in ('event','teams','kickoff','score','live','extra','opening','draw_missing'):
            data,pick=self.past_data();comp=data['header']['competitions'][0]
            if mode=='event':data['header']['id']='999'
            if mode=='teams':comp['competitors'][0]['team']['id']='999'
            if mode=='kickoff':pick['match']['date']=(datetime.now(timezone.utc)-timedelta(hours=10)).isoformat()
            if mode=='score':pick['home_score']=4
            if mode=='live':comp['status']['type']['state']='in'
            if mode=='extra':comp['status']['period']=4
            if mode=='opening':data['odds'][0]['moneyline']['home']={'open':{'odds':'+150'}}
            if mode=='draw_missing':data['odds'][0]['moneyline'].pop('draw')
            self.assertIsNone(historical_close(data,pick),mode)
