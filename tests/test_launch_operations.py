"""Local-only operational and adversarial contracts; no provider is contacted."""
from datetime import date,datetime,timedelta,timezone
from contextlib import contextmanager
import sqlite3,smtplib
import pytest
from test_api import client,sign_in,ADMIN,FAMILY,STAFF
from backend import lesson_calendar,mail_queue

@pytest.fixture
def calendar_db():
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
    db.executescript('''CREATE TABLE locations(id INTEGER PRIMARY KEY,name TEXT,slug TEXT);
    CREATE TABLE users(id INTEGER PRIMARY KEY,first_name TEXT,last_name TEXT);
    CREATE TABLE classes(id INTEGER PRIMARY KEY,location_id INTEGER,instructor_id INTEGER,active INTEGER,weekday INTEGER,start_time TEXT);
    CREATE TABLE school_terms(id INTEGER PRIMARY KEY,status TEXT,start_date TEXT,end_date TEXT);
    INSERT INTO locations VALUES(1,'Test pool','test'); INSERT INTO users VALUES(1,'Test','Teacher');
    INSERT INTO classes VALUES(1,1,1,1,0,'09:00');
    INSERT INTO school_terms VALUES(1,'active','2030-01-01','2030-03-01');''')
    db.executescript(lesson_calendar.SCHEMA)
    yield db
    db.close()

def test_closure_and_cancellation_remove_effective_occurrences(calendar_db):
    db=calendar_db
    assert len(lesson_calendar.on_date(db,'2030-01-07'))==1
    db.execute("INSERT INTO calendar_closures VALUES(1,'2030-01-07','2030-01-07',NULL,'Test closure',1,'now')")
    assert lesson_calendar.on_date(db,'2030-01-07')==[]
    db.execute("INSERT INTO lesson_exceptions VALUES(1,1,'2030-01-14','cancel',NULL,NULL,'Test cancel',1,'now')")
    assert lesson_calendar.on_date(db,'2030-01-14')==[]
    assert lesson_calendar.next_occurrence(db,1,datetime.fromisoformat('2030-01-06T09:00:00+11:00'))['occurrence_date']=='2030-01-21'

def test_moved_lesson_outside_term_keeps_original_identity(calendar_db):
    db=calendar_db
    db.execute("INSERT INTO lesson_exceptions VALUES(1,1,'2030-02-25','move','2030-03-02','11:30','Test move',1,'now')")
    assert lesson_calendar.on_date(db,'2030-02-25')==[]
    moved=lesson_calendar.on_date(db,'2030-03-02')[0]
    assert (moved['original_date'],moved['start_time'],moved['rescheduled'])==('2030-02-25','11:30',True)
    assert lesson_calendar.on_date(db,'2030-03-02',instructor_id=999)==[]
    assert any(x['occurrence_date']=='2030-03-02' for x in lesson_calendar.dates_for_class(db,1,date(2030,2,25)))

@pytest.fixture
def outbox(tmp_path):
    path=tmp_path/'mail.db'
    @contextmanager
    def session():
        db=sqlite3.connect(path);db.row_factory=sqlite3.Row
        try:
            yield db;db.commit()
        except Exception:db.rollback();raise
        finally:db.close()
    with session() as db:db.executescript(mail_queue.SCHEMA)
    return session

def queue_one(session):
    with session() as db:
        mail_queue.enqueue(db,'acknowledgement','HV-ENQ-0001','fictional@example.test','test:1')
        mail_queue.enqueue(db,'acknowledgement','HV-ENQ-0001','fictional@example.test','test:1')
        assert db.execute('SELECT COUNT(*) FROM mail_outbox').fetchone()[0]==1
        row=db.execute('SELECT * FROM mail_outbox').fetchone()
        assert 'fictional@example.test' not in row['encrypted_payload']
        db.execute("UPDATE mail_outbox SET status='queued'")

def test_mail_capture_is_deduplicated_private_and_not_resent(outbox,tmp_path):
    queue_one(outbox)
    assert mail_queue.process_one(outbox,capture_dir=tmp_path/'capture')['status']=='captured'
    assert mail_queue.process_one(outbox,capture_dir=tmp_path/'capture') is None
    saved=tmp_path/'capture/mail-1.eml'
    assert saved.stat().st_mode&0o777==0o600
    assert b'local-preview-only' in saved.read_bytes()

