"""Match-specific editorial reasoning from observed results, without invented news."""
from datetime import datetime

REPORT_VERSION = 3

def number(value):
    return f'{float(value):.2f}'.rstrip('0').rstrip('.').replace('.', ',')


def observations(matches, team_id):
    rows = []
    for match in matches or []:
        home = str(match.get('home_id')) == str(team_id)
        if str(team_id) not in (str(match.get('home_id')), str(match.get('away_id'))):
            continue
        try:
            gf = int(match['home_goals'] if home else match['away_goals'])
            ga = int(match['away_goals'] if home else match['home_goals'])
        except (KeyError, ValueError, TypeError):
            continue
        rows.append(dict(date=match.get('date') or '', gf=gf, ga=ga,
                         venue='home' if home else 'away',
                         opponent=match.get('away') if home else match.get('home'),
                         opponent_id=str(match.get('away_id') if home else match.get('home_id')),
                         outcome='V' if gf > ga else 'N' if gf == ga else 'D',
                         match_id=str(match.get('id') or '')))
    return sorted(rows, key=lambda r: r['date'], reverse=True)


def record(rows):
    n = len(rows)
    return dict(n=n, wins=sum(r['outcome']=='V' for r in rows),
                draws=sum(r['outcome']=='N' for r in rows),
                losses=sum(r['outcome']=='D' for r in rows),
                gf=sum(r['gf'] for r in rows)/n if n else 0,
                ga=sum(r['ga'] for r in rows)/n if n else 0,
                clean=sum(r['ga']==0 for r in rows),
                blanks=sum(r['gf']==0 for r in rows),
                points=sum(3 if r['outcome']=='V' else 1 if r['outcome']=='N' else 0 for r in rows))


def surprise_reading(home, away, h, a, p, hr, ar):
    """Explain upset evidence; labels are editorial, never extra probabilities."""
    ph, pa, pn = p['home'], p['away'], p['draw']
    if abs(ph-pa) < 8:
        return (f'Pas d’outsider clairement établi entre {home} et {away} : les victoires sont estimées à {number(ph)} % et {number(pa)} %. '
                f'Une victoire de l’un ou de l’autre ne constitue donc pas une surprise statistique nette. Le nul vaut {number(pn)} %. '
                'Les favoris dont il est question ici sont ceux du modèle, pas ceux des bookmakers.')
    favorite, outsider, fav, under, fr, ur, up = (home,away,h,a,hr,ar,pa) if ph>pa else (away,home,a,h,ar,hr,ph)
    signals=[]; counters=[]
    if fav['goals_against_avg'] >= 1.4 and under['goals_for_avg'] >= 1.2:
        signals.append(f'{outsider} marque {number(under["goals_for_avg"])} but par match face à un favori qui en concède {number(fav["goals_against_avg"])}')
    else:
        counters.append(f'le croisement attaque de {outsider} ({number(under["goals_for_avg"])} but/match) / défense de {favorite} ({number(fav["goals_against_avg"])} encaissé) ne déclenche pas le signal de fragilité retenu')
    if under['goals_against_avg'] <= 1:
        signals.append(f'{outsider} encaisse au plus un but en moyenne ({number(under["goals_against_avg"])}), un appui à un scénario serré')
    if under['goals_for_avg'] < 1:
        counters.append(f'l’attaque de {outsider} reste sous un but par match ({number(under["goals_for_avg"])}), ce qui freine surtout la victoire sèche')
    if fr and ur:
        fs, us = record(fr[:10]), record(ur[:10])
        if fs['losses']/fs['n'] >= .3:
            signals.append(f'{favorite} a perdu {fs["losses"]} de ses {fs["n"]} derniers matchs disponibles')
        else:
            counters.append(f'{favorite} ne compte que {fs["losses"]} défaite(s) en {fs["n"]} sorties')
        if us['points']/us['n'] >= 1.5:
            signals.append(f'{outsider} a pris {us["points"]} points sur {us["n"]} matchs ({us["wins"]} victoires, {us["draws"]} nuls)')
        if us['blanks']/us['n'] >= .4:
            counters.append(f'{outsider} est resté sans marquer dans {us["blanks"]} de ses {us["n"]} sorties')
    else:
        counters.append('les résultats détaillés manquent pour vérifier les séries ; les moyennes seules ne permettent pas de les inventer')
    # A transparent editorial triage, not a fitted or calibrated upset detector.
    label = 'outsider à examiner' if up >= 20 and len(signals)>=2 else 'surprise peu étayée dans cet échantillon'
    text=(f'{outsider} : {label}. Sa victoire reste estimée à {number(up)} %, le nul à {number(pn)} %. '
          f'Le scénario « {favorite} ne gagne pas » vaut {number(up+pn)} % ; il inclut le nul et ne doit pas être confondu avec une victoire de l’outsider. ')
    text+='Arguments favorables : '+('; '.join(signals) if signals else 'aucun des signaux statistiques retenus n’est déclenché')+'. '
    text+='Arguments contraires : '+('; '.join(counters) if counters else f'le modèle conserve une préférence pour {favorite}, malgré ces signaux')+'. '
    if pn >= up:
        text+=f'Parmi les deux issues contraires au favori, le nul est la plus probable dans le modèle ({number(pn)} % contre {number(up)} %). '
    else:
        text+=f'Le modèle place la victoire de {outsider} devant le nul, mais à {number(up)} % elle reste minoritaire. '
    text+=('La mention « à examiner » exige au moins 20 % de victoire et deux signaux favorables ; c’est un filtre éditorial non validé, pas une nouvelle probabilité. '
           'Ces signaux viennent des mêmes résultats que le modèle : ils ne sont pas indépendants et n’augmentent pas les pourcentages. '
           'Une surprise peut se produire même sans signal. Aucune comparaison aux cotes, aux absences ou aux compositions n’est disponible ici.')
    return text


