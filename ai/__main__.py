"""File CLI for smoke tests; the application imports run_pipeline directly."""
import argparse
import json
import os
from pathlib import Path
from .pipeline import run_pipeline
from .errors import PipelineError

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('input',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    os.umask(0o077)
    try:
        result=run_pipeline(json.loads(args.input.read_text()))
    except PipelineError as e:
        print(json.dumps({'code':e.code,'message':e.message},ensure_ascii=False))
        return 1
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Result validated and saved locally.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
