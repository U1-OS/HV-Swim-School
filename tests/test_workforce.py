"""Isolated integrated workforce and identity regressions. Never contacts providers."""

import csv
import io
import json
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from xml.etree import ElementTree

import pytest
from fastapi import HTTPException

from test_api import client, sign_in, ADMIN, STAFF, FAMILY


def test_security_proofs_rate_limited_and_disabled_invites_revoked(client):
    owner = {"X-CSRF-Token": sign_in(client, ADMIN)}
    invitation = client.post(
        "/api/account/invitations",
        headers=owner,
        json={
            "email": "pending-qa@example.com",
            "first_name": "Invitation QA",
            "role": "staff",
        },
    )
    assert invitation.status_code == 200, invitation.text
    token = invitation.json()["link"].split("=")[-1]
    from backend.database import db_session

    with db_session() as db:
        ident = db.execute(
            "SELECT id FROM users WHERE email='pending-qa@example.com'"
        ).fetchone()[0]
    assert (
        client.patch(
            f"/api/admin/accounts/{ident}/status", headers=owner, json={"active": False}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/redeem",
            json={"token": token, "password": "SamplePasswordOnly!26"},
        ).status_code
        == 400
    )
    for _ in range(10):
        assert (
            client.post(
                "/api/account/mfa/setup",
                headers=owner,
                json={"password": "WrongOnlyPassword!"},
            ).status_code
            == 403
        )
    assert (
        client.post(
            "/api/account/mfa/setup",
            headers=owner,
            json={"password": "WrongOnlyPassword!"},
        ).status_code
        == 429
    )


def test_unsupported_database_url_fails_closed(client):
    from dataclasses import replace
    from backend.config import settings
    from backend.server import validate_production_config

    with pytest.raises(RuntimeError, match="supported PostgreSQL"):
        validate_production_config(
            replace(settings, database_url="mysql://not-a-real-database")
        )