def report(data, names=None, histories=None):
    if data.get('status') != 'ok' or not data.get('prediction'):
        return None
    home, away = names or (data.get('home_name','Domicile'), data.get('away_name','Extérieur'))
    h, a = data['home'], data['away']
    p = data['prediction']['markets']; goals = data['prediction']['expected_goals']
    hr = observations((histories or {}).get('home'), data.get('home_id'))
    ar = observations((histories or {}).get('away'), data.get('away_id'))
    sections = []
    def add(title, text):
        sections.append(dict(title=title, text=text))
    ph, pa, pn = p['home'], p['away'], p['draw']
    gap = abs(ph-pa)
    leader, outsider = (home, away) if ph>pa else (away,home)
    attack_gap = h['goals_for_avg'] - a['goals_for_avg']
    defence_gap = h['goals_against_avg'] - a['goals_against_avg']
    if gap < 8:
        verdict = (f'{home} – {away} : je ne retiens pas de favori net. Seulement {number(gap)} points séparent les deux probabilités de victoire. '
                   f'Le nul, à {number(pn)} %, compte dans cette lecture : réduire la rencontre à un choix sec masquerait une partie du risque.')
    elif max(ph,pa) < 50:
        verdict = (f'Je donne une préférence à {leader}, mais pas une majorité de chances de gagner : {number(max(ph,pa))} %. '
                   f'Le nul ou une victoire de {outsider} pèsent ensemble {number(100-max(ph,pa))} %. L’avantage existe, sa conversion en victoire reste fragile.')
    else:
        verdict = (f'{leader} possède l’avantage du modèle dans cette affiche : {number(max(ph,pa))} % de victoire contre '
                   f'{number(min(ph,pa))} % pour {outsider}. L’écart de {number(gap)} points justifie une préférence, '
                   f'avec encore {number(100-max(ph,pa))} % pour les autres issues.')
    verdict += f' Projection des buts : {number(goals["home"])} pour {home}, {number(goals["away"])} pour {away}.'

    if abs(attack_gap) < .2 and abs(defence_gap) < .2:
        reading = (f'Les bilans moyens sont proches : {home} marque {number(h["goals_for_avg"])} et concède {number(h["goals_against_avg"])} but par match ; '
                   f'{away} est à {number(a["goals_for_avg"])} marqué et {number(a["goals_against_avg"])} encaissé. '
                   'Ces chiffres ne suffisent pas à soutenir l’idée d’une domination structurelle. Le modèle applique aussi un ajustement générique domicile/extérieur de +7 % / −7 %, qui ne décrit pas à lui seul les forces de ces clubs.')
    else:
        stronger = home if attack_gap>0 else away
        tighter = home if defence_gap<0 else away
        reading = (f'La production offensive distingue {stronger} : écart de {number(abs(attack_gap))} but marqué par match entre les deux équipes. '
                   f'Le bilan défensif est plus favorable à {tighter}, avec {number(abs(defence_gap))} but encaissé de moins en moyenne. ')
        reading += ('Les deux indicateurs favorisent donc le même camp ; c’est un appui statistique cohérent à confronter à sa forme immédiate.' if stronger==tighter else
                    'L’attaque et la défense désignent des forces différentes : le match oppose deux profils, plutôt qu’une supériorité uniforme.')
    add('Ce qui distingue cette rencontre', reading)

    def team_section(name, other, own, opp, rows, venue, probability):
        text = (f'Sur les {own["matches"]} rencontres étudiées, {name} compte {own["wins"]} victoires, {own["draws"]} nuls et {own["losses"]} défaites. ')
        own_attack, own_def = own['goals_for_avg'], own['goals_against_avg']
        if own_attack >= 1.6 and opp['goals_against_avg'] >= 1.3:
            text += (f'Son meilleur argument est la rencontre entre son rendement offensif ({number(own_attack)} but par match) et les buts concédés par {other} '
                     f'({number(opp["goals_against_avg"])}). Cela rend un scénario avec plusieurs buts de {name} plausible, sans prouver une tactique ou une qualité d’occasions particulière. ')
        elif own_def <= 1:
            text += (f'Son principal appui est défensif : {number(own_def)} but encaissé par match. Une victoire dans un match contenu paraît plus cohérente '
                     f'avec ce bilan qu’un succès supposant une domination offensive permanente. ')
        elif own_attack < 1:
            text += (f'Le frein est offensif : moins d’un but marqué par match ({number(own_attack)}). Pour soutenir sa victoire, il faudrait une efficacité supérieure '
                     f'à cette moyenne ou une rencontre dans laquelle {other} reste lui aussi limité. ')
        else:
            text += (f'Avec {number(own_attack)} but marqué et {number(own_def)} encaissé par rencontre, le bilan décrit une équipe qui ne dispose pas '
                     'd’une marge évidente : son argument de victoire dépend autant de sa capacité à contenir l’adversaire que de sa production offensive. ')
        if rows:
            recent = record(rows[:10]); older = record(rows[10:])
            text += (f'Les {recent["n"]} sorties les plus récentes donnent {recent["wins"]} victoire(s), {recent["draws"]} nul(s), {recent["losses"]} défaite(s), '
                     f'avec {number(recent["gf"])} but marqué et {number(recent["ga"])} encaissé en moyenne. ')
            if older['n'] >= 3 and recent['n'] >= 3:
                delta = recent['points']/recent['n'] - older['points']/older['n']
                trend = 's’améliore' if delta > .35 else 'se dégrade' if delta < -.35 else 'reste proche du précédent échantillon'
                text += f'Le rendement en points {trend} ({number(recent["points"]/recent["n"])} contre {number(older["points"]/older["n"])} point par match). '
            streak=0
            for row in rows:
                if row['outcome']!=rows[0]['outcome']:break
                streak+=1
            if streak >= 2:
                text += f'La série la plus récente est de {streak} '+{'V':'victoires','N':'nuls','D':'défaites'}[rows[0]['outcome']]+'. '
            text += f'Dans cet historique, {sum(r["ga"]==0 for r in rows)} match(s) sans encaisser et {sum(r["gf"]==0 for r in rows)} sans marquer. '
            venue_rows=[r for r in rows if r['venue']==venue]
            if len(venue_rows)>=3:
                v=record(venue_rows)
                text += (f'Sur le terrain concerné ({"à domicile" if venue=="home" else "à l’extérieur"}), les {v["n"]} matchs disponibles donnent '
                         f'{v["wins"]} victoire(s), {v["draws"]} nul(s), {v["losses"]} défaite(s), {number(v["gf"])} but marqué et {number(v["ga"])} encaissé. '
                         'Ce sous-échantillon éclaire le profil, mais les probabilités affichées restent calculées sur les moyennes tous terrains. ')
            else:
                text += 'Le sous-échantillon sur le terrain concerné est trop court pour soutenir une conclusion domicile/extérieur séparée. '
            latest=rows[0]
            text += f'Dernier résultat disponible : {name} {latest["gf"]}–{latest["ga"]} contre {latest["opponent"] or "un adversaire non renseigné"} ({latest["date"][:10]}). '
        text += f'Le modèle chiffre sa victoire à {number(probability)} % ; cette lecture ne mesure ni la difficulté des adversaires ni les changements d’effectif.'
        return text
    add(f'{home} : ses arguments et ses limites', team_section(home,away,h,a,hr,'home',ph))
    add(f'{away} : comment il peut faire basculer le match', team_section(away,home,a,h,ar,'away',pa))

    encounters={}
    for row in hr:
        if row['opponent_id']==str(data.get('away_id')):encounters[row['match_id'] or row['date']]=row
    if encounters:
        details=[]
        for row in sorted(encounters.values(),key=lambda r:r['date'],reverse=True)[:3]:
            details.append(f'{row["date"][:10]} : {home} {row["gf"]}–{row["ga"]} {away}')
        add('Confrontations réellement retrouvées', '; '.join(details)+'. Ces rencontres sont celles présentes dans l’échantillon récent, pas un historique exhaustif. Elles ne suffisent pas à établir une supériorité durable.')

    total=goals['home']+goals['away']
    if p.get('btts',0)>=60:
        goal_reading=f'Le modèle donne une place importante à un but de chaque côté ({number(p["btts"])} %). Une victoire sans encaisser est donc moins cohérente avec cette projection qu’un succès avec réponse adverse.'
    elif p.get('btts',0)<45:
        goal_reading=f'Les deux équipes marquent est estimé à {number(p.get("btts",0))} % : le calcul penche davantage vers au moins une attaque muette que vers un échange de buts systématique.'
    else:
        goal_reading=f'À {number(p.get("btts",0))} % pour les deux équipes qui marquent, ce marché ne tranche pas nettement. Je ne l’utilise pas comme certitude centrale de l’analyse.'
    goal_reading += (f' Le total attendu est de {number(total)} buts. Plus de 1,5 : {number(p.get("over_1_5",0))} % ; '
                     f'plus de 2,5 : {number(p.get("over_2_5",0))} %. ')
    if total>=3:
        goal_reading+='La projection est orientée vers un total élevé ; elle ne garantit pas que les buts seront répartis entre les deux équipes.'
    elif total<=2.2:
        goal_reading+='Une rencontre à peu de buts est compatible avec ces moyennes ; un 0–0 ou un 1–0 ne serait pas incohérent avec le modèle.'
    else:
        goal_reading+='Le passage de deux à trois buts est une vraie frontière de risque : les deux seuils ne doivent pas être traités comme équivalents.'
    add('Buts : ce que les chiffres permettent vraiment de dire',goal_reading)

    if gap<8:
        scenario=f'Le scénario contradictoire principal est l’excès de confiance dans un favori qui n’est pas établi : {home} et {away} restent proches. Le nul ({number(pn)} %) doit être considéré au même titre que les victoires.'
    else:
        under=a if ph>pa else h
        fav=h if ph>pa else a
        scenario=(f'Pour contredire la préférence pour {leader}, {outsider} peut s’appuyer sur {number(under["goals_for_avg"])} but marqué par match face aux '
                  f'{number(fav["goals_against_avg"])} encaissés par le favori. ')
        scenario+=('La fragilité défensive moyenne du favori laisse une voie statistique à l’outsider.' if fav['goals_against_avg']>=1.4 else
                   'Le bilan défensif du favori rend cette voie plus étroite, sans la supprimer.')
        scenario+=f' La victoire de {outsider} est estimée à {number(min(ph,pa))} % et le nul à {number(pn)} %.'
    add('Le scénario qui ferait échouer ma lecture',scenario)
    add('Surprise possible : outsider et nul', surprise_reading(home,away,h,a,p,hr,ar))
    add('Ma conclusion sur les marchés',
        f'La probabilité d’une victoire de {home} est de {number(ph)} %, celle de {away} de {number(pa)} %. '
        f'Les couvertures 1X ({number(p.get("home_or_draw",ph+pn))} %) et X2 ({number(p.get("away_or_draw",pa+pn))} %) couvrent deux issues, ce qui explique leur niveau plus élevé. '
        'Sans cote réelle, je ne peux pas conclure qu’un choix est rentable. Les marchés de buts, les doubles chances et la victoire d’un même match sont liés : multiplier leurs pourcentages donnerait une fausse probabilité combinée.')
    errors=data.get('data_quality',{}).get('source_errors',{})
    partial=any(bool(v) for v in errors.values()) if isinstance(errors,dict) else bool(errors)
    limits=(f'Échantillons : {h["matches"]} résultats pour {home}, {a["matches"]} pour {away}. '
            + ('Des saisons n’ont pas pu être récupérées : couverture partielle. ' if partial else '')
            + ('Les tendances ci-dessus reposent sur les résultats détaillés disponibles. ' if hr and ar else 'Les résultats détaillés ne sont pas joints à cette analyse enregistrée : aucune série, tendance chronologique ou ventilation par terrain n’est déduite des seules moyennes. ')
            + 'Classement, enjeu de titre/Europe/maintien, absences, compositions, calendrier à venir et intentions tactiques ne sont pas vérifiés ici. '
            'Les buts attendus sont une projection Poisson, pas des xG mesurés sur les occasions. Les pourcentages ne sont pas calibrés sur une performance prédictive démontrée et ne sont pas une analyse en direct.')
    add('Données utilisées et points à vérifier',limits)
    return dict(version=REPORT_VERSION,verdict=verdict,sections=sections,
                method='Lecture conditionnelle des résultats disponibles et modèle Poisson indépendant',
                source=data.get('source'),generated_at=data.get('generated_at'))
