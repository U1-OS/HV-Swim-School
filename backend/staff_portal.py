"""Private staff self-service, dated rosters, leave and encrypted document records.

Rosters describe planned work. This module never writes actual clock entries or payroll.
"""
from __future__ import annotations

import hashlib
import os
import stat
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import config
from .database import audit, db_session, rows
from .security import (
    business_today, decrypt_private_file, decrypt_sensitive, encrypt_private_file,
    encrypt_sensitive, new_token, now_iso,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS staff_leave_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  staff_id INTEGER NOT NULL REFERENCES users(id),
  leave_type TEXT NOT NULL CHECK (leave_type IN ('annual','personal','unpaid','other')),
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  private_note TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','declined','cancelled')),
  revision INTEGER NOT NULL DEFAULT 0,
  reviewed_by INTEGER REFERENCES users(id),
  review_note TEXT,
  reviewed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (end_date>=start_date)
);
CREATE INDEX IF NOT EXISTS idx_staff_leave_dates ON staff_leave_requests(staff_id,start_date,end_date,status);
CREATE TABLE IF NOT EXISTS staff_documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  staff_id INTEGER NOT NULL REFERENCES users(id),
  category TEXT NOT NULL CHECK (category IN ('medical','professional','other')),
  title TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  storage_filename TEXT NOT NULL UNIQUE,
  media_type TEXT NOT NULL,
  byte_count INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  coverage_start TEXT,
  coverage_end TEXT,
  expiry_date TEXT,
  leave_request_id INTEGER REFERENCES staff_leave_requests(id),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','rejected')),
  revision INTEGER NOT NULL DEFAULT 0,
  reviewed_by INTEGER REFERENCES users(id),
  review_note TEXT,
  reviewed_at TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_staff_documents_owner ON staff_documents(staff_id,created_at);