def test_rejection_resubmission_and_self_approval_guard(client):
    staff, headers = principal(client)
    ident = insert_shift(
        staff, "2026-08-03T00:00:00+00:00", "2026-08-03T01:00:00+00:00"
    )
    client.cookies.clear()
    owner = {"X-CSRF-Token": sign_in(client, ADMIN)}
    response = client.post(
        f"/api/workforce/entries/{ident}/review",
        headers=owner,
        json={"action": "reject", "reason": "Check finishing time", "version": 1},
    )
    assert response.status_code == 200, response.text
    from backend.database import db_session

    with db_session() as db:
        email = db.execute("SELECT email FROM users WHERE id=?", (staff,)).fetchone()[0]
    client.cookies.clear()
    headers = {"X-CSRF-Token": sign_in(client, (email, STAFF[1]))}
    assert (
        client.post(
            f"/api/workforce/entries/{ident}/review",
            headers=headers,
            json={
                "action": "resubmit",
                "reason": "Confirmed finishing time",
                "version": 1,
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/workforce/entries/{ident}/review",
            headers=headers,
            json={
                "action": "approve",
                "reason": "Self approval attempted",
                "version": 1,
            },
        ).status_code
        == 403
    )


def principal(client, *, role="staff", scope="none"):
    from backend.database import db_session

    email = f"qa-{uuid.uuid4().hex}@example.com"
    with db_session() as db:
        hashed = db.execute(
            "SELECT password_hash FROM users WHERE email=?", (STAFF[0],)
        ).fetchone()[0]
        ident = db.execute(
            "INSERT INTO users(email,password_hash,role,first_name,last_name,created_at,management_scope) VALUES(?,?,?,'QA','Worker',?,?)",
            (email, hashed, role, datetime.now(timezone.utc).isoformat(), scope),
        ).lastrowid
        db.execute(
            "UPDATE users SET staff_number=? WHERE id=?", (f"HVS-W-{ident:06d}", ident)
        )
    client.cookies.clear()
    csrf = sign_in(client, (email, STAFF[1]))
    return ident, {"X-CSRF-Token": csrf}


def insert_shift(
    staff, start, finish, *, status="submitted", seconds=None, origin="clock"
):
    from backend.database import db_session
    from backend.workforce import stamp, TZ, duration

    with db_session() as db:
        a, b = stamp(start), stamp(finish)
        day = a.astimezone(TZ).date()
        seconds = duration(a, b) if seconds is None else seconds
        ident = db.execute(
            "INSERT INTO time_entries(staff_id,location_id,clock_in,clock_out,worked_seconds,elapsed_seconds,hours,origin,status,review_state,work_date,week_start) VALUES(?,1,?,?,?,?,?,?,?,?,?,?)",
            (
                staff,
                start,
                finish,
                seconds,
                duration(a, b),
                seconds / 3600,
                origin,
                status,
                status,
                day.isoformat(),
                (day - timedelta(days=day.weekday())).isoformat(),
            ),
        ).lastrowid
    return ident


def test_clock_exact_breaks_retries_restart_and_auto_submission(client, monkeypatch):
    from backend import workforce
    from backend.database import db_session

    staff, headers = principal(client)
    at = datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(workforce, "now", lambda: at)
    payload = {
        "action": "in",
        "location_slug": "wood-street",
        "request_id": uuid.uuid4().hex,
    }
    first = client.post("/api/workforce/clock", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    ident = first.json()["entry_id"]
    assert client.post("/api/workforce/clock", json=payload, headers=headers).json()[
        "replayed"
    ]
    assert (
        client.post(
            "/api/workforce/clock", json=payload | {"action": "out"}, headers=headers
        ).status_code
        == 409
    )
    at += timedelta(seconds=30)
    assert (
        client.post(
            "/api/workforce/clock",
            json={
                "action": "break_start",
                "entry_id": ident,
                "paid_break": False,
                "request_id": uuid.uuid4().hex,
            },
            headers=headers,
        ).status_code
        == 200
    )
    at += timedelta(seconds=17)
    assert (
        client.post(
            "/api/workforce/clock",
            json={
                "action": "break_end",
                "entry_id": ident,
                "request_id": uuid.uuid4().hex,
            },
            headers=headers,
        ).status_code
        == 200
    )
    at += timedelta(seconds=10)
    assert (
        client.post(
            "/api/workforce/clock",
            json={
                "action": "break_start",
                "entry_id": ident,
                "paid_break": True,
                "request_id": uuid.uuid4().hex,
            },
            headers=headers,
        ).status_code
        == 200
    )
    at += timedelta(seconds=9)
    finish = {"action": "out", "entry_id": ident, "request_id": uuid.uuid4().hex}
    result = client.post("/api/workforce/clock", json=finish, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["worked_seconds"] == 49 and result.json()["submitted"]
    workforce.migrate()  # restart migration preserves both ledger and idempotency response
    assert client.post("/api/workforce/clock", json=finish, headers=headers).json()[
        "replayed"
    ]
    with db_session() as db:
        row = db.execute("SELECT * FROM time_entries WHERE id=?", (ident,)).fetchone()
        assert (
            row["unpaid_seconds"] == 17
            and row["paid_break_seconds"] == 9
            and row["status"] == "submitted"
        )
        assert (
            db.execute(
                "SELECT COUNT(*) FROM time_entries WHERE staff_id=?", (staff,)
            ).fetchone()[0]
            == 1
        )
    assert client.get("/api/workforce/shift").json()["entry"] is None


def test_database_concurrent_start_only_one_shift(client):
    from backend.database import db_session
    from backend.workforce import clock_action, ClockAction

    staff, _ = principal(client)

    def start(_):
        with db_session() as db:
            return clock_action(
                db, {"id": staff}, ClockAction(action="in", request_id=uuid.uuid4().hex)
            )["entry_id"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(start, range(8)))
    assert len(set(ids)) == 1


@pytest.mark.parametrize(
    "start,finish,expected",
    [
        ("2026-04-05T01:30:00+11:00", "2026-04-05T03:30:00+10:00", 10800),
        ("2026-10-04T01:30:00+10:00", "2026-10-04T03:30:00+11:00", 3600),
    ],
)
def test_dst_exact_duration(client, start, finish, expected):
    staff, _ = principal(client)
    insert_shift(staff, start, finish)
    result = client.get(
        "/api/workforce/report", params={"period": "daily", "on": start[:10]}
    ).json()
    assert result["totals"]["worked_seconds"] == expected


def test_overnight_period_split_and_break_allocation(client):
    from backend.database import db_session

    staff, _ = principal(client)
    entry = insert_shift(
        staff, "2026-08-31T23:30:00+10:00", "2026-09-01T01:00:00+10:00"
    )
    with db_session() as db:
        db.execute(
            "INSERT INTO shift_breaks(entry_id,started_at,ended_at,paid,actor_id) VALUES(?, '2026-08-31T23:55:00+10:00','2026-09-01T00:10:00+10:00',0,?)",
            (entry, staff),
        )
    august = client.get(
        "/api/workforce/report", params={"period": "monthly", "on": "2026-08-01"}
    ).json()
    september = client.get(
        "/api/workforce/report", params={"period": "monthly", "on": "2026-09-01"}
    ).json()
    assert august["totals"]["worked_seconds"] == 1500
    assert september["totals"]["worked_seconds"] == 3000
    assert (
        august["totals"]["unpaid_break_seconds"]
        + september["totals"]["unpaid_break_seconds"]
        == 900
    )


def test_complete_queries_exact_small_shifts_and_settings(client):
    staff, _ = principal(client)
    for second in range(130):
        start = datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc) + timedelta(
            seconds=second * 2
        )
        insert_shift(
            staff, start.isoformat(), (start + timedelta(seconds=1)).isoformat()
        )
    result = client.get(
        "/api/workforce/report", params={"period": "daily", "on": "2026-07-06"}
    ).json()
    assert (
        result["totals"]["shift_count"] == 130
        and result["totals"]["worked_seconds"] == 130
    )
    client.cookies.clear()
    headers = {"X-CSRF-Token": sign_in(client, ADMIN)}
    response = client.patch(
        "/api/workforce/settings",
        json={
            "week_start": 6,
            "fortnight_anchor": "2026-01-04",
            "long_shift_hours": 12,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    r = client.get(
        "/api/workforce/report", params={"period": "weekly", "on": "2026-07-06"}
    ).json()
    assert r["start"] == "2026-07-05"
    r = client.get(
        "/api/workforce/report", params={"period": "fortnightly", "on": "2026-01-03"}
    ).json()
    assert r["start"] == "2025-12-21"


def test_manual_weekly_not_silently_prorated(client):
    from backend.database import db_session

    staff, headers = principal(client)
    result = client.post(
        "/api/staff/time-entries",
        json={
            "week_start": "2026-06-29",
            "location_slug": "wood-street",
            "entry_mode": "weekly",
            "total_hours": 12.5,
        },
        headers=headers,
    )
    assert result.status_code == 200, result.text
    report = client.get(
        "/api/workforce/report", params={"period": "monthly", "on": "2026-07-01"}
    ).json()
    assert report["issues"] and report["totals"]["worked_seconds"] == 0
    report = client.get(
        "/api/workforce/report",
        params={"period": "custom", "start": "2026-06-29", "end": "2026-07-05"},
    ).json()
    assert report["totals"]["worked_seconds"] == 45000


def test_manual_totals_cannot_duplicate_overnight_or_previous_week_clock(client):
    worker, headers = principal(client)
    insert_shift(worker, "2026-08-02T23:00:00+10:00", "2026-08-03T01:00:00+10:00")
    daily = {
        "week_start": "2026-08-03",
        "location_slug": "wood-street",
        "entry_mode": "daily",
        "daily_entries": [{"work_date": "2026-08-03", "hours": 1}],
    }
    weekly = {
        "week_start": "2026-08-03",
        "location_slug": "wood-street",
        "entry_mode": "weekly",
        "total_hours": 10,
    }
    for payload in (daily, weekly):
        result = client.post("/api/staff/time-entries", headers=headers, json=payload)
        assert result.status_code == 409, result.text
        assert "overlap" in result.json()["detail"]
    # Adjacent days are safe: an end at midnight does not occupy the next day.
    daily["daily_entries"][0]["work_date"] = "2026-08-04"
    result = client.post("/api/staff/time-entries", headers=headers, json=daily)
    assert result.status_code == 200, result.text
    # Editing this own draft remains possible without conflicting with itself.
    daily["daily_entries"][0]["hours"] = 2
    assert (
        client.post("/api/staff/time-entries", headers=headers, json=daily).status_code
        == 200
    )


def test_review_blocks_historical_overlaps_but_allows_adjacent_periods(client):
    from backend.database import db_session

    worker, _ = principal(client)
    clock = insert_shift(
        worker, "2026-08-02T23:00:00+10:00", "2026-08-03T01:00:00+10:00"
    )
    manual = insert_shift(
        worker,
        "2026-08-03T00:00:00+10:00",
        "2026-08-03T02:00:00+10:00",
        origin="manual",
    )
    adjacent = insert_shift(
        worker, "2026-08-01T23:00:00+10:00", "2026-08-02T00:00:00+10:00"
    )
    client.cookies.clear()
    owner = {"X-CSRF-Token": sign_in(client, ADMIN)}
    for ident in (clock, manual):
        result = client.post(
            f"/api/workforce/entries/{ident}/review",
            headers=owner,
            json={
                "action": "approve",
                "reason": "Review existing allocation",
                "version": 1,
            },
        )
        assert result.status_code == 409, result.text
    result = client.post(
        f"/api/workforce/entries/{adjacent}/review",
        headers=owner,
        json={"action": "approve", "reason": "Reviewed separate shift", "version": 1},
    )
    assert result.status_code == 200, result.text
    # Older approved data is checked again before it can enter a new export batch.
    with db_session() as db:
        db.execute(
            "UPDATE time_entries SET status='approved' WHERE id IN (?,?)",
            (clock, manual),
        )
    period = {"period": "weekly", "on": "2026-08-03", "staff_id": worker}
    preview = client.get("/api/workforce/export-preview", params=period)
    assert preview.status_code == 200, preview.text
    assert preview.json()["issues"]
    exported = client.post("/api/workforce/exports", headers=owner, json=period)
    assert exported.status_code == 409, exported.text


def test_manager_scope_self_approval_and_no_owner_access(client):
    from backend.database import db_session

    worker, _ = principal(client)
    unrelated, _ = principal(client)
    manager, headers = principal(client, scope="manager")
    own = insert_shift(
        manager, "2026-07-10T09:00:00+10:00", "2026-07-10T10:00:00+10:00"
    )
    allowed = insert_shift(
        worker, "2026-07-10T09:00:00+10:00", "2026-07-10T10:00:00+10:00"
    )
    denied = insert_shift(
        unrelated, "2026-07-10T09:00:00+10:00", "2026-07-10T10:00:00+10:00"
    )
    with db_session() as db:
        db.execute("INSERT INTO manager_assignments VALUES(?,?)", (manager, worker))
    payload = {"action": "approve", "version": 1, "reason": "Checked actual hours"}
    assert (
        client.post(
            f"/api/workforce/entries/{allowed}/review", json=payload, headers=headers
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/workforce/entries/{denied}/review", json=payload, headers=headers
        ).status_code
        == 404
    )
    assert client.post(
        f"/api/workforce/entries/{own}/review", json=payload, headers=headers
    ).status_code in (403, 404)
    assert client.get("/api/account/team").status_code == 403
    assert client.get("/api/admin/accounts").status_code == 403
    assert (
        client.get("/api/workforce/report", params={"staff_id": unrelated}).status_code
        == 403
    )
    client.cookies.clear()
    sign_in(client, FAMILY)
    assert client.get("/api/workforce/report").status_code == 403
    assert client.get(f"/api/workforce/entries/{allowed}/history").status_code == 403


def test_corrections_reapproval_export_immutability_and_files(client):
    from backend.database import db_session

    staff, _ = principal(client)
    entry = insert_shift(
        staff, "2026-06-10T09:00:00+10:00", "2026-06-10T10:00:00+10:00"
    )
    client.cookies.clear()
    headers = {"X-CSRF-Token": sign_in(client, ADMIN)}
    review = {"action": "approve", "version": 1, "reason": "Reviewed attendance"}
    assert (
        client.post(
            f"/api/workforce/entries/{entry}/review", json=review, headers=headers
        ).status_code
        == 200
    )
    correction = {
        "version": 1,
        "reason": "Corrected missed finish",
        "clock_in": "2026-06-10T09:00:00+10:00",
        "clock_out": "2026-06-10T11:00:00+10:00",
        "breaks": [
            {
                "started_at": "2026-06-10T10:00:00+10:00",
                "ended_at": "2026-06-10T10:15:00+10:00",
                "paid": False,
            }
        ],
    }
    assert (
        client.post(
            f"/api/workforce/entries/{entry}/correct", json=correction, headers=headers
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/workforce/entries/{entry}/review", json=review, headers=headers
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/workforce/entries/{entry}/review",
            json=review | {"version": 2},
            headers=headers,
        ).status_code
        == 200
    )
    period = {"period": "daily", "on": "2026-06-10", "staff_id": staff}
    result = client.post("/api/workforce/exports", json=period, headers=headers)
    assert result.status_code == 200, result.text
    batch = result.json()["batch_id"]
    assert result.json()["transmitted"] is False
    csv1 = client.get(f"/api/workforce/exports/{batch}.csv").content
    assert csv1 == client.get(f"/api/workforce/exports/{batch}.csv").content
    parsed = list(csv.reader(io.StringIO(csv1.decode("utf-8-sig"))))
    assert parsed[1][9] == "6300" and parsed[1][10] == "1.75"
    xlsx = client.get(f"/api/workforce/exports/{batch}.xlsx").content
    assert xlsx == client.get(f"/api/workforce/exports/{batch}.xlsx").content
    with zipfile.ZipFile(io.BytesIO(xlsx)) as z:
        assert z.testzip() is None
        for name in z.namelist():
            ElementTree.fromstring(z.read(name))
        assert b"6300" in z.read("xl/worksheets/sheet1.xml")
    assert (
        client.post("/api/workforce/exports", json=period, headers=headers).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/workforce/entries/{entry}/correct",
            json=correction | {"version": 2},
            headers=headers,
        ).status_code
        == 409
    )
    amendment = client.post(
        f"/api/workforce/entries/{entry}/amend",
        json={
            "work_date": "2026-06-10",
            "adjustment_seconds": -300,
            "reason": "Amend exported attendance correction",
        },
        headers=headers,
    )
    assert amendment.status_code == 200, amendment.text
    assert csv1 == client.get(f"/api/workforce/exports/{batch}.csv").content
    history = client.get(f"/api/workforce/entries/{entry}/history").json()["events"]
    assert any(
        e["action"] == "correct"
        and e["before"]["hours"] == 1
        and e["after"]["worked_seconds"] == 6300
        for e in history
    )
    with db_session() as db:
        with pytest.raises(Exception, match="immutable"):
            db.execute("DELETE FROM hour_export_batches WHERE id=?", (batch,))


def test_formula_injection_safe_and_xlsx_typed(client):
    from backend.workforce import safe_cell, workbook_bytes

    assert safe_cell(" =1+1") == "' =1+1" and safe_cell(-300) == -300
    snapshot = {
        "start": "2026-01-01",
        "end": "2026-01-01",
        "generated_at": "2026-01-02",
        "totals": {"approved_seconds": 1},
        "rows": [
            {
                "staff_name": '=HYPERLINK("https://invalid")',
                "approved_seconds": 1,
                "worked_seconds": 1,
            }
        ],
    }
    with zipfile.ZipFile(io.BytesIO(workbook_bytes(snapshot))) as z:
        xml = z.read("xl/worksheets/sheet1.xml")
        assert b"<f>" not in xml and b't="inlineStr"' in xml


def test_invitation_activation_token_replay_and_recovery(client, monkeypatch):
    from backend import identity
    from backend.database import db_session

    monkeypatch.setattr(identity, "email_configured", lambda: False)
    client.cookies.clear()
    headers = {"X-CSRF-Token": sign_in(client, ADMIN)}
    email = f"invited-{uuid.uuid4().hex}@example.com"
    result = client.post(
        "/api/account/invitations",
        json={"email": email, "first_name": "QA Invite", "role": "staff"},
        headers=headers,
    )
    assert result.status_code == 200, result.text
    token = result.json()["link"].split("=")[-1]
    ident = result.json()["account_id"]
    assert not result.json()["email_accepted"]
    with db_session() as db:
        assert not db.execute(
            "SELECT active FROM users WHERE id=?", (ident,)
        ).fetchone()[0]
        assert token not in str(
            [tuple(r) for r in db.execute("SELECT * FROM account_tokens")]
        )
    payload = {"token": token, "password": "UniqueLongPassword!123"}
    assert client.post("/api/auth/redeem", json=payload).status_code == 200
    assert client.post("/api/auth/redeem", json=payload).status_code == 400
    client.cookies.clear()
    sign_in(client, (email, payload["password"]))
    assert client.get("/api/account/profile").json()["email_verified_at"] is None
    assert (
        client.post(
            "/api/account/invitations",
            json={"email": "other@example.com", "first_name": "Other"},
        ).status_code
        == 403
    )
    for _ in range(5):
        assert (
            client.post("/api/auth/recovery", json={"email": email}).status_code == 200
        )
    assert client.post("/api/auth/recovery", json={"email": email}).status_code == 429


def test_mfa_login_replay_and_password_recovery_does_not_bypass(client, monkeypatch):
    from backend import identity
    from backend.database import db_session

    staff, headers = principal(client)
    password = STAFF[1]
    result = client.post(
        "/api/account/mfa/setup", json={"password": password}, headers=headers
    )
    assert result.status_code == 200, result.text
    secret = result.json()["secret"]
    counter = identity.current_counter()
    monkeypatch.setattr(identity, "current_counter", lambda: counter)
    code = identity.totp(secret, counter)
    assert (
        client.post(
            "/api/account/mfa/confirm",
            json={"password": password, "code": code},
            headers=headers,
        ).status_code
        == 200
    )
    with db_session() as db:
        email = db.execute("SELECT email FROM users WHERE id=?", (staff,)).fetchone()[0]
        assert (
            secret
            not in db.execute(
                "SELECT secret FROM account_mfa WHERE user_id=?", (staff,)
            ).fetchone()[0]
        )
    client.cookies.clear()
    assert (
        client.post(
            "/api/auth/login", json={"email": email, "password": password}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"email": email, "password": password, "code": code}
        ).status_code
        == 401
    )
    counter += 1
    result = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
            "code": identity.totp(secret, counter),
        },
    )
    assert result.status_code == 200, result.text
    assert client.get("/api/auth/me").json()["user"]["mfa_enabled"]


def test_owner_access_change_revokes_sessions_and_retains_records(client):
    from backend.database import db_session

    staff, staff_headers = principal(client)
    staff_cookie = client.cookies.get("hv_session")
    entry = insert_shift(
        staff, "2026-05-01T09:00:00+10:00", "2026-05-01T10:00:00+10:00"
    )
    client.cookies.clear()
    headers = {"X-CSRF-Token": sign_in(client, ADMIN)}
    result = client.post(
        f"/api/account/{staff}/access",
        json={
            "management_scope": "manager",
            "staff_ids": [],
            "reason": "Approved team management role",
        },
        headers=headers,
    )
    assert result.status_code == 200, result.text
    client.cookies.clear()
    client.cookies.set("hv_session", staff_cookie)
    assert client.get("/api/auth/me").status_code == 401
    with db_session() as db:
        assert db.execute("SELECT id FROM time_entries WHERE id=?", (entry,)).fetchone()
