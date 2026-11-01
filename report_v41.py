"""V41 evidence-bounded French match reports. No fabricated injuries, standings or stakes."""

def report(home_name, away_name, home, away, prediction, quality):
    p=prediction['markets']; x=prediction['expected_goals']
    hgf=home['goals_for_avg']; hga=home['goals_against_avg']
    agf=away['goals_for_avg']; aga=away['goals_against_avg']
    gap=round(p['home']-p['away'],1)
    favorite=home_name if gap>8 else away_name if gap < -8 else None
    attack=home_name if hgf>agf+.35 else away_name if agf>hgf+.35 else None
    home_form=home['wins']/max(home['matches'],1)
    away_form=away['wins']/max(away['matches'],1)
    lead=(f"{home_name} part avec un avantage statistique mesuré : {p['home']} % de victoire contre {p['away']} % pour {away_name}." if gap>8 else
          f"{away_name} ressort favori du modèle ({p['away']} % contre {p['home']} %), malgré le déplacement." if gap < -8 else
          f"Le modèle ne dégage pas de favori net entre {home_name} ({p['home']} %) et {away_name} ({p['away']} %).")
    home_case=(f"{home_name} marque {hgf:.2f} but(s) et en encaisse {hga:.2f} par match sur l'échantillon étudié. Face à une défense adverse qui concède {aga:.2f} but(s) en moyenne, sa voie vers la victoire passe par l'efficacité offensive et la maîtrise des transitions."
               if hgf>=agf else
               f"Pour gagner, {home_name} doit améliorer son rendement offensif observé ({hgf:.2f} but(s)/match) et profiter de l'avantage théorique du terrain. La défense de {away_name} concède {aga:.2f} but(s)/match : c'est un point à surveiller.")
    away_case=(f"{away_name} possède une moyenne offensive de {agf:.2f} but(s)/match. Si cette production se confirme contre une équipe qui encaisse {hga:.2f} but(s) en moyenne, les visiteurs ont un scénario crédible de victoire."
               if agf>=hgf else
               f"{away_name} devra compenser une production offensive moyenne de {agf:.2f} but(s)/match. Son meilleur scénario serait de contenir les occasions adverses et d'exploiter les moments de déséquilibre, sans que les données disponibles prouvent une supériorité tactique.")
    if p['btts']>=65:
        scenario=f"Les deux équipes marquent est estimé à {p['btts']} % : le modèle envisage un match où les deux attaques trouvent des occasions. Un premier but pourrait accentuer les espaces."
    elif p['over_2_5']<=45:
        scenario=f"Avec {p['over_2_5']} % pour plus de 2,5 buts, le modèle privilégie plutôt un score contenu. Les phases arrêtées et le premier but pourraient alors peser davantage."
    else:
        scenario=f"Le seuil de 2,5 buts est évalué à {p['over_2_5']} % et les deux équipes marquent à {p['btts']} %. Ces marchés ne décrivent pas exactement le même scénario : il faut éviter de les confondre."
    if abs(gap)<8:
        opinion=f"Mon jugement : opposition ouverte, sans raison statistique suffisante pour annoncer un vainqueur certain. Les buts attendus ({x['home']} contre {x['away']}) donnent une lecture plus utile que le seul nom des clubs."
    else:
        opinion=f"Mon jugement : léger avantage à {favorite}, mais ce n'est pas une certitude. L'écart de {abs(gap):.1f} points entre les probabilités de victoire doit être confronté aux compositions et aux actualités avant toute conclusion ferme."
    caveats=[]
    if min(quality['home_games'],quality['away_games'])<10:caveats.append('échantillon réduit')
    if abs(home_form-away_form)>.3:caveats.append('écart notable de résultats récents, sans correction de la force des adversaires')
    caveats.extend(['classement et enjeux de compétition non vérifiés','blessures et suspensions non vérifiées','compositions et calendrier de récupération non vérifiés','xG et niveau des adversaires non intégrés'])
    return {'version':'41.0','type':'rapport_statistique_argumente','title':f'{home_name} – {away_name}',
            'sections':[{'heading':'Lecture du duel','body':lead},
                        {'heading':f'Pourquoi {home_name} peut gagner','body':home_case},
                        {'heading':f'Pourquoi {away_name} peut gagner','body':away_case},
                        {'heading':'Scénario de match','body':scenario},
                        {'heading':'Mon avis argumenté','body':opinion}],
            'enjeux':{'status':'non_verifies','message':'Course au titre, maintien, qualification, derby ou match décisif : aucun enjeu n’est affirmé sans classement et règlement de compétition vérifiés.'},
            'evidence':{'source':'ESPN (calendriers et scores via API non officielle)','matches_home':quality['home_games'],'matches_away':quality['away_games'],'home_goal_avg':hgf,'away_goal_avg':agf},
            'limitations':caveats,'notice':'Interprétation conditionnelle des statistiques, pas une opinion humaine ni une IA générative. Aucune cote de bookmaker utilisée.'}
