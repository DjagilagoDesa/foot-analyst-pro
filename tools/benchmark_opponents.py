"""Run offline: python tools/benchmark_opponents.py --help"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import probabilities, summary
from opponent_benchmark import run
from opponent_review import extended_review


def main():
    parser=argparse.ArgumentParser(description='Compare two frozen models chronologically; never updates production.')
    parser.add_argument('--input',required=True,help='JSON list of verified 90-minute fixtures')
    parser.add_argument('--validation-from',required=True,help='Timezone-aware ISO date, fixed before evaluation')
    parser.add_argument('--test-from',required=True,help='Timezone-aware ISO date, fixed before evaluation')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    raw=Path(args.input).read_bytes()
    records=json.loads(raw)
    report=run(records,args.validation_from,args.test_from,probabilities,summary)
    report['special_markets_review']=extended_review(report)
    report['dataset_sha256']=hashlib.sha256(raw).hexdigest()
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('version','validation','test','skipped','decision')},ensure_ascii=False))


if __name__=='__main__': main()
