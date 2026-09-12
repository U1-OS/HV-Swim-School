"""Synthetic staff self-service security and management planning regressions."""
import base64
import json
from datetime import timedelta

import pytest

from test_api import client, sign_in, STAFF, ADMIN, FAMILY, make_test_png_base64
from test_workforce import principal, insert_shift


def owner(client):
    client.cookies.clear()
    return {'X-CSRF-Token': sign_in(client, ADMIN)}


def resume(client, ident):
    from backend.database import db_session
    with db_session() as db:
        email = db.execute('SELECT email FROM users WHERE id=?', (ident,)).fetchone()[0]
    client.cookies.clear()
    return {'X-CSRF-Token': sign_in(client, (email, STAFF[1]))}


def future(days=10):
    from backend.security import business_today
    return (business_today() + timedelta(days=days)).isoformat()


def shift(staff, days=10, **changes):
    return dict(staff_id=staff, location_slug='wood-street', shift_date=future(days),
                start_time='09:00', end_time='11:00', role_label='Instructor', **changes)


def document(**changes):
    return dict(category='medical', title='Synthetic private record', original_filename='certificate.png',
                document_media_type='image/png', document_base64=make_test_png_base64(), **changes)


@pytest.mark.parametrize('scope', ['none', 'manager'])
def test_staff_boundary_denies_operations_and_privilege_changes(client, scope):
    ident, headers = principal(client, scope=scope)
    denied_get = ['/api/staff/swimmers', '/api/staff/incidents', '/api/staff/merchandise',
                  '/api/staff/classes', '/api/admin/metrics', '/api/management/roster',
                  '/api/management/leave', '/api/management/documents', '/api/staff/support-tickets']
    for path in denied_get:
        response = client.get(path)
        assert response.status_code in (403,404), (path,response.text)
    for path in ['/api/staff/time-entries', '/api/staff/qualifications', '/api/staff/skill-progress',
                 '/api/workforce/entries/1/review', '/api/workforce/entries/1/correct',
                 '/api/management/roster', '/api/staff/incidents']:
        assert client.post(path, json={}, headers=headers).status_code == 403, path
    for path in ['/api/account/profile','/api/account/sessions','/api/workforce/portal',
                 '/api/workforce/roster','/api/workforce/leave','/api/workforce/documents']:
        response = client.get(path)
        assert response.status_code == 200, (path,response.text)
    people=client.get('/api/workforce/people').json()
    assert people['can_review'] is False
    assert {r['id'] for r in people['staff']} == {ident}
    bad=client.patch('/api/account/profile',json={'first_name':'Changed','role':'admin'},headers=headers)
    assert bad.status_code == 422


def test_roster_publish_revisions_ownership_overlap_and_clock_separation(client):
    from backend.database import db_session
    worker, _ = principal(client)
    other, _ = principal(client)
    clock=insert_shift(worker,'2026-08-03T00:00:00+00:00','2026-08-03T01:00:00+00:00')
    with db_session() as db:
        before=dict(db.execute('SELECT * FROM time_entries WHERE id=?',(clock,)).fetchone())
    headers=owner(client); payload=shift(worker)
    response=client.post('/api/management/roster',json=payload,headers=headers)
    assert response.status_code == 200,response.text
    row=response.json()['shift']; path=f"/api/management/roster/{row['id']}"
    resume(client,worker)
    assert client.get('/api/workforce/roster').json()['roster'] == []
    assert client.post(path+'/publish',json={'revision':0},headers=resume(client,worker)).status_code == 403
    headers=owner(client)
    assert client.post(path+'/publish',json={'revision':0},headers=headers).json()['shift']['revision'] == 1
    assert client.patch(path,json=payload|{'revision':0,'status':'published'},headers=headers).status_code == 409
    assert client.post('/api/management/roster',json=payload|{'status':'published','location_slug':'bendigo-east'},headers=headers).status_code == 409
    adjacent=client.post('/api/management/roster',json=payload|{'status':'published','start_time':'11:00','end_time':'12:00'},headers=headers)
    assert adjacent.status_code == 200,adjacent.text
    assert client.patch(path,json=payload|{'revision':1,'status':'published','end_time':'11:30'},headers=headers).status_code == 409
    resume(client,worker)
    assert {r['staff_id'] for r in client.get('/api/workforce/roster').json()['roster']} == {worker}
    resume(client,other)
    assert client.get('/api/workforce/roster').json()['roster'] == []
    headers=owner(client)
    assert client.post(path+'/cancel',json={'revision':1},headers=headers).json()['shift']['status'] == 'cancelled'
    assert client.patch(path,json=payload|{'revision':2},headers=headers).status_code == 409
    assert client.post('/api/admin/roster',json=payload,headers=headers).status_code == 410
    assert client.patch(f"/api/admin/roster/{row['id']}",json=payload,headers=headers).status_code == 410
    with db_session() as db:
        assert dict(db.execute('SELECT * FROM time_entries WHERE id=?',(clock,)).fetchone()) == before


