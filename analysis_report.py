"""Evidence-based editorial report from the statistics actually available."""
def report(data, names=None):
    if data.get('status')!='ok' or not data.get('prediction'):return None
    home,away=names or (data.get('home_name','Domicile'),data.get('away_name','Extérieur'))
    h,a=data['home'],data['away']; p=data['prediction']['markets']; xg=data['prediction']['expected_goals']
    leader=home if p['home']>p['away'] else away
    gap=abs(p['home']-p['away'])
    verdict=(f"Avantage statistique à {leader}, {'léger' if gap<12 else 'marqué' if gap>25 else 'modéré'}. "
             f"Le modèle attribue {p['home']} % à {home}, {p['draw']} % au nul et {p['away']} % à {away}. "
             "Ce jugement porte sur les résultats récents disponibles, pas sur une certitude de victoire.")
    def team_reason(name,own,opponent):
        return (f"{name} reste une option crédible : {own['wins']} victoires, {own['draws']} nuls et {own['losses']} défaites "
                f"sur {own['matches']} matchs étudiés. L’équipe marque {own['goals_for_avg']} but(s) par match "
                f"et en encaisse {own['goals_against_avg']}. Son adversaire en concède {opponent['goals_against_avg']} en moyenne. "
                "Pour gagner, elle devra transformer cette production offensive en occasions concrètes et limiter les erreurs défensives. "
                "Ces moyennes portent sur tous les terrains et ne constituent pas des statistiques exclusivement domicile/extérieur.")
    total=round(xg['home']+xg['away'],2)
    goals=(f"Projection : {xg['home']} but(s) pour {home}, {xg['away']} pour {away}, soit {total} au total. "
           f"Plus de 1,5 but : {p.get('over_1_5',0)} % ; plus de 2,5 : {p.get('over_2_5',0)} % ; "
           f"les deux équipes marquent : {p.get('btts',0)} %. "
           "Ces marchés sont corrélés : leurs probabilités ne doivent pas être multipliées pour fabriquer une cote de combiné.")
    return {'verdict':verdict,'sections':[
        {'title':f'Pourquoi {home} peut gagner','text':team_reason(home,h,a)},
        {'title':f'Pourquoi {away} peut gagner','text':team_reason(away,a,h)},
        {'title':'Lecture des buts','text':goals},
        {'title':'Scénarios qui peuvent contredire le favori','text':f"Le nul représente {p['draw']} %. Un premier but contre le cours du jeu, une exclusion ou un changement de composition peut modifier l’équilibre. Ces événements ne sont pas anticipés dans ce calcul ; les pourcentages affichés ne sont pas recalculés à partir du score en direct."},
        {'title':'Ce qui manque avant de conclure','text':"Classement, enjeu précis de la compétition, blessures, suspensions, compositions, repos, tactique, xG et cotes réelles ne sont pas intégrés. Aucun fait sur ces sujets n’est inventé. Cette analyse est une interprétation statistique, pas encore une recherche IA contextuelle sur l’actualité."}
    ],'method':'Résultats récents et modèle Poisson indépendant','source':data.get('source'),'generated_at':data.get('generated_at')}
