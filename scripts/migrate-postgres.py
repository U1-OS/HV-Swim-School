"""Transfer an approved SQLite snapshot to an empty PostgreSQL schema. No deployment."""
import argparse,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.database_migration import migrate
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('snapshot',type=Path)
    args=parser.parse_args()
    url=os.environ.get('HV_MIGRATION_TARGET_URL')
    if not url:parser.error('Set HV_MIGRATION_TARGET_URL using your private secret manager')
    try:result=migrate(args.snapshot,url)
    except Exception as exc:
        print(f'Migration stopped ({type(exc).__name__}); no source data changed. Inspect privately.',file=sys.stderr);raise SystemExit(1)
    print(json.dumps(result,indent=2))
