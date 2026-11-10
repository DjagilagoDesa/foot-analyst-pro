"""Read quoted pre-match prices, never infer missing bookmaker markets."""
import math
from datetime import datetime, timezone


def decimal_price(value):
    if isinstance(value, bool):
        return None
    try:
        american = float(value)
        if not math.isfinite(american) or abs(american) < 100:
            return None
        return round(1 + (american / 100 if american > 0 else 100 / -american), 2)
    except (TypeError, ValueError, OverflowError):
        return None


def extract(event, observed_at, now=None):
    now = now or datetime.now(timezone.utc)
    comp = (event.get('competitions') or [{}])[0]
    status = (comp.get('status') or event.get('status') or {}).get('type') or {}
    kickoff = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
    if kickoff.tzinfo is None or kickoff <= now or status.get('state') != 'pre' or status.get('completed'):
        return []
    if any(word in status.get('name', '').upper() for word in ('POSTPONED', 'CANCEL', 'ABANDON', 'SUSPEND')):
        return []
    books = []
    for odds in comp.get('odds') or []:
        if not isinstance(odds, dict):
            continue
        provider = odds.get('provider') or {}
        if not provider.get('name'):
            continue
        markets = {}
        # Only the current quoted line; opening prices are not current prices.
        for side in ('home', 'draw', 'away'):
            price = decimal_price((odds.get('moneyline', {}).get(side, {}).get('close') or {}).get('odds'))
            if price:
                markets[side] = price
        # A two-way moneyline can denote qualification, not the 90-minute 1X2.
        if not all(side in markets for side in ('home','draw','away')):
            markets.clear()
        for side, prefix in (('over', 'o'), ('under', 'u')):
            current = odds.get('total', {}).get(side, {}).get('close') or {}
            line = str(current.get('line', '')).lower()
            if line in (prefix+'1.5', prefix+'2.5', prefix+'3.5'):
                price = decimal_price(current.get('odds'))
                if price:
                    markets[side+'_'+line[1:].replace('.', '_')] = price
        if markets:
            books.append({'bookmaker': str(provider['name']), 'markets': markets,
                          'observed_at': observed_at, 'source_updated_at': None})
    return books


def historical_close(data, pick, now=None):
    """Use explicitly labelled closing prices from a verified final match, not live prices."""
    from tracking import fixture_info, score
    now=now or datetime.now(timezone.utc)
    match=pick['match'];info=fixture_info(data)
    if str(data.get('header',{}).get('id'))!=str(match['id']):
        return None
    kickoff=datetime.fromisoformat(match['date'].replace('Z','+00:00'))
    if info['date']!=kickoff or info['date']>=now or info['state']!='post' or not info['completed']:
        return None
    if ((info['period'] is None and info['name']!='STATUS_FULL_TIME')
        or (info['period'] is not None and int(info['period'])!=2)
        or any(x in info['name'] for x in ('EXTRA','PENALT','CANCEL','ABANDON','POSTPON'))):
        return None
    if info['home_id']!=str(match['home']['id']) or info['away_id']!=str(match['away']['id']):
        return None
    if score(info['home'].get('score'))!=pick.get('home_score') or score(info['away'].get('score'))!=pick.get('away_score'):
        return None
    for book in data.get('odds') or data.get('pickcenter') or []:
        if not isinstance(book, dict):
            continue
        provider=book.get('provider') or {};markets={}
        for side in ('home','draw','away'):
            value=decimal_price((book.get('moneyline',{}).get(side,{}).get('close') or {}).get('odds'))
            if value:markets[side]=value
        if provider.get('name') and len(markets)==3:
            return {'bookmaker':provider['name'],'markets':markets,'source':'ESPN',
                'kind':'historical_close','observed_at':None,'source_updated_at':None,
                'retrieved_at':now.isoformat(),
                'source_url':'https://www.espn.com/soccer/match/_/gameId/'+str(match['id'])}
    return None
