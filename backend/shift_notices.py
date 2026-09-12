"""Owned absence / unavailable-shift notices. Never mutates roster or payroll."""
from datetime import timedelta
from typing import Literal
from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from .database import db_session, audit, rows
from .security import business_today, now_iso, encrypt_sensitive, decrypt_sensitive

SCHEMA = '''
CREATE TABLE IF NOT EXISTS staff_shift_notices (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 staff_id INTEGER NOT NULL REFERENCES users(id),
 roster_id INTEGER NOT NULL REFERENCES rosters(id),
 shift_date TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
 location_name TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('absent','unavailable')),
 private_note TEXT, status TEXT NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','acknowledged','resolved')),
 revision INTEGER NOT NULL DEFAULT 0,
 review_note TEXT, reviewed_by INTEGER REFERENCES users(id),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shift_notices_owner ON staff_shift_notices(staff_id,status);
'''

def migrate():
    with db_session() as db: db.executescript(SCHEMA)

class NoticeInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    roster_id: int=Field(gt=0)
    kind: Literal['absent','unavailable']
    private_note: str=Field(default='',max_length=1200)

class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    revision: int=Field(ge=0)
    status: Literal['acknowledged','resolved']
    review_note: str=Field(min_length=3,max_length=1200)

def require(user, admin=False):
    if user['role'] not in (('admin',) if admin else ('admin','staff')):
        raise HTTPException(403,'This is a private staff record')

def listing(user):
    with db_session() as db:
        items=rows(db.execute('''SELECT n.*,u.first_name,u.last_name FROM staff_shift_notices n
            JOIN users u ON u.id=n.staff_id '''+('WHERE n.staff_id=? ' if user['role']=='staff' else '')+
            'ORDER BY n.created_at DESC LIMIT 500',(user['id'],) if user['role']=='staff' else ()))
        for row in items:
            for key in ('private_note','review_note'):row[key]=decrypt_sensitive(row[key]) if row[key] else ''
        return {'notices':items,'changes_roster':False}

def register(app, session_user, csrf_guard):
    @app.get('/api/workforce/shift-notices')
    def own(user=Depends(session_user)):
        require(user)
        return listing(user)

    @app.get('/api/management/shift-notices')
    def all_notices(user=Depends(session_user)):
        require(user,True)
        return listing(user)

    @app.post('/api/workforce/shift-notices')
    def create(payload:NoticeInput,request:Request,user=Depends(session_user),x_csrf_token:str|None=Header(default=None)):
        require(user);csrf_guard(request,user,x_csrf_token)
        with db_session() as db:
            db.execute('BEGIN IMMEDIATE')
            shift=db.execute('''SELECT r.*,l.name location_name FROM rosters r JOIN locations l ON l.id=r.location_id
                WHERE r.id=? AND r.staff_id=? AND r.status='published' ''',(payload.roster_id,user['id'])).fetchone()
            if not shift:raise HTTPException(404,'Published shift not found in your roster')
            if shift['shift_date']<(business_today()-timedelta(days=7)).isoformat():
                raise HTTPException(422,'Contact management directly about older shifts')
            if db.execute("SELECT id FROM staff_shift_notices WHERE roster_id=? AND staff_id=? AND status<>'resolved'",(payload.roster_id,user['id'])).fetchone():
                raise HTTPException(409,'A notice for this shift is already awaiting resolution')
            at=now_iso()
            ident=db.execute('''INSERT INTO staff_shift_notices(staff_id,roster_id,shift_date,start_time,end_time,location_name,kind,private_note,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)''',(user['id'],shift['id'],shift['shift_date'],shift['start_time'],shift['end_time'],shift['location_name'],payload.kind,encrypt_sensitive(payload.private_note),at,at)).lastrowid
            audit(db,user['id'],'create_shift_notice','staff_shift_notice',ident,{'roster_id':shift['id'],'kind':payload.kind})
        return {'id':ident,'status':'pending','changes_roster':False}

    @app.post('/api/management/shift-notices/{ident}/review')
    def review(ident:int,payload:Decision,request:Request,user=Depends(session_user),x_csrf_token:str|None=Header(default=None)):
        require(user,True);csrf_guard(request,user,x_csrf_token)
        with db_session() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM staff_shift_notices WHERE id=?',(ident,)).fetchone()
            if not row:raise HTTPException(404,'Notice not found')
            if row['staff_id']==user['id']:raise HTTPException(403,'Another manager must review your notice')
            if row['revision']!=payload.revision or row['status']=='resolved':raise HTTPException(409,'This notice changed. Reload before reviewing')
            db.execute('''UPDATE staff_shift_notices SET status=?,review_note=?,reviewed_by=?,updated_at=?,revision=revision+1 WHERE id=?''',
                (payload.status,encrypt_sensitive(payload.review_note),user['id'],now_iso(),ident))
            audit(db,user['id'],'review_shift_notice','staff_shift_notice',ident,{'status':payload.status})
        return {'id':ident,'status':payload.status,'revision':payload.revision+1,'changes_roster':False}