"""

# These apply to EVERY staff account, including a legacy assigned-team manager. GET
# hours remain self-only in workforce.scope_ids. Unlisted mutations are denied before
# the handler receives private data or reaches an external provider.
STAFF_EXACT = {
    'GET': {
        '/api/auth/me', '/api/account/profile', '/api/account/sessions',
        '/api/workforce/portal', '/api/workforce/roster', '/api/workforce/leave', '/api/workforce/shift-notices',
        '/api/workforce/documents', '/api/workforce/shift', '/api/workforce/report',
        '/api/workforce/people', '/api/staff/roster', '/api/staff/time-entries',
        '/api/staff/qualifications', '/api/notifications',
    },
    'PATCH': {'/api/account/profile'},
    'POST': {
        '/api/auth/logout', '/api/auth/change-password', '/api/account/revoke-other-sessions',
        '/api/account/mfa/setup', '/api/account/mfa/confirm', '/api/account/mfa/disable',
        '/api/workforce/clock', '/api/staff/clock', '/api/workforce/leave',
        '/api/workforce/documents', '/api/workforce/shift-notices',
    },
}
STAFF_PATTERNS = {
    'GET': (r'/api/workforce/documents/[1-9][0-9]*/download',
            r'/api/staff/qualifications/[1-9][0-9]*/document',
            r'/api/workforce/entries/[1-9][0-9]*/history'),
    'POST': (r'/api/workforce/leave/[1-9][0-9]*/cancel',
             r'/api/notifications/[1-9][0-9]*/read'),
}


def enforce_staff_capability(user, method, path):
    if user['role'] != 'staff':
        return
    if path in STAFF_EXACT.get(method, ()):
        return
    if any(re.fullmatch(pattern, path) for pattern in STAFF_PATTERNS.get(method, ())):
        return
    raise HTTPException(403, 'Staff access is limited to your own details, work hours, roster, leave and documents')


def migrate():
    with db_session() as db:
        db.executescript(SCHEMA)
        columns = {row['name'] for row in db.execute('PRAGMA table_info(rosters)')}
        for name, definition in {
            'revision': 'INTEGER NOT NULL DEFAULT 0',
            'created_by': 'INTEGER REFERENCES users(id)',
            'updated_at': 'TEXT',
            'published_at': 'TEXT',
        }.items():
            if name not in columns:
                db.execute(f'ALTER TABLE rosters ADD COLUMN {name} {definition}')


def employee(user):
    if user['role'] not in ('staff', 'admin'):
        raise HTTPException(403, 'Staff account required')


def management(user):
    if user['role'] != 'admin':
        raise HTTPException(403, 'Management access required')


def current_revision(record, revision):
    if record['revision'] != revision:
        raise HTTPException(409, 'This record changed. Reload before saving again')


def window(start, end):
    start = start or business_today()
    end = end or start + timedelta(days=90)
    if end < start or (end-start).days > 366:
        raise HTTPException(422, 'Choose a date range of no more than 366 days')
    return start.isoformat(), end.isoformat()


class RosterInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    staff_id: int = Field(gt=0)
    location_slug: str = Field(min_length=1, max_length=80)
    shift_date: date
    start_time: str = Field(pattern=r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
    end_time: str = Field(pattern=r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
    role_label: str = Field(default='Instructor', min_length=1, max_length=100)
    status: Literal['draft', 'published'] = 'draft'

    @model_validator(mode='after')
    def valid_times(self):
        if self.end_time <= self.start_time:
            raise ValueError('Finish must be after start on the same date')
        if not business_today() <= self.shift_date <= business_today()+timedelta(days=730):
            raise ValueError('Choose a roster date within the next two years')
        return self


class RosterUpdate(RosterInput):
    revision: int = Field(ge=0)


class RevisionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0)


class LeaveInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    leave_type: Literal['annual', 'personal', 'unpaid', 'other']
    start_date: date
    end_date: date
    private_note: str = Field(default='', max_length=1200)

    @model_validator(mode='after')
    def valid_dates(self):
        if self.end_date < self.start_date or (self.end_date-self.start_date).days > 366:
            raise ValueError('Choose a leave period of no more than 366 days')
        if self.start_date < business_today()-timedelta(days=31) or self.end_date > business_today()+timedelta(days=730):
            raise ValueError('Older leave requires direct management review; future leave is limited to two years')
        return self


class LeaveDecision(RevisionInput):
    status: Literal['approved', 'declined', 'cancelled']
    review_note: str = Field(default='', max_length=1200)


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    category: Literal['medical', 'professional', 'other']
    title: str = Field(min_length=2, max_length=120)
    original_filename: str = Field(min_length=1, max_length=180)
    document_media_type: Literal['application/pdf', 'image/png', 'image/jpeg']
    document_base64: str = Field(min_length=20, max_length=6_666_668)
    coverage_start: date | None = None
    coverage_end: date | None = None
    expiry_date: date | None = None
    leave_request_id: int | None = Field(default=None, gt=0)

    @model_validator(mode='after')
    def valid_metadata(self):
        self.original_filename = Path(self.original_filename.replace('\\', '/')).name.strip()
        if not self.original_filename or any(ord(c)<32 or ord(c)==127 for c in self.original_filename):
            raise ValueError('Enter a valid document filename')
        if (self.coverage_start is None) != (self.coverage_end is None):
            raise ValueError('Enter both document coverage dates')
        if self.coverage_start and self.coverage_end < self.coverage_start:
            raise ValueError('Coverage end must be on or after its start')
        return self


class DocumentDecision(RevisionInput):
    status: Literal['accepted', 'rejected']
    review_note: str = Field(default='', max_length=1200)


def roster_rows(db, start, end, staff_id=None, published_only=False):
    where = 'r.shift_date>=? AND r.shift_date<=?'
    params = [start, end]
    if staff_id is not None:
        where += ' AND r.staff_id=?'
        params.append(staff_id)
    if published_only:
        where += " AND r.status='published'"
    return rows(db.execute(f'''SELECT r.*,l.name location_name,l.slug location_slug,
        u.first_name,u.last_name FROM rosters r JOIN locations l ON l.id=r.location_id
        JOIN users u ON u.id=r.staff_id WHERE {where} ORDER BY r.shift_date,r.start_time,r.id''', params))


def roster_record(db, ident):
    return db.execute('SELECT * FROM rosters WHERE id=?', (ident,)).fetchone()


def validate_roster(db, payload, excluding_id=0):
    if not db.execute("SELECT id FROM users WHERE id=? AND active=1 AND role IN ('staff','admin')", (payload.staff_id,)).fetchone():
        raise HTTPException(404, 'Active staff member not found')
    location = db.execute('SELECT id FROM locations WHERE slug=?', (payload.location_slug,)).fetchone()
    if not location:
        raise HTTPException(404, 'Work location not found')
    if payload.status == 'published':
        if db.execute("""SELECT id FROM rosters WHERE staff_id=? AND shift_date=? AND id<>?
            AND status='published' AND start_time<? AND end_time>? LIMIT 1""",
            (payload.staff_id, payload.shift_date.isoformat(), excluding_id, payload.end_time, payload.start_time)).fetchone():
            raise HTTPException(409, 'This published shift overlaps another shift for this person')
        if db.execute("""SELECT id FROM staff_leave_requests WHERE staff_id=? AND status='approved'
            AND start_date<=? AND end_date>=? LIMIT 1""",
            (payload.staff_id, payload.shift_date.isoformat(), payload.shift_date.isoformat())).fetchone():
            raise HTTPException(409, 'Approved leave covers this date. Resolve the leave before publishing a shift')
    return location['id']


def save_roster(db, user, payload, ident=None):
    db.execute('BEGIN IMMEDIATE')
    previous = roster_record(db, ident) if ident else None
    if ident:
        if not previous:
            raise HTTPException(404, 'Roster shift not found')
        current_revision(previous, payload.revision)
        if previous['shift_date'] < business_today().isoformat() or previous['status']=='cancelled':
            raise HTTPException(409, 'Past and cancelled roster records are preserved')
    location_id = validate_roster(db, payload, ident or 0)
    at = now_iso()
    published_at = at if payload.status=='published' else None
    values = (payload.staff_id, location_id, payload.shift_date.isoformat(), payload.start_time,
              payload.end_time, payload.role_label, payload.status, at, published_at)
    if previous:
        db.execute('''UPDATE rosters SET staff_id=?,location_id=?,shift_date=?,start_time=?,end_time=?,
            role_label=?,status=?,updated_at=?,published_at=?,revision=revision+1 WHERE id=? AND revision=?''',
            (*values, ident, payload.revision))
    else:
        ident = db.execute('''INSERT INTO rosters(staff_id,location_id,shift_date,start_time,end_time,
            role_label,status,updated_at,published_at,created_by) VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (*values, user['id'])).lastrowid
    audit(db, user['id'], 'update_staff_roster' if previous else 'create_staff_roster', 'roster', ident,
          {'staff_id':payload.staff_id, 'shift_date':payload.shift_date.isoformat(), 'status':payload.status})
    return dict(roster_record(db, ident))


def leave_rows(db, staff_id=None):
    records = rows(db.execute('''SELECT r.*,u.first_name,u.last_name FROM staff_leave_requests r
        JOIN users u ON u.id=r.staff_id ''' + ('WHERE r.staff_id=? ' if staff_id is not None else '') +
        'ORDER BY r.created_at DESC,r.id DESC LIMIT 200', (staff_id,) if staff_id is not None else ()))
    for record in records:
        record['private_note'] = decrypt_sensitive(record['private_note']) or ''
        record['review_note'] = decrypt_sensitive(record['review_note']) or ''
        record['roster_conflicts'] = rows(db.execute("""SELECT id,shift_date,start_time,end_time FROM rosters
            WHERE staff_id=? AND status='published' AND shift_date>=? AND shift_date<=? ORDER BY shift_date,start_time""",
            (record['staff_id'], record['start_date'], record['end_date'])))
    return records


def document_rows(db, staff_id=None):
    records = rows(db.execute('''SELECT d.id,d.staff_id,d.category,d.title,d.original_filename,
        d.media_type,d.byte_count,d.coverage_start,d.coverage_end,d.expiry_date,d.leave_request_id,
        d.status,d.revision,d.reviewed_by,d.review_note,d.reviewed_at,d.created_at,u.first_name,u.last_name
        FROM staff_documents d JOIN users u ON u.id=d.staff_id ''' +
        ('WHERE d.staff_id=? ' if staff_id is not None else '') + 'ORDER BY d.created_at DESC,d.id DESC LIMIT 200',
        (staff_id,) if staff_id is not None else ()))
    for record in records:
        for field in ('title', 'original_filename', 'review_note'):
            record[field] = decrypt_sensitive(record[field]) or ''
        prefix = 'workforce' if staff_id is not None else 'management'
        record['download_url'] = f'/api/{prefix}/documents/{record["id"]}/download'
    return records


def document_directory():
    directory = config.DATA_DIR / 'staff-documents'
    if directory.is_symlink():
        raise HTTPException(503, 'Private document storage is unavailable')
    return directory


def document_path(filename):
    if not re.fullmatch(r'[A-Za-z0-9_-]{32}\.hvdoc', filename or ''):
        raise HTTPException(409, 'Document storage reference is invalid')
    path = document_directory() / filename
    if path.is_symlink() or not path.is_file():
        raise HTTPException(404, 'Document file not found')
    return path


def private_document_bytes(filename):
    # Hold the directory and file descriptors, so a swapped symlink cannot redirect
    # a private download outside storage between validation and the read.
    document_path(filename)
    directory_fd = None
    descriptor = None
    try:
        directory_fd = os.open(document_directory(), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptor = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 5_100_000:
            raise HTTPException(409, 'Document file failed its integrity check')
        with os.fdopen(descriptor, 'rb') as source:
            descriptor = None
            return source.read(5_100_001)
    except OSError as exc:
        raise HTTPException(404, 'Document file not found') from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory_fd is not None:
            os.close(directory_fd)


def register(app, session_user, csrf_guard, validate_upload):
    @app.get('/api/workforce/roster')
    def own_roster(start: date | None = None, end: date | None = None, user=Depends(session_user)):
        employee(user)
        bounds = window(start, end)
        with db_session() as db:
            return {'roster':roster_rows(db, *bounds, user['id'], True), 'start':bounds[0], 'end':bounds[1], 'read_only':True}

    @app.get('/api/management/roster')
    def management_roster(start: date | None = None, end: date | None = None, user=Depends(session_user)):
        management(user)
        bounds = window(start, end)
        with db_session() as db:
            return {'roster':roster_rows(db,*bounds), 'start':bounds[0], 'end':bounds[1],
                    'staff':rows(db.execute("SELECT id,first_name,last_name,staff_number FROM users WHERE role IN ('staff','admin') AND active=1 ORDER BY first_name,last_name")),
                    'locations':rows(db.execute('SELECT id,name,slug FROM locations ORDER BY name'))}

    @app.post('/api/management/roster')
    def create_roster(payload: RosterInput, request: Request, user=Depends(session_user), x_csrf_token: str | None=Header(default=None)):
        management(user); csrf_guard(request,user,x_csrf_token)
        with db_session() as db:
            return {'shift':save_roster(db,user,payload)}

    @app.patch('/api/management/roster/{ident}')
    def update_roster(ident: int, payload: RosterUpdate, request: Request, user=Depends(session_user), x_csrf_token: str | None=Header(default=None)):
        management(user); csrf_guard(request,user,x_csrf_token)
        with db_session() as db:
            return {'shift':save_roster(db,user,payload,ident)}

    @app.post('/api/management/roster/{ident}/publish')
    def publish_roster(ident: int, payload: RevisionInput, request: Request, user=Depends(session_user), x_csrf_token: str | None=Header(default=None)):
        management(user); csrf_guard(request,user,x_csrf_token)
        with db_session() as db:
            db.execute('BEGIN IMMEDIATE')
            record=roster_record(db,ident)
            if not record: raise HTTPException(404,'Roster shift not found')
            current_revision(record,payload.revision)
            if record['status']!='draft': raise HTTPException(409,'Only a draft shift can be published')
            if record['shift_date'] < business_today().isoformat(): raise HTTPException(409,'Past roster records are preserved')
            slug=db.execute('SELECT slug FROM locations WHERE id=?',(record['location_id'],)).fetchone()['slug']
            values={k:record[k] for k in ('staff_id','shift_date','start_time','end_time','role_label')}
            values.update(location_slug=slug,status='published',revision=payload.revision)
            # The transaction is already locked; avoid a nested SQLite BEGIN.
            update=RosterUpdate(**values)
            validate_roster(db,update,ident)
            at=now_iso()
            db.execute("UPDATE rosters SET status='published',published_at=?,updated_at=?,revision=revision+1 WHERE id=?",(at,at,ident))
            audit(db,user['id'],'publish_staff_roster','roster',ident,{'revision':payload.revision+1})
            return {'shift':dict(roster_record(db,ident))}

    @app.post('/api/management/roster/{ident}/cancel')
    def cancel_roster(ident: int, payload: RevisionInput, request: Request, user=Depends(session_user), x_csrf_token: str | None=Header(default=None)):
        management(user); csrf_guard(request,user,x_csrf_token)
        with db_session() as db:
            db.execute('BEGIN IMMEDIATE');record=roster_record(db,ident)
            if not record: raise HTTPException(404,'Roster shift not found')
            current_revision(record,payload.revision)
            if record['status']=='cancelled' or record['shift_date']<business_today().isoformat():
                raise HTTPException(409,'Past and cancelled roster records are preserved')
            db.execute("UPDATE rosters SET status='cancelled',updated_at=?,revision=revision+1 WHERE id=?",(now_iso(),ident))
            audit(db,user['id'],'cancel_staff_roster','roster',ident,{'revision':payload.revision+1})
            return {'shift':dict(roster_record(db,ident))}

    @app.get('/api/workforce/leave')
    def own_leave(user=Depends(session_user)):
        employee(user)
        with db_session() as db: return {'requests':leave_rows(db,user['id'])}

    @app.get('/api/management/leave')
    def management_leave(user=Depends(session_user)):
        management(user)
        with db_session() as db: return {'requests':leave_rows(db)}

    @app.post('/api/workforce/leave')
    def create_leave(payload: LeaveInput, request: Request, user=Depends(session_user), x_csrf_token: str | None=Header(default=None)):
        employee(user); csrf_guard(request,user,x_csrf_token)
        with db_session() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("""SELECT id FROM staff_leave_requests WHERE staff_id=? AND status IN ('pending','approved')
                AND start_date<=? AND end_date>=? LIMIT 1""",(user['id'],payload.end_date.isoformat(),payload.start_date.isoformat())).fetchone():
                raise HTTPException(409,'An active leave request already covers these dates')
            at=now_iso()
            ident=db.execute('''INSERT INTO staff_leave_requests(staff_id,leave_type,start_date,end_date,private_note,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?)''',(user['id'],payload.leave_type,payload.start_date.isoformat(),payload.end_date.isoformat(),encrypt_sensitive(payload.private_note),at,at)).lastrowid
            audit(db,user['id'],'request_staff_leave','staff_leave',ident,{'start_date':payload.start_date.isoformat(),'end_date':payload.end_date.isoformat()})
            return {'request':next(r for r in leave_rows(db,user['id']) if r['id']==ident)}

    @app.post('/api/workforce/leave/{ident}/cancel')
    def cancel_leave(ident: int, payload: RevisionInput, request: Request, user=Depends(session_user), x_csrf_token: str | None=Header(default=None)):
        employee(user); csrf_guard(request,user,x_csrf_token)
        with db_session() as db:
            db.execute('BEGIN IMMEDIATE')
            record=db.execute('SELECT * FROM staff_leave_requests WHERE id=? AND staff_id=?',(ident,user['id'])).fetchone()
            if not record: raise HTTPException(404,'Leave request not found')
            current_revision(record,payload.revision)
            if record['status']!='pending': raise HTTPException(409,'Only pending requests can be withdrawn; contact management about approved leave')
            db.execute("UPDATE staff_leave_requests SET status='cancelled',updated_at=?,revision=revision+1 WHERE id=?",(now_iso(),ident))
            audit(db,user['id'],'withdraw_staff_leave','staff_leave',ident,{'revision':payload.revision+1})
            return {'saved':True,'id':ident,'status':'cancelled','revision':payload.revision+1}

    @app.post('/api/management/leave/{ident}/decision')
    def decide_leave(ident: int, payload: LeaveDecision, request: Request, user=Depends(session_user), x_csrf_token: str | None=Header(default=None)):
        management(user); csrf_guard(request,user,x_csrf_token)
        with db_session() as db:
            db.execute('BEGIN IMMEDIATE');record=db.execute('SELECT * FROM staff_leave_requests WHERE id=?',(ident,)).fetchone()
            if not record: raise HTTPException(404,'Leave request not found')
            current_revision(record,payload.revision)
            if record['staff_id']==user['id']: raise HTTPException(403,'Another manager must review your leave')
            if record['status']!='pending' and not (record['status']=='approved' and payload.status=='cancelled'):
                raise HTTPException(409,'This request has already been decided')
            if payload.status=='approved' and db.execute("""SELECT id FROM rosters WHERE staff_id=? AND status='published'
                AND shift_date>=? AND shift_date<=? LIMIT 1""",(record['staff_id'],record['start_date'],record['end_date'])).fetchone():
                raise HTTPException(409,'Published shifts overlap this leave. Cancel or reassign them before approval')
            at=now_iso()
            db.execute('''UPDATE staff_leave_requests SET status=?,review_note=?,reviewed_by=?,reviewed_at=?,updated_at=?,revision=revision+1 WHERE id=?''',
                       (payload.status,encrypt_sensitive(payload.review_note),user['id'],at,at,ident))
            audit(db,user['id'],'review_staff_leave','staff_leave',ident,{'status':payload.status,'revision':payload.revision+1})
            return {'saved':True,'id':ident,'status':payload.status,'revision':payload.revision+1}

    @app.get('/api/workforce/documents')
    def own_documents(user=Depends(session_user)):
        employee(user)
        with db_session() as db: return {'documents':document_rows(db,user['id'])}

    @app.get('/api/management/documents')
    def management_documents(user=Depends(session_user)):
        management(user)
        with db_session() as db: return {'documents':document_rows(db)}

    @app.post('/api/workforce/documents')
    def upload_document(payload: DocumentInput, request: Request, user=Depends(session_user), x_csrf_token: str | None=Header(default=None)):
        employee(user); csrf_guard(request,user,x_csrf_token)
        document,_,digest=validate_upload(payload.document_base64,payload.document_media_type)
        filename=f'{new_token(24)}.hvdoc'; directory=document_directory()
        directory.mkdir(mode=0o700,parents=True,exist_ok=True)
        path=directory/filename
        created=False
        try:
            with db_session() as db:
                db.execute('BEGIN IMMEDIATE')
                if payload.leave_request_id and not db.execute('SELECT id FROM staff_leave_requests WHERE id=? AND staff_id=?',(payload.leave_request_id,user['id'])).fetchone():
                    raise HTTPException(404,'Your leave request was not found')
                usage=db.execute('SELECT COUNT(*) total,COALESCE(SUM(byte_count),0) bytes FROM staff_documents WHERE staff_id=?',(user['id'],)).fetchone()
                if usage['total']>=200 or usage['bytes']+len(document)>200_000_000:
                    raise HTTPException(409,'Your document storage limit has been reached; contact management')
                # Persist only ciphertext, with an exclusive private file creation.
                descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                created=True
                with os.fdopen(descriptor,'wb') as output: output.write(encrypt_private_file(document))
                at=now_iso()
                ident=db.execute('''INSERT INTO staff_documents(staff_id,category,title,original_filename,storage_filename,media_type,
                    byte_count,sha256,coverage_start,coverage_end,expiry_date,leave_request_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (user['id'],payload.category,encrypt_sensitive(payload.title),encrypt_sensitive(payload.original_filename),filename,
                     payload.document_media_type,len(document),digest,payload.coverage_start.isoformat() if payload.coverage_start else None,
                     payload.coverage_end.isoformat() if payload.coverage_end else None,payload.expiry_date.isoformat() if payload.expiry_date else None,
                     payload.leave_request_id,at)).lastrowid
                audit(db,user['id'],'upload_staff_document','staff_document',ident,{'category':payload.category,'byte_count':len(document)})
                return {'document':next(d for d in document_rows(db,user['id']) if d['id']==ident)}
        except Exception as exc:
            if created: path.unlink(missing_ok=True)
            if isinstance(exc, FileExistsError):
                raise HTTPException(409, 'Please retry this document upload') from exc
            if isinstance(exc, OSError):
                raise HTTPException(503, 'Private document storage is unavailable') from exc
            raise

    def download(ident,user,manager=False):
        management(user) if manager else employee(user)
        with db_session() as db:
            record=db.execute('SELECT * FROM staff_documents WHERE id=?',(ident,)).fetchone()
            if not record or (not manager and record['staff_id']!=user['id']): raise HTTPException(404,'Document not found')
            ciphertext=private_document_bytes(record['storage_filename'])
            try: document=decrypt_private_file(ciphertext)
            except (ValueError,RuntimeError) as exc: raise HTTPException(409,'Document file failed its integrity check') from exc
            if len(document)!=record['byte_count'] or hashlib.sha256(document).hexdigest()!=record['sha256']:
                raise HTTPException(409,'Document file failed its integrity check')
            filename=decrypt_sensitive(record['original_filename'])
            audit(db,user['id'],'download_staff_document','staff_document',ident)
            return Response(document,media_type=record['media_type'],headers={
                'Content-Disposition':"attachment; filename*=UTF-8''"+quote(filename,safe=''),
                'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"sandbox; default-src 'none'"})

    @app.get('/api/workforce/documents/{ident}/download')
    def own_download(ident:int,user=Depends(session_user)): return download(ident,user)

    @app.get('/api/management/documents/{ident}/download')
    def management_download(ident:int,user=Depends(session_user)): return download(ident,user,True)

    @app.post('/api/management/documents/{ident}/review')
    def review_document(ident:int,payload:DocumentDecision,request:Request,user=Depends(session_user),x_csrf_token:str|None=Header(default=None)):
        management(user);csrf_guard(request,user,x_csrf_token)
        with db_session() as db:
            db.execute('BEGIN IMMEDIATE');record=db.execute('SELECT * FROM staff_documents WHERE id=?',(ident,)).fetchone()
            if not record:raise HTTPException(404,'Document not found')
            current_revision(record,payload.revision)
            if record['staff_id']==user['id']:raise HTTPException(403,'Another manager must review your document')
            if record['status']!='pending':raise HTTPException(409,'This document has already been reviewed')
            db.execute('''UPDATE staff_documents SET status=?,review_note=?,reviewed_by=?,reviewed_at=?,revision=revision+1 WHERE id=?''',
                       (payload.status,encrypt_sensitive(payload.review_note),user['id'],now_iso(),ident))
            audit(db,user['id'],'review_staff_document','staff_document',ident,{'status':payload.status,'revision':payload.revision+1})
            return {'saved':True,'id':ident,'status':payload.status,'revision':payload.revision+1}

    @app.get('/api/workforce/portal')
    def portal(user=Depends(session_user)):
        employee(user);bounds=window(None,None)
        with db_session() as db:
            return {'profile':{key:user.get(key) for key in ('id','first_name','last_name','email','phone','staff_number')},
                    'roster':roster_rows(db,*bounds,user['id'],True),'leave':leave_rows(db,user['id']),
                    'documents':document_rows(db,user['id']), 'locations':rows(db.execute('SELECT id,name,slug FROM locations ORDER BY name')),
                    'capabilities':['profile','clock','own_hours','own_roster','leave','documents'],
                    'timezone':'Australia/Melbourne','roster_read_only':True}