def test_leave_ownership_encryption_decisions_and_roster_blocking(client):
    from backend.database import db_session
    worker, headers=principal(client)
    payload={'leave_type':'personal','start_date':future(20),'end_date':future(21),'private_note':'Synthetic confidential medical narrative'}
    response=client.post('/api/workforce/leave',json=payload,headers=headers)
    assert response.status_code == 200,response.text
    row=response.json()['request']; ident=row['id']
    assert client.post('/api/workforce/leave',json=payload,headers=headers).status_code == 409
    other, their=principal(client)
    assert client.get('/api/workforce/leave').json()['requests'] == []
    assert client.post(f'/api/workforce/leave/{ident}/cancel',json={'revision':0},headers=their).status_code == 404
    headers=owner(client)
    planned=client.post('/api/management/roster',json=shift(worker,20,status='published'),headers=headers).json()['shift']
    decision=f'/api/management/leave/{ident}/decision'
    assert client.post(decision,json={'revision':0,'status':'approved'},headers=headers).status_code == 409
    listed=next(r for r in client.get('/api/management/leave').json()['requests'] if r['id']==ident)
    assert listed['roster_conflicts'][0]['id'] == planned['id']
    assert client.post(f"/api/management/roster/{planned['id']}/cancel",json={'revision':0},headers=headers).status_code == 200
    assert client.post(decision,json={'revision':0,'status':'approved','review_note':'Synthetic private decision'},headers=headers).status_code == 200
    assert client.post(decision,json={'revision':0,'status':'declined'},headers=headers).status_code == 409
    assert client.post('/api/management/roster',json=shift(worker,21,status='published'),headers=headers).status_code == 409
    draft=client.post('/api/management/roster',json=shift(worker,21),headers=headers).json()['shift']
    assert client.post(f"/api/management/roster/{draft['id']}/publish",json={'revision':0},headers=headers).status_code == 409
    headers=resume(client,worker)
    assert client.post(f'/api/workforce/leave/{ident}/cancel',json={'revision':1},headers=headers).status_code == 409
    assert client.get('/api/workforce/leave').json()['requests'][0]['private_note'] == payload['private_note']
    with db_session() as db:
        record=db.execute('SELECT * FROM staff_leave_requests WHERE id=?',(ident,)).fetchone()
        assert record['private_note'].startswith('enc:v1:') and record['review_note'].startswith('enc:v1:')
        audit_text=json.dumps([dict(r) for r in db.execute("SELECT * FROM audit_log WHERE entity_type='staff_leave' AND entity_id=?",(str(ident),))])
        assert payload['private_note'] not in audit_text and 'Synthetic private decision' not in audit_text


def test_leave_withdrawal_and_admin_cannot_review_self(client):
    worker,headers=principal(client)
    payload={'leave_type':'annual','start_date':future(30),'end_date':future(31)}
    row=client.post('/api/workforce/leave',json=payload,headers=headers).json()['request']
    path=f"/api/workforce/leave/{row['id']}/cancel"
    assert client.post(path,json={'revision':1},headers=headers).status_code == 409
    assert client.post(path,json={'revision':0},headers=headers).json()['status'] == 'cancelled'
    assert client.post(path,json={'revision':1},headers=headers).status_code == 409
    ident,headers=principal(client,role='admin')
    row=client.post('/api/workforce/leave',json=payload,headers=headers).json()['request']
    assert client.post(f"/api/management/leave/{row['id']}/decision",json={'revision':0,'status':'approved'},headers=headers).status_code == 403