@pytest.mark.parametrize('error,status',[(smtplib.SMTPDataError(451,b'temporary'),'retry'),(smtplib.SMTPDataError(550,b'permanent'),'failed'),(OSError('disconnect'),'uncertain')])
def test_mail_failure_states_do_not_claim_delivery(outbox,error,status):
    queue_one(outbox)
    def transport(_):raise error
    assert mail_queue.process_one(outbox,transport=transport)['status']==status
    assert mail_queue.process_one(outbox,transport=transport) is None

def test_worker_crash_requires_reconciliation(outbox):
    queue_one(outbox)
    with outbox() as db:
        db.execute("UPDATE mail_outbox SET status='processing',claimed_at=?",((datetime.now(timezone.utc)-timedelta(minutes=11)).isoformat(),))
    assert mail_queue.process_one(outbox,transport=lambda _:pytest.fail('Must not retry an uncertain send')) is None
    with outbox() as db:assert db.execute('SELECT status FROM mail_outbox').fetchone()[0]=='uncertain'

def test_live_email_is_locked_without_explicit_approval():
    with pytest.raises(ValueError,match='approval'):mail_queue.smtp_transport({})
    with pytest.raises(ValueError,match='incomplete'):mail_queue.smtp_transport({'HV_APP_ENV':'production','HV_EMAIL_LIVE_APPROVED':'true'})

@pytest.mark.parametrize('path',['/api/admin/calendar','/api/admin/mail','/api/admin/launch-readiness'])
def test_new_operations_are_role_protected(client,path):
    client.cookies.clear();assert client.get(path).status_code==401
    for creds in (FAMILY,STAFF):
        sign_in(client,creds);assert client.get(path).status_code==403
    sign_in(client,ADMIN);assert client.get(path).status_code==200

def test_launch_evidence_csrf_expiry_and_no_activation(client):
    from backend.server import business_today
    token=sign_in(client,ADMIN)
    value={'reference':'Synthetic owner review reference','expires_on':(business_today()+timedelta(days=10)).isoformat()}
    assert client.put('/api/admin/launch-readiness/domain',json=value).status_code==403
    headers={'X-CSRF-Token':token}
    assert client.put('/api/admin/launch-readiness/domain',json=value,headers=headers).status_code==200
    report=client.get('/api/admin/launch-readiness').json()
    assert not report['launch_authorised'] and not report['ready_for_launch_review']
    assert next(c for c in report['checks'] if c['key']=='domain')['ready']
    assert client.put('/api/admin/launch-readiness/unknown',json=value,headers=headers).status_code==404
    assert client.put('/api/admin/launch-readiness/domain',json=value|{'expires_on':'2000-01-01'},headers=headers).status_code==422

def test_calendar_changes_validate_overlap_history_and_csrf(client):
    from backend.server import business_today
    token=sign_in(client,ADMIN);headers={'X-CSRF-Token':token}
    future=(business_today()+timedelta(days=200)).isoformat()
    payload={'start_date':future,'end_date':future,'reason':'Synthetic calendar closure'}
    assert client.post('/api/admin/calendar/closures',json=payload).status_code==403
    result=client.post('/api/admin/calendar/closures',json=payload,headers=headers)
    assert result.status_code==200,result.text
    assert client.post('/api/admin/calendar/closures',json=payload,headers=headers).status_code==409
    assert client.post('/api/admin/calendar/closures',json=payload|{'start_date':'2000-01-01'},headers=headers).status_code==422
    assert client.delete(f"/api/admin/calendar/closures/{result.json()['id']}",headers=headers).status_code==200

def test_uncertain_mail_cannot_be_blindly_queued(client):
    from backend.database import db_session
    token=sign_in(client,ADMIN);headers={'X-CSRF-Token':token}
    with db_session() as db:
        mail_queue.enqueue(db,'acknowledgement','HV-ENQ-0999','fictional@example.test','uncertain-api-test')
        row=db.execute("SELECT id FROM mail_outbox WHERE dedupe_key='uncertain-api-test'").fetchone();ident=row[0]
        db.execute("UPDATE mail_outbox SET status='uncertain' WHERE id=?",(ident,))
    route=f'/api/admin/mail/{ident}/review';reason='Synthetic provider reconciliation'
    assert client.post(route,json={'action':'queue','reason':reason},headers=headers).status_code==409
    assert client.post(route,json={'action':'confirm_not_sent','reason':reason}).status_code==403
    assert client.post(route,json={'action':'confirm_not_sent','reason':reason},headers=headers).status_code==200
    public=client.get('/api/admin/mail').text
    assert 'fictional@example.test' not in public and 'encrypted_payload' not in public


