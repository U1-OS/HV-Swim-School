"""Run one bounded mail batch. Default capture writes private local files, never sends."""
import argparse,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.database import db_session,initialise_database
from backend.config import DATA_DIR
from backend.security import business_today
from backend.mail_queue import process_one,queue_due,smtp_transport

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smtp',action='store_true')
    parser.add_argument('--release-held',action='store_true')
    parser.add_argument('--limit',type=int,default=20)
    args=parser.parse_args()
    if not 1<=args.limit<=100:parser.error('Limit must be between 1 and 100')
    transport=smtp_transport(os.environ) if args.smtp else None
    initialise_database()
    with db_session() as db:
        queue_due(db,business_today().isoformat())
        if args.release_held:db.execute("UPDATE mail_outbox SET status='queued' WHERE status='held'")
    for _ in range(args.limit):
        result=process_one(db_session,None if args.smtp else DATA_DIR/'email-capture',transport)
        if result is None:break
        print(result)
    print('SMTP mode completed; review accepted/uncertain records.' if args.smtp else 'Local capture complete. Nothing sent.')
