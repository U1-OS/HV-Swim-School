"""Create or rehearse restore of an encrypted private-data bundle. No live overwrite."""
import argparse,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.recovery import create_bundle,restore_bundle
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['create','restore']);parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path)
    args=parser.parse_args();phrase=os.environ.get('HV_BACKUP_PASSPHRASE','')
    if args.action=='create':
        material={name:os.environ[name] for name in ['HV_DATA_ENCRYPTION_KEY','HV_SESSION_SECRET'] if name in os.environ}
        result=create_bundle(args.source,args.destination,phrase,material)
    else:result=restore_bundle(args.source,args.destination,phrase)
    print(json.dumps(result))