def test_private_documents_encrypted_ownership_review_and_integrity(client):
    from backend.database import db_session
    from backend import config
    worker,headers=principal(client)
    payload=document(coverage_start=future(),coverage_end=future(11),expiry_date=future(365))
    response=client.post('/api/workforce/documents',json=payload,headers=headers)
    assert response.status_code == 200,response.text
    record=response.json()['document'];ident=record['id'];url=record['download_url']
    assert 'storage_filename' not in record and 'sha256' not in record
    binary=base64.b64decode(payload['document_base64'])
    downloaded=client.get(url)
    assert downloaded.status_code == 200 and downloaded.content == binary
    assert downloaded.headers['content-disposition'].startswith('attachment;')
    assert downloaded.headers['x-content-type-options'] == 'nosniff'
    assert downloaded.headers['cache-control'] == 'private, no-store'
    assert 'sandbox' in downloaded.headers['content-security-policy']
    with db_session() as db:
        stored=db.execute('SELECT * FROM staff_documents WHERE id=?',(ident,)).fetchone()
        path=config.DATA_DIR/'staff-documents'/stored['storage_filename']
        assert stored['title'].startswith('enc:v1:') and stored['original_filename'].startswith('enc:v1:')
        assert path.read_bytes().startswith(b'HVFILE1') and binary not in path.read_bytes()
        assert path.stat().st_mode & 0o077 == 0
    other,their=principal(client)
    assert client.get(url).status_code == 404
    assert client.get('/api/workforce/documents').json()['documents'] == []
    owner_headers=owner(client)
    assert client.get(f'/api/management/documents/{ident}/download').content == binary
    review=f'/api/management/documents/{ident}/review'
    assert client.post(review,json={'revision':0,'status':'accepted','review_note':'Checked privately'},headers=owner_headers).status_code == 200
    assert client.post(review,json={'revision':0,'status':'rejected'},headers=owner_headers).status_code == 409
    resume(client,worker)
    assert client.get('/api/workforce/documents').json()['documents'][0]['status'] == 'accepted'
    path.write_bytes(path.read_bytes()[:-1]+b'X')
    assert client.get(url).status_code == 409
    client.cookies.clear();sign_in(client,FAMILY)
    for route in [url,f'/api/management/documents/{ident}/download','/api/workforce/documents','/api/workforce/leave','/api/workforce/roster']:
        assert client.get(route).status_code == 403
    client.cookies.clear()
    assert client.get(url).status_code == 401


def test_document_upload_validation_size_paths_and_link_ownership(client):
    from backend.database import db_session
    from backend import config
    worker,headers=principal(client)
    payload=document()
    assert client.post('/api/workforce/documents',json=payload).status_code == 403
    for changes in [{'document_media_type':'image/svg+xml'}, {'document_base64':'!'*32},
                    {'coverage_start':future()}, {'coverage_start':future(11),'coverage_end':future(10)},
                    {'original_filename':'evil\nfilename.png'}, {'staff_id':999999}, {'category':'unknown'}]:
        assert client.post('/api/workforce/documents',json=payload|changes,headers=headers).status_code == 422,changes
    large=client.post('/api/workforce/documents',json=payload|{'document_base64':'A'*2_100_000},headers=headers)
    assert large.status_code == 422 and 'selected type' in large.text
    oversized=base64.b64encode(b'x'*5_000_001).decode()
    assert client.post('/api/workforce/documents',json=payload|{'document_base64':oversized},headers=headers).status_code == 413
    assert client.post('/api/workforce/documents',content=b'x'*7_100_001,headers=headers).status_code == 413
    assert client.post('/api/workforce/leave',content=b'x'*2_000_001,headers=headers).status_code == 413
    leave=client.post('/api/workforce/leave',json={'leave_type':'other','start_date':future(),'end_date':future()},headers=headers).json()['request']
    other,their=principal(client)
    assert client.post('/api/workforce/documents',json=payload|{'leave_request_id':leave['id']},headers=their).status_code == 404
    saved=client.post('/api/workforce/documents',json=payload|{'original_filename':'../../certificate.png'},headers=their).json()['document']
    assert saved['original_filename']=='certificate.png'
    with db_session() as db:
        db.execute('UPDATE staff_documents SET storage_filename=? WHERE id=?',('../outside',saved['id']))
    assert client.get(saved['download_url']).status_code == 409


def test_past_draft_cannot_publish_and_migration_is_idempotent(client):
    from backend.database import db_session
    from backend import staff_portal
    worker,_=principal(client);headers=owner(client)
    row=client.post('/api/management/roster',json=shift(worker),headers=headers).json()['shift']
    with db_session() as db:
        db.execute("UPDATE rosters SET shift_date='2000-01-01' WHERE id=?",(row['id'],))
    assert client.post(f"/api/management/roster/{row['id']}/publish",json={'revision':0},headers=headers).status_code == 409
    staff_portal.migrate();staff_portal.migrate()
    with db_session() as db:
        assert db.execute('SELECT id FROM rosters WHERE id=?',(row['id'],)).fetchone()


