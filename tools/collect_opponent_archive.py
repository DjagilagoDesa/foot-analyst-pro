"""Collect bounded ESPN scoreboard archives for offline tests, not production."""
import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import ESPN, fetch, parse_events


def collect(leagues, start, end):
    if not 0 <= (end-start).days <= 366: raise ValueError('Choose 1 to 367 calendar days per collection')
    if end >= datetime.now(timezone.utc).date()-timedelta(days=1): raise ValueError('Use completed historical days, at least two days old')
    requests = [(league,start+timedelta(days=i)) for league in leagues for i in range((end-start).days+1)]
    if len(requests)>2000: raise ValueError('At most 2000 scoreboard requests per collection')
    games = {}; errors = []; incomplete = []; stopped_early = False; completed = 0
    def one(league,day):
        payload = fetch(f'{ESPN}/{league}/scoreboard',{'dates':day.strftime('%Y%m%d'),'limit':1000},ttl=3600)
        eligible = []
        for event in payload.get('events',[]):
            comp = (event.get('competitions') or [{}])[0]
            status = comp.get('status') or event.get('status') or {}
            # If the provider does not identify regulation time, do not certify it.
            if status.get('period') != 2: continue
            for row in parse_events({'events':[event]},regulation_only=True):
                kickoff = datetime.fromisoformat(row['date'].replace('Z','+00:00'))
                row.update(league=league,regulation_only=True,
                           available_at=(kickoff+timedelta(hours=24)).isoformat(),availability_assumed=True,
                           collected_at=datetime.now(timezone.utc).isoformat(),
                           source_url=f'https://www.espn.com/soccer/match/_/gameId/{row["id"]}')
                eligible.append(row)
        return eligible,len(payload.get('events',[]))>=1000
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {pool.submit(one,*job):job for job in requests}
        for future in as_completed(jobs):
            league,day = jobs[future]
            completed += 1
            try:
                rows,truncated = future.result()
                if truncated: incomplete.append(dict(league=league,date=day.isoformat(),reason='possible_truncation'))
                for row in rows:
                    # collected_at can differ across requests; stable identity is the event.
                    games.setdefault(row['id'],row)
            except Exception as error:
                errors.append(dict(league=league,date=day.isoformat(),error=type(error).__name__))
                if len(errors)>=12 and not games:
                    stopped_early = True
                    for queued in jobs: queued.cancel()
                    break
    return sorted(games.values(),key=lambda g:g['date']),dict(leagues=leagues,start=start.isoformat(),end=end.isoformat(),
        requests=len(requests),completed_requests=completed,stopped_early=stopped_early,errors=errors,incomplete=incomplete,
        limitation='Retrospective provider archive, not a vintage snapshot. Result availability is assumed kickoff + 24h. Coverage and later corrections are not guaranteed.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--leagues',nargs='+',required=True)
    parser.add_argument('--start',type=date.fromisoformat,required=True)
    parser.add_argument('--end',type=date.fromisoformat,required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    games,metadata=collect(args.leagues,args.start,args.end)
    serialized=json.dumps(games,ensure_ascii=False,indent=2)+'\n'
    metadata['dataset_sha256']=hashlib.sha256(serialized.encode()).hexdigest()
    Path(args.output).write_text(serialized)
    Path(args.output+'.coverage.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(fixtures=len(games),requests=metadata['requests'],failures=len(metadata['errors']))))
    if not games: raise SystemExit('No usable real fixtures collected; no benchmark conclusion is possible.')

if __name__=='__main__':main()
