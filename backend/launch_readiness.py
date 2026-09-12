"""Owner attestations alongside independently measured application configuration."""
from urllib.parse import urlparse

EVIDENCE={
 'domain':'Domain ownership and DNS', 'mailbox':'Business mailbox send/receive test',
 'business':'Pricing, calendar and venue instructions','photos':'Approved imagery and consent',
 'policies':'Final policy review','recovery':'Backup restoration rehearsal',
 'security':'Independent security review','accessibility':'Keyboard and assistive-technology review',
 'postgres':'Production database migration and reconciliation',
}
SCHEMA="""CREATE TABLE IF NOT EXISTS launch_evidence(
 key TEXT PRIMARY KEY,reference TEXT NOT NULL,reviewed_by INTEGER NOT NULL REFERENCES users(id),
 reviewed_at TEXT NOT NULL,expires_on TEXT NOT NULL
);"""

def report(db,settings,today):
    saved={row['key']:dict(row) for row in db.execute('SELECT * FROM launch_evidence')}
    checks=[]
    for key,label in EVIDENCE.items():
        item=saved.get(key)
        current=bool(item and item['expires_on']>=today)
        checks.append({'key':key,'label':label,'ready':current,'kind':'Owner evidence','reference':item['reference'] if item else '', 'expires_on':item['expires_on'] if item else None})
    parsed=urlparse(settings.public_url)
    remote=bool(parsed.scheme=='https' and parsed.hostname and parsed.hostname not in ('localhost','127.0.0.1','::1') and not parsed.hostname.endswith(('.test','.invalid','.example')))
    measured=[('runtime','Production environment',settings.production),('origin','Configured HTTPS business origin',remote),('storage','PostgreSQL adapter selected',bool(settings.database_url)),('keys','Separate production data key',settings.production and len(settings.data_encryption_key)>=32 and settings.data_encryption_key!=settings.session_secret)]
    checks.extend({'key':key,'label':label,'ready':bool(ok),'kind':'Configuration check','reference':''} for key,label,ok in measured)
    return {'checks':checks,'ready_for_launch_review':all(c['ready'] for c in checks),'launch_authorised':False,'message':'Evidence records support a launch review; they never deploy the site or activate payments/email.'}
