import unittest
from analysis_report import report

class ReportTests(unittest.TestCase):
    def test_five_match_form_is_dated_and_does_not_change_probabilities(self):
        team = dict(wins=7, draws=3, losses=2, matches=12, goals_for_avg=1.7, goals_against_avg=1.1)
        data = dict(status='ok', home_name='Paris', away_name='Lyon', home_id='1', away_id='2',
                    home=team, away=team, prediction=dict(expected_goals={'home': 1.8, 'away': 1.3},
                    markets={'home': 48, 'draw': 28, 'away': 24, 'over_1_5': 70, 'over_2_5': 45, 'btts': 50}))
        games = [dict(id=str(n), date=f'2026-10-{n:02}T12:00:00Z', home_id='1', away_id='3',
                      home='Paris', away='Autre club', home_goals=2, away_goals=0) for n in range(1, 7)]
        result = report(data, histories={'home': games, 'away': []})
        section = next(s for s in result['sections'] if s['title'].startswith('Forme sur les cinq'))
        self.assertIn('15 point(s) sur 15', section['text'])
        self.assertIn('10 but(s) marqué(s) et 0 encaissé(s)', section['text'])
        self.assertIn('2026-10-02 au 2026-10-06', section['text'])
        self.assertIn('Lyon : résultats détaillés indisponibles', section['text'])
        self.assertIn('pas nécessairement les cinq derniers matchs toutes compétitions', section['text'])
        self.assertEqual(data['prediction']['markets']['home'], 48)
        freshness = next(s for s in result['sections'] if s['title'] == 'Ancienneté des résultats utilisés')
        self.assertIn('2026-10-06', freshness['text'])
        self.assertIn('Lyon : date du dernier résultat utilisé indisponible', freshness['text'])
        sources = [s for s in result['sections'] if s.get('source_url')]
        self.assertEqual(len(sources), 1)
        self.assertTrue(sources[0]['source_url'].endswith('/6'))

    def test_report_uses_real_metrics_and_balanced_scenarios(self):
        team=dict(wins=7,draws=3,losses=2,matches=12,goals_for_avg=1.7,goals_against_avg=1.1)
        data=dict(status='ok',home_name='Paris',away_name='Lyon',home=team,away=team,prediction=dict(expected_goals={'home':1.8,'away':1.3},markets={'home':48,'draw':28,'away':24,'over_1_5':70,'over_2_5':45,'btts':50}))
        result=report(data)
        self.assertIn('Paris',result['verdict'])
        sections=result['sections']
        self.assertTrue(any('7 victoires' in section['text'] for section in sections))
        self.assertTrue(any('Lyon' in section['title'] for section in sections))
        self.assertTrue(any('Surprise possible' in section['title'] for section in sections))
        self.assertIn('ne sont pas vérifiés',sections[-1]['text'])
    def test_champions_report_distinguishes_match_and_qualification(self):
        team = dict(wins=6, draws=2, losses=2, matches=10, goals_for_avg=1.6, goals_against_avg=1.1)
        data = dict(status='ok', league='uefa.champions', home_name='Paris', away_name='Madrid',
                    home=team, away=team, prediction=dict(expected_goals={'home':1.7,'away':1.3},
                    markets={'home':45,'away':30,'draw':25}))
        result = report(data)
        section = next(s for s in result['sections'] if s['title'].startswith('Ligue des champions'))
        self.assertIn('pas la qualification', section['text'])
        self.assertIn('force n’est pas corrigée', section['text'])
        self.assertIn('Paris : détail du parcours européen indisponible', section['text'])
        self.assertEqual(data['prediction']['markets']['home'], 45)

    def test_no_report_without_successful_data(self):
        self.assertIsNone(report({'status':'insufficient_data'}))

