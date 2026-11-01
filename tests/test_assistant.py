import unittest,os
from unittest.mock import patch,Mock
from football_assistant import answer,supplied_ticket
class Assistant(unittest.TestCase):
 def test_exact_target_from_supplied_odds(self):
  d=supplied_ticket('Ticket entre 30 et 50\nA-B | 1X + BTTS | 3,5\nC-D | X2 + plus de 2.5 | 3\nE-F | 1X | 4')
  self.assertEqual(d['status'],'ok');self.assertEqual(d['ticket']['combined_odds'],42)
  self.assertEqual(d['ticket']['odds_source'],'user_supplied_unverified')
 def test_target_not_reachable(self):
  d=supplied_ticket('entre 30 et 50\nA-B | 1X | 1.5\nC-D | 1X | 1.5');self.assertEqual(d['status'],'needs_odds')
 def test_same_match_not_multiplied(self):
  d=supplied_ticket('entre 5 et 7\nA-B | 1X | 2\nA-B | BTTS | 3');self.assertEqual(d['status'],'needs_odds')
 def test_winamax_requires_evidence_not_model(self):
  with patch('football_assistant.requests.post') as post:
   d,status=answer({'prompt':'ticket Winamax cote entre 30 et 50'})
  post.assert_not_called();self.assertEqual(d['status'],'needs_odds')
 def test_missing_configuration_not_fake_ai(self):
  with patch.dict(os.environ,{'OPENAI_API_KEY':'','OPENAI_MODEL':''}):
   d,status=answer({'prompt':'Explique le rôle du milieu défensif'})
  self.assertEqual(status,503);self.assertEqual(d['error'],'assistant_not_configured')
 def test_real_provider_contract_with_mock(self):
  response=Mock();response.json.return_value={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'Réponse documentée'}]}]}
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test-secret','OPENAI_MODEL':'test-model'}),patch('football_assistant.requests.post',return_value=response) as post:
   d,status=answer({'prompt':'Explique le rôle du milieu défensif'})
  self.assertEqual(d['assistant_reply'],'Réponse documentée');self.assertFalse(post.call_args.kwargs['json']['store']);self.assertNotIn('test-secret',str(d))
if __name__=='__main__':unittest.main()