def test_document_self_review_quota_and_symlink_fail_closed(client):
    from backend.database import db_session
    from backend import config
    ident,headers=principal(client,role='admin')
    saved=client.post('/api/workforce/documents',json=document(),headers=headers).json()['document']
    assert client.post(f"/api/management/documents/{saved['id']}/review",json={'revision':0,'status':'accepted'},headers=headers).status_code == 403
    with db_session() as db:
        record=db.execute('SELECT * FROM staff_documents WHERE id=?',(saved['id'],)).fetchone()
        path=config.DATA_DIR/'staff-documents'/record['storage_filename']
        other=config.DATA_DIR/'synthetic-not-a-document'
        other.write_text('Synthetic forbidden file')
        path.unlink();path.symlink_to(other)
        db.execute('UPDATE staff_documents SET byte_count=200000000 WHERE id=?',(saved['id'],))
    assert client.get(saved['download_url']).status_code == 404
    assert client.post('/api/workforce/documents',json=document(),headers=headers).status_code == 409
    assert other.read_text() == 'Synthetic forbidden file'


def test_concurrent_roster_changes_cannot_overwrite_each_other(client):
    from concurrent.futures import ThreadPoolExecutor
    worker,_=principal(client);headers=owner(client);payload=shift(worker,40)
    row=client.post('/api/management/roster',json=payload,headers=headers).json()['shift']
    def update(label):
        return client.patch(f"/api/management/roster/{row['id']}",json=payload|{'revision':0,'role_label':label},headers=headers).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(update,['First update','Second update'])) == [200,409]


def test_profile_updates_stay_own_and_file_name_collision_preserves_existing(client,monkeypatch):
    from backend.database import db_session
    from backend import config,staff_portal
    worker,headers=principal(client)
    updated=client.patch('/api/account/profile',json={'first_name':'Own profile','last_name':'Synthetic','phone':'0400000000'},headers=headers)
    assert updated.status_code == 200,updated.text
    with db_session() as db:
        assert db.execute('SELECT first_name FROM users WHERE id=?',(worker,)).fetchone()[0] == 'Own profile'
    monkeypatch.setattr(staff_portal,'new_token',lambda length:'A'*32)
    saved=client.post('/api/workforce/documents',json=document(),headers=headers).json()['document']
    path=config.DATA_DIR/'staff-documents'/('A'*32+'.hvdoc');original=path.read_bytes()
    # The same exclusive path must not be overwritten or removed during cleanup.
    assert client.post('/api/workforce/documents',json=document(),headers=headers).status_code == 409
    assert path.read_bytes() == original
    assert client.get(saved['download_url']).status_code == 200


def test_shift_notice_owned_private_revisioned_and_does_not_edit_roster(client):
    from backend.database import db_session
    worker, _=principal(client)
    other, _=principal(client)
    headers=owner(client)
    created=client.post('/api/management/roster',json=shift(worker,status='published'),headers=headers)
    assert created.status_code==200,created.text
    roster=created.json()['shift']
    payload={'roster_id':roster['id'],'kind':'unavailable','private_note':'Synthetic confidential absence note'}
    assert client.post('/api/workforce/shift-notices',json=payload,headers=resume(client,other)).status_code==404
    headers=resume(client,worker)
    assert client.post('/api/workforce/shift-notices',json=payload).status_code==403
    response=client.post('/api/workforce/shift-notices',json=payload,headers=headers)
    assert response.status_code==200,response.text
    ident=response.json()['id']
    assert client.post('/api/workforce/shift-notices',json=payload,headers=headers).status_code==409
    assert client.get('/api/workforce/shift-notices').json()['notices'][0]['private_note']==payload['private_note']
    with db_session() as db:
        assert payload['private_note'] not in db.execute('SELECT private_note FROM staff_shift_notices WHERE id=?',(ident,)).fetchone()[0]
    review=f'/api/management/shift-notices/{ident}/review'
    assert client.post(review,json={'revision':0,'status':'resolved','review_note':'Arrange cover'},headers=headers).status_code==403
    resume(client,other)
    assert client.get('/api/workforce/shift-notices').json()['notices']==[]
    headers=owner(client)
    decision={'revision':0,'status':'acknowledged','review_note':'Management will arrange cover'}
    assert client.post(review,json=decision,headers=headers).status_code==200
    assert client.post(review,json=decision,headers=headers).status_code==409
    with db_session() as db:
        assert dict(db.execute('SELECT * FROM rosters WHERE id=?',(roster['id'],)).fetchone())==roster
    client.cookies.clear();sign_in(client,FAMILY)
    assert client.get('/api/workforce/shift-notices').status_code==403
    assert client.get('/api/management/shift-notices').status_code==403
