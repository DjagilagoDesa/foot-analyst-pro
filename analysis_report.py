"""Match-specific editorial reasoning from observed results, without invented news."""
from datetime import datetime

REPORT_VERSION = 10

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
                         match_id=str(match.get('id') or ''), competition=match.get('competition')))
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


def domestic_section(data):
    context = data.get('domestic_context')
    if not context:
        return None
    lines = [f"Contexte consulté le {context.get('observed_at', '')[:16].replace('T', ' ')} UTC."]
    for side in ('home', 'away'):
        name = data.get(side+'_name', side)
        team_id = str(data.get(side+'_id'))
        item = context.get('teams', {}).get(team_id, {})
        rows = observations(item.get('games'), team_id)
        if not rows:
            lines.append(f'{name} : forme nationale indisponible dans la couverture consultée.')
        else:
            stats = record(rows)
            sequence = ' – '.join(row['outcome'] for row in rows)
            lines.append(f"{name} ({item.get('league')}) : {sequence}, du plus récent au plus ancien (V = victoire, N = nul, D = défaite). "
                         f"{stats['n']} match(s) du {rows[-1]['date'][:10]} au {rows[0]['date'][:10]}, "
                         f"{stats['points']} point(s) sur {3*stats['n']}, {sum(r['gf'] for r in rows)} but(s) marqué(s), "
                         f"{sum(r['ga'] for r in rows)} encaissé(s).")
            for venue, label in (('home', 'domicile'), ('away', 'extérieur')):
                split = record([r for r in rows if r['venue'] == venue])
                lines.append(f"Dans ces résultats à {label} : {split['n']} match(s), {split['wins']} victoire(s), "
                             f"{split['draws']} nul(s), {split['losses']} défaite(s).")
        last = item.get('last_observed_match')
        if item.get('rest_hours') is not None and last:
            lines.append(f"{name} : {number(item['rest_hours'])} heures entre le dernier coup d’envoi observé "
                         f"({last['date'][:10]}, {last.get('home')} – {last.get('away')}) et ce match européen.")
        else:
            lines.append(f'{name} : temps de repos non calculable avec les données vérifiées.')
        if item.get('status') != 'ok':
            lines.append(f'{name} : couverture partielle ou indisponible, aucune série complétée artificiellement.')
    lines.append(context.get('note', ''))
    if context.get('failed_leagues'):
        lines.append('Certains championnats n’ont pas répondu à la recherche.')
    lines.append(('Les résultats nationaux retenus dans la base de calcul participent aux moyennes du modèle ; le repos ne modifie pas les probabilités. ' if data.get('analysis_basis') else 'La forme nationale et le repos contextualisent le jugement ; ils ne modifient pas les probabilités européennes. ') +
                 'Les forces des adversaires nationaux ne sont pas ajustées : ces bilans ne sont pas directement équivalents entre championnats.')
    return dict(title='Forme nationale et repos avant la Ligue des champions', text=' '.join(lines))


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
    basis = data.get('analysis_basis')
    if basis:
        details = []
        for side, name in (('home',home),('away',away)):
            item = basis[side]
            competitions = ', '.join(f'{key} : {count}' for key,count in item['competitions'].items()) or 'aucune'
            details.append(f"{name} : {item['sample']} match(s) utilisé(s), {competitions}, du {(item.get('oldest') or '')[:10]} au {(item.get('newest') or '')[:10]}.")
        details.append('Recherche bornée aux compétitions couvertes et aux résultats exploitables des 540 derniers jours, jusqu’à 20 par équipe. '
                       'Les historiques peuvent mélanger championnat et Europe : le niveau des adversaires n’est pas corrigé. '
                       'Un petit échantillon rend les pourcentages particulièrement fragiles ; ils ne sont pas calibrés.')
        if any(basis[side]['sample'] < 10 for side in ('home','away')):
            details.append('ÉCHANTILLON LIMITÉ : moins de dix résultats pour au moins une équipe. Analyse exploratoire, forte incertitude.')
        add('Base des calculs : recherche adaptée par équipe', ' '.join(details))
    if data.get('league') == 'uefa.champions':
        lines = []
        for name, rows, venue in ((home, hr, 'home'), (away, ar, 'away')):
            rows = [r for r in rows if r.get('competition') in (None,'uefa.champions','uefa.europa')]
            if not rows:
                lines.append(f'{name} : détail du parcours européen indisponible.')
                continue
            split = record([r for r in rows if r['venue'] == venue])
            opponents = list(dict.fromkeys(r['opponent'] for r in rows if r.get('opponent')))
            lines.append(f"{name} : résultats européens du {rows[-1]['date'][:10]} au {rows[0]['date'][:10]}. "
                         f"Sur le terrain considéré : {split['n']} match(s), {split['wins']} victoire(s), "
                         f"{split['draws']} nul(s), {split['losses']} défaite(s). "
                         f"Adversaires rencontrés : {', '.join(opponents)}.")
        lines.append('Ces parcours affrontent des adversaires différents : leur force n’est pas corrigée par le modèle. '
                     + ('Le classement européen et le score cumulé d’une éventuelle double confrontation ne sont pas vérifiés. ' if data.get('domestic_context') else 'La forme en championnat national, le classement européen et le score cumulé d’une éventuelle double confrontation ne sont pas vérifiés. ')
                     + 'Les marchés concernent le résultat du match, pas la qualification. Aucun bonus de confiance européen n’est ajouté.')
        add('Ligue des champions : lecture du parcours européen', ' '.join(lines))
    from match_availability import section as personnel_section
    personnel = personnel_section(data)
    if personnel:
        sections.append(personnel)
    national = domestic_section(data)
    if national:
        sections.append(national)
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

    if hr or ar:
        form = []
        for name, rows in ((home, hr), (away, ar)):
            recent = rows[:5]
            if not recent:
                form.append(f'{name} : résultats détaillés indisponibles pour comparer la forme sur cinq matchs.')
                continue
            stats = record(recent)
            sequence = ' – '.join(row['outcome'] for row in recent)
            form.append(
                f'{name} : {sequence} (du plus récent au plus ancien ; V = victoire, N = nul, D = défaite). '
                f'Sur {stats["n"]} match(s) disponible(s), {stats["points"]} point(s) sur {3 * stats["n"]}, '
                f'{sum(row["gf"] for row in recent)} but(s) marqué(s) et {sum(row["ga"] for row in recent)} encaissé(s). '
                f'Période observée : {recent[-1]["date"][:10]} au {recent[0]["date"][:10]}.')
        form.append('Cette forme décrit les matchs retrouvés dans les compétitions indiquées, pas nécessairement les cinq derniers matchs toutes compétitions. '
                    'Elle ne modifie pas les probabilités du modèle et ne renseigne pas les absences ou les compositions actuelles.')
        add('Forme sur les cinq derniers résultats disponibles', ' '.join(form))

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

    h2h = data.get('head_to_head')
    if h2h is not None:
        past = observations(h2h.get('matches'),data.get('home_id'))
        years = h2h.get('seasons_checked') or []
        scope = (f"Recherche dans la compétition {h2h.get('competition',data.get('league',''))}, "
                 + (f"sur les saisons {min(years)} à {max(years)}. " if years else "sur les saisons disponibles. "))
        if past:
            stats = record(past)
            text = (scope + f"Sur {stats['n']} confrontation(s) retrouvée(s), {home} compte {stats['wins']} victoire(s), "
                    f"{stats['draws']} nul(s) et {stats['losses']} défaite(s) face à {away}. "
                    f"Buts moyens : {number(stats['gf'])} pour {home}, {number(stats['ga'])} pour {away}. ")
            text += 'Résultats, du plus récent au plus ancien : ' + '; '.join(
                f"{r['date'][:10]} : {home} {r['gf']}–{r['ga']} {away} ({'chez '+home if r['venue']=='home' else 'chez '+away})"
                for r in past) + '. '
            if stats['wins'] > stats['losses']:
                dominant = home
            elif stats['losses'] > stats['wins']:
                dominant = away
            else:
                dominant = None
            if dominant:
                text += f"Le bilan de ces confrontations favorise {dominant}. "
                if gap >= 8:
                    text += ("Il va dans le sens de la préférence du modèle, sans constituer une preuve indépendante. " if dominant==leader else
                             "Il contredit la préférence actuelle du modèle : c’est un point à examiner dans le scénario de surprise, pas une raison suffisante pour renverser le favori. ")
            else:
                text += "Ce bilan ne départage pas les équipes par le nombre de victoires. "
            try:
                generated = datetime.fromisoformat(data['generated_at'].replace('Z','+00:00'))
                latest = datetime.fromisoformat(past[0]['date'].replace('Z','+00:00'))
                if (generated-latest).days > 730:
                    text += "Même la confrontation la plus récente date de plus de deux ans : sa pertinence actuelle est faible. "
            except (KeyError, ValueError, TypeError):
                pass
            if stats['n'] < 3:
                text += "Moins de trois confrontations : échantillon trop court pour dégager une tendance robuste. "
            text += ("Ces résultats contextualisent le jugement et les surprises possibles ; ils ne modifient pas mécaniquement les pourcentages calculés sur l’échantillon indiqué. "
                     "Certains de ces matchs peuvent déjà figurer dans ces résultats et ne constituent donc pas un second signal indépendant. "
                     "Les effectifs et les entraîneurs ont pu changer depuis.")
        else:
            text = scope + ("La source n’a pas répondu : confrontations indisponibles. " if h2h.get('status')=='unavailable' else
                            "Aucune confrontation terminée retrouvée dans cette couverture ; cela ne signifie pas que les équipes ne se sont jamais affrontées. ")
        if h2h.get('status')=='partial':
            text += " Certaines saisons sont indisponibles : bilan partiel."
        text += " La recherche est limitée à cette compétition et à dix confrontations ; les autres coupes et championnats ne sont pas couverts ici."
        add('Confrontations passées : bilan et incidence sur le jugement',text)
    else:
        encounters = [r for r in hr if r['opponent_id']==str(data.get('away_id'))]
        if encounters:
            add('Confrontations présentes dans la forme récente', '; '.join(
                f"{r['date'][:10]} : {home} {r['gf']}–{r['ga']} {away}" for r in encounters)
                + '. Cette ancienne analyse ne contient pas de recherche historique distincte.')

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
    freshness = []
    for name, rows in ((home, hr), (away, ar)):
        freshness.append(f"{name} : dernier résultat utilisé daté du {rows[0]['date'][:10]}." if rows else
                         f'{name} : date du dernier résultat utilisé indisponible.')
    freshness.append('La date de génération de cette analyse ne prouve pas que les actualités du jour ont été vérifiées. '
                     'Les dates ci-dessus décrivent les résultats utilisés, pas la date de consultation de la source.')
    add('Ancienneté des résultats utilisés', ' '.join(freshness))
    # Direct links point only to historical matches actually present in this report.
    for name, rows in ((home, hr), (away, ar)):
        linked = next((row for row in rows if row['match_id'].isdigit()), None)
        if linked:
            sections.append(dict(title=f'Source du dernier résultat référencé : {name}',
                                 text=f"{linked['date'][:10]} : adversaire {linked['opponent']}, {linked['gf']} but(s) marqué(s), {linked['ga']} encaissé(s). Cette fiche documente ce résultat uniquement.",
                                 source_url='https://www.espn.com/soccer/match/_/gameId/'+linked['match_id']))
    add('Données utilisées et points à vérifier',limits)
    return dict(version=REPORT_VERSION,verdict=verdict,sections=sections,
                method='Lecture conditionnelle des résultats disponibles et modèle Poisson indépendant',
                source=data.get('source'),generated_at=data.get('generated_at'))

