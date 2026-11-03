import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import requests
import app as server
from market_odds import decimal_price, extract


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
