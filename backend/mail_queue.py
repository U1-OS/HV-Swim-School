"""Durable enquiry mail with explicit capture/live boundaries and uncertain-send handling."""
import hashlib
import json
import os
import smtplib
import ssl
from datetime import datetime,timedelta,timezone
from pathlib import Path
from .enquiry_mail import enquiry_email
from .security import encrypt_sensitive,decrypt_sensitive,now_iso

SCHEMA="""CREATE TABLE IF NOT EXISTS mail_outbox(
 id INTEGER PRIMARY KEY AUTOINCREMENT,dedupe_key TEXT UNIQUE NOT NULL,
 encrypted_payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'held',attempts INTEGER NOT NULL DEFAULT 0,
 available_at TEXT NOT NULL,claimed_at TEXT,last_error TEXT,created_at TEXT NOT NULL,finished_at TEXT
);"""


def enqueue(db,kind,reference,recipient,key):
    enquiry_email(kind,reference,recipient)  # Validate before storing.
    db.execute("INSERT OR IGNORE INTO mail_outbox(dedupe_key,encrypted_payload,available_at,created_at) VALUES(?,?,?,?)",(key,encrypt_sensitive(json.dumps({'kind':kind,'reference':reference,'recipient':recipient})),now_iso(),now_iso()))


def queue_due(db,today):
    for row in db.execute("SELECT e.id,e.revision,e.enquiry_type,u.email FROM enquiries e JOIN users u ON u.id=e.assigned_to WHERE e.status<>'closed' AND e.follow_up_on<=? AND u.active=1 AND u.role='admin'",(today,)):
        ref=f"HV-{'MERCH' if row['enquiry_type']=='merchandise' else 'ENQ'}-{row['id']:04d}"
        enqueue(db,'management_follow_up',ref,row['email'],f"follow-up:{row['id']}:{row['revision']}:{today}")


def recover_claims(db,now):
    cutoff=(now-timedelta(minutes=10)).isoformat()
    db.execute("UPDATE mail_outbox SET status='uncertain',last_error='Worker stopped during delivery; reconcile before retrying' WHERE status='processing' AND claimed_at<?",(cutoff,))


def process_one(session,capture_dir=None,transport=None):
    """Capture is local-only. An injected transport must be approved by the CLI gate."""
    with session() as db:
        db.execute('BEGIN IMMEDIATE')
        recover_claims(db,datetime.now(timezone.utc))
        row=db.execute("SELECT * FROM mail_outbox WHERE status IN ('queued','retry') AND available_at<=? ORDER BY id LIMIT 1",(now_iso(),)).fetchone()
        if not row:return None
        item=dict(row)
        db.execute("UPDATE mail_outbox SET status='processing',attempts=attempts+1,claimed_at=? WHERE id=?",(now_iso(),item['id']))
    try:
        payload=json.loads(decrypt_sensitive(item['encrypted_payload']))
        message=enquiry_email(payload['kind'],payload['reference'],payload['recipient'])
        message['Message-ID']=f"<{hashlib.sha256(item['dedupe_key'].encode()).hexdigest()}@hvswim.local>"
        if capture_dir is not None:
            root=Path(capture_dir);root.mkdir(mode=0o700,parents=True,exist_ok=True)
            target=root/f"mail-{item['id']}.eml"
            fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as output: output.write(message.as_bytes())
            status,error='captured',None
        elif transport is not None:
            transport(message)
            status,error='accepted',None  # SMTP acceptance is not proof of inbox delivery.
        else:
            status,error='held','No transport configured'
    except smtplib.SMTPResponseException as exc:
        status='retry' if 400<=exc.smtp_code<500 and item['attempts']<4 else 'failed'
        error=f'SMTP rejected message ({exc.smtp_code}); no provider body stored'
    except (OSError,smtplib.SMTPException):
        status,error='uncertain','Connection failed; check provider outcome before retrying'
    except (ValueError,TypeError,KeyError,json.JSONDecodeError):
        status,error='failed','Stored message could not be prepared'
    with session() as db:
        db.execute("UPDATE mail_outbox SET status=?,last_error=?,finished_at=?,available_at=? WHERE id=? AND status='processing'",(status,error,now_iso() if status in ('accepted','captured') else None,(datetime.now(timezone.utc)+timedelta(minutes=min(60,2**(item['attempts']+1)))).isoformat(),item['id']))
    return {'id':item['id'],'status':status}


def smtp_transport(env):
    if env.get('HV_APP_ENV')!='production' or env.get('HV_EMAIL_LIVE_APPROVED')!='true':
        raise ValueError('Live email requires explicit production approval')
    required=['HV_SMTP_HOST','HV_SMTP_USER','HV_SMTP_PASSWORD','HV_SMTP_FROM']
    if any(not env.get(key) for key in required):raise ValueError('Verified SMTP configuration is incomplete')
    def send(message):
        message['From']=env['HV_SMTP_FROM']
        del message['X-HV-Swim-Draft']
        from email.utils import parseaddr
        domain=parseaddr(env['HV_SMTP_FROM'])[1].rsplit('@',1)[-1]
        if not domain or '.' not in domain: raise ValueError('A verified sender address is required')
        message.replace_header('Message-ID',str(message['Message-ID']).replace('@hvswim.local>',f'@{domain}>'))
        with smtplib.SMTP_SSL(env['HV_SMTP_HOST'],int(env.get('HV_SMTP_PORT','465')),timeout=20,context=ssl.create_default_context()) as smtp:
            smtp.login(env['HV_SMTP_USER'],env['HV_SMTP_PASSWORD'])
            refused=smtp.send_message(message)
            if refused:raise smtplib.SMTPRecipientsRefused(refused)
    return send