def test_account_email_cannot_bypass_live_approval(monkeypatch):
    from backend import identity
    from dataclasses import replace
    for key in ('HV_SMTP_HOST','HV_SMTP_USER','HV_SMTP_PASSWORD','HV_SMTP_FROM'):monkeypatch.setenv(key,'synthetic')
    monkeypatch.delenv('HV_EMAIL_LIVE_APPROVED',raising=False)
    monkeypatch.setattr(identity,'settings',replace(identity.settings,app_env='production'))
    monkeypatch.setattr(smtplib,'SMTP_SSL',lambda *a,**k:pytest.fail('Must not contact SMTP'))
    assert not identity.deliver_link('fictional@example.test','https://example.test/#secret','invite')


def test_oauth_callback_cannot_transfer_to_another_browser(client,monkeypatch):
    from backend import server
    from test_api import _oauth_start
    client.cookies.clear();state=_oauth_start(client,monkeypatch,server,'google')
    client.cookies.clear()  # Callback opened in a different browser with no binding cookie.
    monkeypatch.setattr(server,'oauth_exchange_code',lambda *a,**k:pytest.fail('Unbound callback must not contact provider'))
    result=client.get(f'/api/auth/oauth/google/callback?state={state}&code=synthetic',follow_redirects=False)
    assert result.headers['location'].endswith('oauth_error=browser_mismatch')
    assert client.get('/api/auth/me').status_code==401


def test_safeguarding_report_is_not_automatically_disclosed_to_family(client):
    from backend.database import db_session
    token=sign_in(client,ADMIN)
    with db_session() as db:
        swimmer=db.execute("SELECT s.id FROM swimmers s JOIN users u ON u.id=s.customer_id WHERE u.email=? ORDER BY s.id",(FAMILY[0],)).fetchone()[0]
    payload={'swimmer_id':swimmer,'location_slug':'wood-street','incident_at':datetime.now(timezone.utc).isoformat(),'incident_type':'safeguarding','what_happened':'Synthetic protected concern for testing','injury_observed':'None observed','first_aid_applied':'Not required','further_action':'Management review requested','witnesses':'Synthetic witness identity','parent_notified':False}
    result=client.post('/api/staff/incidents',json=payload,headers={'X-CSRF-Token':token})
    assert result.status_code==200,result.text
    ident=result.json()['id'];assert result.json()['family_notification']=='withheld_for_safeguarding_review'
    sign_in(client,FAMILY)
    assert all(row['id']!=ident for row in client.get('/api/customer/incidents').json()['reports'])
    assert result.json()['reference'] not in client.get('/api/notifications').text


def test_enquiry_requires_collection_acknowledgement(client):
    from backend.server import EnquiryInput
    from pydantic import ValidationError
    with pytest.raises(ValidationError,match='acknowledge'):
        EnquiryInput(name='Synthetic Parent',email='fictional@example.com')


def test_chunked_request_stops_reading_at_size_limit():
    import asyncio
    from starlette.requests import Request
    from backend import server
    received=[]
    async def receive():
        received.append(1)
        assert len(received)<=3,'Request should stop reading once the body limit is exceeded'
        return {'type':'http.request','body':b'x'*(server.DEFAULT_API_BODY_LIMIT//2+1),'more_body':True}
    request=Request({'type':'http','http_version':'1.1','method':'POST','scheme':'http','path':'/api/auth/login','raw_path':b'/api/auth/login','query_string':b'','headers':[(b'host',b'testserver')],'client':('127.0.0.1',1),'server':('testserver',80)},receive)
    async def next_handler(_):pytest.fail('Oversized body must not reach authentication')
    response=asyncio.run(server.security_headers(request,next_handler))
    assert response.status_code==413 and len(received)==2
