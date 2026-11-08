"""Conservative adapter for fixture-specific ESPN personnel data.

A listed starter is not proof of club confirmation. Missing players are never
inferred to be injured; suspensions are not assumed to apply across competitions.
"""
import copy
import json
from datetime import datetime, timezone
from tracking import fixture_info

VERSION = 2
SUPPORTED_LEAGUES = ('eng.1','esp.1','ita.1','ger.1','fra.1','bra.1','por.1','ned.1','usa.1','arg.1','mex.1','uefa.champions','uefa.europa','eng.2','eng.3','eng.4','eng.fa','eng.league_cup','eng.trophy')
REFRESH_SECONDS = 300
MAX_REPORT_AGE_DAYS = 7


def obj(value):
    return value if isinstance(value, dict) else {}


def rows(value):
    return value if isinstance(value, list) else []


def instant(value):
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('missing_timezone')
    return date


def collect(server, league, home_id, away_id, event_id, now=None):
    fixed_now = now
    now = now or datetime.now(timezone.utc)
    ids = (str(home_id), str(away_id))
    result = dict(version=VERSION, observed_at=now.isoformat(), status='unavailable',
                  fixture_verified=False, teams={}, source='ESPN', source_url=None, league=league, event_id=str(event_id),
                  report_age_limit_days=MAX_REPORT_AGE_DAYS,
                  limitation='Couverture ESPN partielle. Une liste vide ne prouve pas l’absence de blessés ou suspendus. Confirmation officielle des compositions non vérifiée. Aucun ajustement des probabilités.')
    if league not in getattr(server, 'LEAGUES', SUPPORTED_LEAGUES) or not str(event_id).isdigit():
        result['reason'] = 'missing_fixture'
        return result
    result['source_url'] = f'https://www.espn.com/soccer/match/_/gameId/{event_id}'
    try:
        data = server.fetch(f'{server.ESPN}/{league}/summary', {'event':str(event_id)}, ttl=120)
        info = fixture_info(data)
        now = fixed_now or datetime.now(timezone.utc)
        result['observed_at'] = now.isoformat()
        if str((data.get('header') or {}).get('id')) != str(event_id) or (info['home_id'], info['away_id']) != ids:
            result['reason'] = 'fixture_mismatch'
            return result
        if info['state'] != 'pre' or info['completed'] or info['date'] <= now or any(x in info['name'] for x in ('POSTPON', 'CANCEL', 'ABANDON', 'SUSPEND')):
            result['reason'] = 'fixture_not_upcoming'
            return result
    except Exception:
        result['reason'] = 'source_unavailable'
        return result
    result.update(fixture_verified=True, status='partial', kickoff=info['date'].isoformat())
    for team in ids:
        result['teams'][team] = dict(lineup_status='unavailable', starters=[], availability=[], discarded_reports=0)
    rosters = data.get('rosters')
    for roster in rosters if isinstance(rosters, list) else []:
        if not isinstance(roster, dict): continue
        target = result['teams'].get(str(obj(roster.get('team')).get('id')))
        if target is None: continue
        seen = set(); starters = []
        for player in rows(roster.get('roster')):
            if not isinstance(player, dict) or player.get('starter') is not True: continue
            athlete = obj(player.get('athlete'))
            pid = str(athlete.get('id') or '')
            name = athlete.get('displayName')
            if not pid or not isinstance(name, str) or not name or pid in seen: continue
            seen.add(pid)
            position = obj(player.get('position')) or obj(athlete.get('position'))
            starters.append(dict(id=pid, name=name, position=str(position.get('abbreviation') or '')))
        target['starters'] = starters
        if starters:
            target['lineup_status'] = 'reported' if len(starters) == 11 else 'partial'
            # No field from this undocumented feed is treated as club confirmation.
            target['officially_verified'] = False
    blocks = data.get('injuries')
    states = {'out':'reported_out', 'doubtful':'doubtful', 'questionable':'questionable',
              'day-to-day':'questionable', 'suspended':'suspension_unverified_scope',
              'suspension':'suspension_unverified_scope'}
    for block in blocks if isinstance(blocks, list) else []:
        if not isinstance(block, dict): continue
        target = result['teams'].get(str(obj(block.get('team')).get('id')))
        if target is None: continue
        seen = set()
        for item in rows(block.get('injuries')):
            if not isinstance(item, dict): continue
            athlete = obj(item.get('athlete'))
            state = states.get(str(item.get('status', '')).strip().lower())
            name = athlete.get('displayName'); pid = str(athlete.get('id') or '')
            try:
                reported = instant(item['date'])
                recent = 0 <= (now-reported).total_seconds() <= MAX_REPORT_AGE_DAYS*86400
            except (KeyError, ValueError, TypeError, AttributeError):
                recent = False
            if not recent or not state or not pid or not isinstance(name, str) or not name:
                target['discarded_reports'] += 1
                continue
            if pid in seen: continue
            seen.add(pid)
            position = obj(athlete.get('position'))
            target['availability'].append(dict(id=pid, name=name, status=state,
                reported_at=reported.isoformat(), position=str(position.get('abbreviation') or ''),
                match_applicability_verified=False,
                conflicts_with_lineup=pid in {p['id'] for p in target['starters']}))
    return result


def section(data):
    context = data.get('personnel_context')
    if not context: return None
    lines = [f"Vérification effectuée le {context.get('observed_at', '')[:16].replace('T', ' ')} UTC."]
    labels = {'reported_out':'forfait signalé par ESPN', 'doubtful':'incertain', 'questionable':'disponibilité incertaine',
              'suspension_unverified_scope':'suspension signalée, application à ce match non vérifiée'}
    for side in ('home', 'away'):
        name = data.get(side+'_name', side)
        item = context.get('teams', {}).get(str(data.get(side+'_id')), {})
        starters = item.get('starters', [])
        if starters:
            qualifier = 'Composition indiquée par ESPN, confirmation officielle non vérifiée' if item.get('lineup_status') == 'reported' else 'Composition partielle indiquée par ESPN'
            lines.append(f"{name} : {qualifier} : " + ', '.join(p['name'] for p in starters) + '.')
        else:
            lines.append(f'{name} : composition indisponible ; aucune composition probable inventée.')
        availability = item.get('availability', [])
        for player in availability:
            lines.append(f"{name} — {player['name']} : {labels[player['status']]} (date du signalement : {player['reported_at'][:10]}).")
            if player.get('conflicts_with_lineup'):
                lines.append(f"Signalements contradictoires pour {player['name']} : également indiqué parmi les titulaires. Disponibilité à revérifier.")
                continue
            if player['status'] == 'reported_out':
                role = player.get('position', '').upper()
                focus = ('l’organisation du gardien et de la défense' if role in ('GK', 'G') else
                         'les repères défensifs' if role in ('D', 'DF', 'CB', 'LB', 'RB') else
                         'la création et l’équilibre au milieu' if role in ('M', 'MF', 'CM', 'DM', 'AM') else
                         'les solutions offensives' if role in ('F', 'FW', 'ST', 'CF', 'LW', 'RW') else 'l’équilibre de l’équipe')
                lines.append(f"Si l’absence de {player['name']} est confirmée pour ce match, il faudra vérifier {focus} et son remplacement. Son importance individuelle n’est pas mesurée ici.")
        if not availability:
            lines.append(f'{name} : aucun signalement récent exploitable reçu ; effectif complet non confirmé.')
        if item.get('discarded_reports'):
            lines.append('Des signalements sans date exploitable, anciens ou non reconnus ont été écartés.')
    lines.append(context.get('limitation', ''))
    if context.get('source_url'): lines.append('Source consultée : '+context['source_url'])
    return dict(title='Compositions et disponibilités signalées', text=' '.join(lines), source_url=context.get('source_url'))


def context_signature(context):
    """Preserve changed source states; repeated checks do not duplicate history."""
    return json.dumps({k:v for k,v in context.items() if k != 'observed_at'}, sort_keys=True, ensure_ascii=False)


def apply_context(cached, context):
    old = cached.get('personnel_context')
    snapshots = cached.setdefault('personnel_snapshots', [])
    if not snapshots and old:
        snapshots.append(copy.deepcopy(old))
    if not snapshots or context_signature(snapshots[-1]) != context_signature(context):
        snapshots.append(copy.deepcopy(context))
    cached['personnel_context'] = copy.deepcopy(context)
    if cached.get('report'):
        title = 'Compositions et disponibilités signalées'
        cached['report']['sections'] = [s for s in cached['report']['sections'] if s['title'] != title]
        cached['report']['sections'].append(section(cached))


def refresh_cached(server, cached, now=None):
    """Refresh source context only; retain prior states, original odds and generated_at."""
    if cached.get('league') not in getattr(server, 'LEAGUES', SUPPORTED_LEAGUES): return False
    fixed_now = now
    now = now or datetime.now(timezone.utc)
    old = cached.get('personnel_context') or {}
    try:
        if 0 <= (now-instant(old['observed_at'])).total_seconds() < REFRESH_SECONDS: return False
        if old.get('kickoff') and instant(old['kickoff']) <= now: return False
    except (KeyError, ValueError, TypeError, AttributeError):
        pass
    context = collect(server, cached['league'], cached.get('home_id'), cached.get('away_id'), cached.get('event_id', ''), now=fixed_now)
    if not context.get('fixture_verified'): return False
    apply_context(cached, context)
    return True
