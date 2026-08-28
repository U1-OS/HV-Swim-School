"""Automated API tests for the HV Swim platform.

These lock in the security properties the build depends on — role boundaries, ownership
isolation, CSRF enforcement and sign-in rate limiting — so that neither agent working on
this repo can quietly regress them. No running server is needed; FastAPI's TestClient
drives the app in-process against a throwaway database.

    pip install -r requirements.txt pytest
    pytest tests/ -q
"""

from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAMILY = ("parent@hvswim.demo", "FamilyDemo!26")
STAFF = ("staff@hvswim.demo", "StaffDemo!26")
ADMIN = ("admin@hvswim.demo", "AdminDemo!26")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """A client backed by a fresh seeded database, never the developer's own."""
    db_dir = tmp_path_factory.mktemp("hvswim-test-data")
    os.environ["HV_APP_ENV"] = "development"
    os.environ["HV_DATA_DIR"] = str(db_dir)

    from backend import config
    importlib.reload(config)
    config.DATA_DIR = db_dir
    config.DB_PATH = db_dir / "test.db"

    from backend import database
    importlib.reload(database)
    database.DB_PATH = config.DB_PATH

    from backend import server
    importlib.reload(server)

    with TestClient(server.app) as test_client:
        yield test_client


def sign_in(client, credentials):
    """Returns a fresh session. Cookies live on the client, so sign in per test group."""
    response = client.post("/api/auth/login", json={"email": credentials[0], "password": credentials[1]})
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


# --- public surface -------------------------------------------------------------------

def test_health_is_public(client):
    assert client.get("/api/health").status_code == 200


def test_public_endpoints_need_no_session(client):
    for path in ("/api/public/locations", "/api/public/site-settings", "/api/classes"):
        assert client.get(path).status_code == 200, path


def test_public_site_serves_only_explicitly_approved_files(client):
    for path in ("/", "/index.html", "/assets/styles.css", "/service-worker.js", "/robots.txt", "/favicon.ico"):
        assert client.get(path).status_code == 200, path

    # These paths all exist in a normal checkout. None may ever become a public download,
    # even if a future deployment also places an .env file or production database here.
    private_paths = (
        "/.env",
        "/.env.example",
        "/.git/config",
        "/AGENTS.md",
        "/HANDOFF.md",
        "/backend/config.py",
        "/data/hv_swim.db",
        "/tests/test_api.py",
    )
    for path in private_paths:
        response = client.get(path, headers={"Accept": "application/octet-stream"})
        assert response.status_code == 404, path
        assert "session_secret" not in response.text.lower(), path


def test_public_files_support_head_for_probes_and_crawlers(client):
    for path in ("/", "/index.html", "/robots.txt", "/assets/styles.css"):
        response = client.head(path)
        assert response.status_code == 200, path
        assert response.content == b"", path


def test_security_policy_allows_only_the_opt_in_facebook_frame(client):
    policy = client.get("/index.html").headers.get("content-security-policy", "")
    assert "script-src 'self'" in policy
    assert "connect-src 'self'" in policy
    assert "frame-src https://www.facebook.com" in policy
    assert "frame-ancestors 'self'" in policy


def test_native_app_origin_can_reach_the_api(client):
    response = client.options(
        "/api/health",
        headers={
            "Origin": "capacitor://localhost",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "capacitor://localhost"


def test_invalid_host_and_form_encoded_api_requests_are_rejected_early(client):
    assert client.get("/api/health", headers={"Host": "trusted.example/forged-path"}).status_code == 400
    form_response = client.post(
        "/api/public/enquiries",
        content="name=Sam&email=sam%40example.com",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert form_response.status_code == 415
    assert form_response.headers.get("cache-control") == "no-store"


def test_public_class_list_never_exposes_swimmer_identities(client):
    body = client.get("/api/classes").text.lower()
    for leak in ("medical", "date_of_birth", "emergency_contact", "swimmer_id"):
        assert leak not in body, f"{leak} appears in the public class list"


# --- authentication -------------------------------------------------------------------

def test_protected_endpoints_reject_anonymous_callers(client):
    client.cookies.clear()
    for path in ("/api/auth/me", "/api/customer/swimmers", "/api/staff/roster", "/api/admin/metrics"):
        assert client.get(path).status_code == 401, path


def test_wrong_password_is_rejected(client):
    client.cookies.clear()
    response = client.post("/api/auth/login", json={"email": FAMILY[0], "password": "NotThePassword1!"})
    assert response.status_code == 401
    assert "password" not in response.json()["detail"].lower().replace("email or password is incorrect", "")


def test_unknown_and_known_emails_give_the_same_error(client):
    """A different message for a real account would let anyone enumerate customers."""
    client.cookies.clear()
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "NotThePassword1!"})
    known = client.post("/api/auth/login", json={"email": FAMILY[0], "password": "NotThePassword1!"})
    assert unknown.status_code == known.status_code == 401
    assert unknown.json()["detail"] == known.json()["detail"]


def test_repeated_failures_are_rate_limited(client):
    client.cookies.clear()
    email = "spray-target@example.com"
    statuses = [
        client.post("/api/auth/login", json={"email": email, "password": "WrongPassword1!"}).status_code
        for _ in range(12)
    ]
    assert 429 in statuses, "sign-in attempts are not rate limited"


def test_old_login_attempts_are_pruned_even_when_login_fails(client):
    from backend.database import db_session

    old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    with db_session() as db:
        cursor = db.execute(
            "INSERT INTO login_attempts(email,ip_address,success,created_at) VALUES(?,?,0,?)",
            ("expired@example.com", "198.51.100.20", old),
        )
        attempt_id = cursor.lastrowid
    response = client.post(
        "/api/auth/login",
        json={"email": "still-wrong@example.com", "password": "NotThePassword1!"},
    )
    assert response.status_code == 401
    with db_session() as db:
        assert db.execute("SELECT id FROM login_attempts WHERE id=?", (attempt_id,)).fetchone() is None


def test_sign_out_invalidates_the_session(client):
    client.cookies.clear()
    csrf = sign_in(client, FAMILY)
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401


# --- CSRF -----------------------------------------------------------------------------

def test_state_changing_request_without_csrf_token_is_refused(client):
    client.cookies.clear()
    sign_in(client, FAMILY)
    response = client.post("/api/customer/bookings", json={"class_id": 1, "swimmer_id": 1})
    assert response.status_code == 403


def test_state_changing_request_with_wrong_csrf_token_is_refused(client):
    client.cookies.clear()
    sign_in(client, FAMILY)
    response = client.post(
        "/api/customer/bookings",
        json={"class_id": 1, "swimmer_id": 1},
        headers={"X-CSRF-Token": "not-the-right-token"},
    )
    assert response.status_code == 403


# --- role boundaries ------------------------------------------------------------------

def test_family_account_cannot_reach_staff_or_management(client):
    client.cookies.clear()
    sign_in(client, FAMILY)
    for path in ("/api/staff/roster", "/api/staff/time-entries", "/api/admin/metrics", "/api/admin/dashboard", "/api/admin/accounts"):
        assert client.get(path).status_code == 403, path


def test_staff_account_cannot_reach_management(client):
    client.cookies.clear()
    sign_in(client, STAFF)
    for path in ("/api/admin/metrics", "/api/admin/dashboard", "/api/admin/accounts"):
        assert client.get(path).status_code == 403, path


def test_staff_account_cannot_export_enquiries(client):
    """Enquiry exports carry parent contact details and children's names."""
    client.cookies.clear()
    sign_in(client, STAFF)
    assert client.get("/api/admin/exports/enquiries.csv").status_code == 403


def test_family_account_cannot_export_anything(client):
    client.cookies.clear()
    sign_in(client, FAMILY)
    for path in ("/api/admin/exports/enquiries.csv", "/api/admin/exports/timesheets.csv"):
        assert client.get(path).status_code == 403, path


def test_management_exports_are_audit_logged(client):
    from backend.database import db_session

    client.cookies.clear()
    sign_in(client, ADMIN)
    user_id = client.get("/api/auth/me").json()["user"]["id"]
    with db_session() as db:
        before = db.execute("SELECT COUNT(*) FROM audit_log WHERE action='export_enquiries'").fetchone()[0]
    response = client.get("/api/admin/exports/enquiries.csv")
    assert response.status_code == 200
    with db_session() as db:
        row = db.execute(
            "SELECT user_id,detail,ip_address FROM audit_log WHERE action='export_enquiries' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        after = db.execute("SELECT COUNT(*) FROM audit_log WHERE action='export_enquiries'").fetchone()[0]
    assert after == before + 1
    assert row["user_id"] == user_id
    assert "record_count" in row["detail"]
    assert row["ip_address"]


def test_management_can_reach_its_own_surfaces(client):
    client.cookies.clear()
    sign_in(client, ADMIN)
    for path in ("/api/admin/metrics", "/api/admin/dashboard"):
        assert client.get(path).status_code == 200, path


def test_management_can_provision_a_family_and_swimmer_with_a_forced_password_change(client):
    client.cookies.clear()
    admin_csrf = sign_in(client, ADMIN)
    original_password = "WelcomeFamily!2026"
    account = client.post(
        "/api/admin/accounts",
        json={
            "email": "new-family@example.com",
            "temporary_password": original_password,
            "role": "customer",
            "first_name": "Morgan",
            "last_name": "Lee",
            "phone": "0400 111 222",
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert account.status_code == 200, account.text
    account_id = account.json()["id"]
    swimmer = client.post(
        "/api/admin/swimmers",
        json={
            "customer_id": account_id,
            "first_name": "Ari",
            "last_name": "Lee",
            "date_of_birth": "2021-06-12",
            "level": "Program match required",
            "emergency_contact": "Morgan Lee · 0400 111 222",
            "photo_consent": False,
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert swimmer.status_code == 200, swimmer.text

    client.cookies.clear()
    login = client.post(
        "/api/auth/login",
        json={"email": "new-family@example.com", "password": original_password},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["must_change_password"] is True
    changed_password = "FamilyChosen!2026"
    changed = client.post(
        "/api/auth/change-password",
        json={"current_password": original_password, "new_password": changed_password},
        headers={"X-CSRF-Token": login.json()["csrf_token"]},
    )
    assert changed.status_code == 200, changed.text
    assert client.get("/api/auth/me").json()["user"]["must_change_password"] is False

    client.cookies.clear()
    assert client.post(
        "/api/auth/login",
        json={"email": "new-family@example.com", "password": original_password},
    ).status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"email": "new-family@example.com", "password": changed_password},
    ).status_code == 200


def test_management_can_suspend_and_securely_reissue_access(client):
    client.cookies.clear()
    admin_csrf = sign_in(client, ADMIN)
    me = client.get("/api/auth/me").json()["user"]
    accounts = client.get("/api/admin/accounts").json()["accounts"]
    family = next(item for item in accounts if item["email"] == "new-family@example.com")
    headers = {"X-CSRF-Token": admin_csrf}

    cannot_lock_self = client.patch(
        f"/api/admin/accounts/{me['id']}/status", json={"active": False}, headers=headers
    )
    assert cannot_lock_self.status_code == 400
    suspended = client.patch(
        f"/api/admin/accounts/{family['id']}/status", json={"active": False}, headers=headers
    )
    assert suspended.status_code == 200, suspended.text

    client.cookies.clear()
    assert client.post(
        "/api/auth/login",
        json={"email": family["email"], "password": "FamilyChosen!2026"},
    ).status_code == 401

    client.cookies.clear()
    admin_csrf = sign_in(client, ADMIN)
    headers = {"X-CSRF-Token": admin_csrf}
    assert client.patch(
        f"/api/admin/accounts/{family['id']}/status", json={"active": True}, headers=headers
    ).status_code == 200
    temporary_password = "ReissuedAccess!2026"
    reissued = client.post(
        f"/api/admin/accounts/{family['id']}/temporary-password",
        json={"temporary_password": temporary_password},
        headers=headers,
    )
    assert reissued.status_code == 200, reissued.text

    client.cookies.clear()
    login = client.post(
        "/api/auth/login",
        json={"email": family["email"], "password": temporary_password},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["must_change_password"] is True


def test_xero_timesheet_action_is_audited_readiness_only_and_uses_melbourne_dates(client):
    from backend.database import db_session
    from backend.security import now_iso

    client.cookies.clear()
    admin_csrf = sign_in(client, ADMIN)
    with db_session() as db:
        staff = db.execute("SELECT id FROM users WHERE role='staff' ORDER BY id LIMIT 1").fetchone()
        location = db.execute("SELECT id FROM locations ORDER BY id LIMIT 1").fetchone()
        admin_id = db.execute("SELECT id FROM users WHERE email=?", (ADMIN[0],)).fetchone()["id"]
        db.execute(
            "UPDATE users SET xero_employee_id=NULL,xero_payroll_calendar_id=NULL WHERE id=?",
            (staff["id"],),
        )
        cursor = db.execute(
            """INSERT INTO time_entries(
                   staff_id,location_id,clock_in,clock_out,hours,status,approved_by,approved_at
               ) VALUES(?,?,?,?,?,'approved',?,?)""",
            (
                staff["id"],
                location["id"],
                "2026-08-28T15:30:00+00:00",
                "2026-08-28T16:30:00+00:00",
                1.0,
                admin_id,
                now_iso(),
            ),
        )
        entry_id = cursor.lastrowid
        db.execute(
            "UPDATE integration_connections SET status='connected',metadata='{}',updated_at=? WHERE provider='xero'",
            (now_iso(),),
        )

    preview = client.post(
        "/api/integrations/xero/sync-timesheets",
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["synced"] == 0
    assert body["dry_run"] is True
    assert body["transmission_locked"] is True
    entry = next(item for item in body["entries"] if item["entry_id"] == entry_id)
    assert entry["business_date"] == "2026-08-29"
    assert entry["employee_mapped"] is False
    assert "access_token" not in preview.text
    assert "refresh_token" not in preview.text

    mapped = client.patch(
        f"/api/admin/staff/{staff['id']}/xero-mapping",
        json={"employee_id": "xero-employee-test", "payroll_calendar_id": "xero-calendar-test"},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert mapped.status_code == 200, mapped.text
    assert mapped.json()["employee_mapped"] is True
    with db_session() as db:
        assert db.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action='preview_xero_timesheets'"
        ).fetchone()[0] >= 1


# --- ownership isolation --------------------------------------------------------------

def test_family_sees_only_its_own_swimmers(client):
    client.cookies.clear()
    sign_in(client, FAMILY)
    mine = client.get("/api/customer/swimmers").json()["swimmers"]
    me = client.get("/api/auth/me").json()["user"]["id"]
    assert all(swimmer["customer_id"] == me for swimmer in mine)


def test_family_cannot_book_a_swimmer_it_does_not_own(client):
    client.cookies.clear()
    csrf = sign_in(client, FAMILY)
    response = client.post(
        "/api/customer/bookings",
        json={"class_id": 1, "swimmer_id": 999999},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code in (403, 404), response.text


def test_staff_sees_only_its_own_time_entries(client):
    client.cookies.clear()
    sign_in(client, STAFF)
    me = client.get("/api/auth/me").json()["user"]["id"]
    entries = client.get("/api/staff/time-entries").json()["time_entries"]
    assert all(entry["staff_id"] == me for entry in entries)


def test_broadcast_read_state_is_private_to_each_account(client):
    from backend.database import db_session
    from backend.security import now_iso, password_hash

    client.cookies.clear()
    admin_csrf = sign_in(client, ADMIN)
    created = client.post(
        "/api/admin/notifications",
        json={
            "audience_role": "customer",
            "title": "Receipt isolation test",
            "message": "Each family keeps its own read state.",
            "kind": "info",
            "channels": ["in_app"],
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert created.status_code == 200, created.text
    notification_id = created.json()["id"]

    second_email = "second-family@example.com"
    second_password = "SecondFamily!2026"
    with db_session() as db:
        db.execute(
            """INSERT OR IGNORE INTO users(email,password_hash,role,first_name,last_name,created_at)
               VALUES(?,?,?,?,?,?)""",
            (second_email, password_hash(second_password), "customer", "Taylor", "Reed", now_iso()),
        )

    client.cookies.clear()
    first_csrf = sign_in(client, FAMILY)
    first_before = next(n for n in client.get("/api/notifications").json()["notifications"] if n["id"] == notification_id)
    assert first_before["read_at"] is None
    assert client.post(
        f"/api/notifications/{notification_id}/read", headers={"X-CSRF-Token": first_csrf}
    ).status_code == 200
    first_after = next(n for n in client.get("/api/notifications").json()["notifications"] if n["id"] == notification_id)
    assert first_after["read_at"] is not None

    client.cookies.clear()
    sign_in(client, (second_email, second_password))
    second_view = next(n for n in client.get("/api/notifications").json()["notifications"] if n["id"] == notification_id)
    assert second_view["read_at"] is None


def test_external_message_channels_are_never_falsely_reported_as_sent(client):
    client.cookies.clear()
    csrf = sign_in(client, ADMIN)
    response = client.post(
        "/api/admin/notifications",
        json={
            "audience_role": "staff",
            "title": "Adapter boundary",
            "message": "In-app only until a provider adapter is implemented.",
            "kind": "info",
            "channels": ["in_app", "email", "sms", "push"],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text
    assert response.json()["in_app_delivered"] is True
    assert response.json()["external_channels"] == {
        "email": "not_implemented",
        "sms": "not_implemented",
        "push": "not_implemented",
    }
    assert "queued" not in response.json()


# --- secrets --------------------------------------------------------------------------

def test_integration_status_never_returns_credentials(client):
    client.cookies.clear()
    sign_in(client, ADMIN)
    body = client.get("/api/admin/dashboard").text.lower()
    for secret in ("client_secret", "storefront_token", "api_token", "password_hash", "csrf_token"):
        assert secret not in body, f"{secret} is exposed in the management dashboard payload"


# --- public enquiry form -------------------------------------------------------------

ENQUIRY = {
    "name": "Sam Rivers",
    "email": "sam@example.com",
    "swimmer_name": "Ivy",
    "swimmer_age": "5",
    "program_interest": "Learn to Swim",
}


def test_enquiry_can_be_submitted_without_an_account(client):
    client.cookies.clear()
    response = client.post("/api/public/enquiries", json=ENQUIRY)
    assert response.status_code == 200, response.text
    assert response.json()["received"] is True
    assert response.json()["reference"].startswith("HV-ENQ-")


def test_merchandise_interest_is_recorded_as_merchandise_not_a_fake_swimmer(client):
    from backend.database import db_session

    client.cookies.clear()
    response = client.post(
        "/api/public/enquiries",
        json={
            "enquiry_type": "merchandise",
            "name": "Alex Rivers",
            "email": "alex@example.com",
            "program_interest": "HV Swim Logo Towel",
            "experience": "Please tell me when the first sample is approved.",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["reference"].startswith("HV-MERCH-")
    with db_session() as db:
        row = db.execute("SELECT * FROM enquiries WHERE id=?", (response.json()["id"],)).fetchone()
    assert row["enquiry_type"] == "merchandise"
    assert not row["swimmer_name"]
    assert not row["swimmer_age"]


def test_honeypot_submission_is_swallowed(client):
    """A bot fills every field. It should get a normal-looking reply and store nothing."""
    client.cookies.clear()
    response = client.post("/api/public/enquiries", json={**ENQUIRY, "website": "http://spam.example"})
    assert response.status_code == 200
    assert response.json()["id"] == 0


def test_enquiries_are_rate_limited_per_address(client):
    """The only unauthenticated write endpoint in the system — it must not be floodable."""
    client.cookies.clear()
    statuses = [client.post("/api/public/enquiries", json=ENQUIRY).status_code for _ in range(10)]
    assert 429 in statuses, "the public enquiry form accepts unlimited submissions"
    refusal = next(s for s in statuses if s == 429)
    assert refusal == 429


def test_enquiry_rejects_a_malformed_email(client):
    client.cookies.clear()
    response = client.post("/api/public/enquiries", json={**ENQUIRY, "email": "not-an-email"})
    assert response.status_code == 422


def test_enquiry_list_is_management_only(client):
    """Enquiries hold parent contact details and children's names."""
    client.cookies.clear()
    assert client.get("/api/admin/enquiries").status_code == 401
    sign_in(client, FAMILY)
    assert client.get("/api/admin/enquiries").status_code == 403


# --- error handling ------------------------------------------------------------------

def test_unknown_page_returns_the_branded_404_to_a_browser(client):
    response = client.get("/no-such-page.html", headers={"Accept": "text/html"})
    assert response.status_code == 404
    assert "HV Swim" in response.text
    assert "detail" not in response.text[:200].lower()


def test_unknown_api_path_still_returns_json(client):
    response = client.get("/api/no-such-endpoint", headers={"Accept": "application/json"})
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


# --- caching -------------------------------------------------------------------------

def test_api_responses_are_never_cached(client):
    client.cookies.clear()
    assert client.get("/api/health").headers.get("cache-control") == "no-store"


def test_versioned_assets_are_cached_hard(client):
    response = client.get("/assets/styles.css?v=5.1.1")
    if response.status_code == 200:
        assert "max-age=31536000" in response.headers.get("cache-control", "")


def test_large_assets_are_compressed_for_mobile_delivery(client):
    response = client.get("/assets/styles.css?v=5.1.1", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"
    assert "Accept-Encoding" in response.headers.get("vary", "")


# --- booking integrity ---------------------------------------------------------------

def test_a_swimmer_cannot_be_booked_twice_into_the_same_class(client):
    """Guarded in application code and by a unique index, so a race cannot slip past."""
    client.cookies.clear()
    csrf = sign_in(client, FAMILY)
    swimmers = client.get("/api/customer/swimmers").json()["swimmers"]
    classes = client.get("/api/classes").json()["classes"]
    assert swimmers and classes, "seed data is missing"
    swimmer_id = swimmers[0]["id"]
    target = next((c for c in classes if c["available"] > 0), classes[0])
    headers = {"X-CSRF-Token": csrf}
    body = {"class_id": target["id"], "swimmer_id": swimmer_id}

    first = client.post("/api/customer/bookings", json=body, headers=headers)
    assert first.status_code in (200, 409), first.text
    second = client.post("/api/customer/bookings", json=body, headers=headers)
    assert second.status_code == 409, "the same swimmer was booked into one class twice"


def test_booking_a_full_class_offers_the_waitlist_rather_than_overfilling(client):
    """Class capacity encodes the instructor-to-swimmer ratio, so it must never be exceeded."""
    client.cookies.clear()
    csrf = sign_in(client, FAMILY)
    swimmers = client.get("/api/customer/swimmers").json()["swimmers"]
    full = [c for c in client.get("/api/classes").json()["classes"] if c["available"] == 0]
    if not full or not swimmers:
        pytest.skip("no full class in the seed data")
    response = client.post(
        "/api/customer/bookings",
        json={"class_id": full[0]["id"], "swimmer_id": swimmers[-1]["id"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code in (200, 409)
    if response.status_code == 200:
        assert response.json()["status"] == "waitlisted"


def test_a_family_can_cancel_rebook_and_cancel_the_same_class(client):
    client.cookies.clear()
    admin_csrf = sign_in(client, ADMIN)
    staff = client.get("/api/admin/staff").json()["staff"]
    create = client.post(
        "/api/admin/classes",
        json={
            "code": "REBOOK-TEST",
            "title": "Rebooking regression class",
            "level": "Test",
            "location_slug": "wood-street",
            "instructor_id": staff[0]["id"],
            "weekday": 2,
            "start_time": "11:15",
            "duration_minutes": 30,
            "capacity": 5,
            "price_cents": 2500,
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert create.status_code == 200, create.text

    client.cookies.clear()
    family_csrf = sign_in(client, FAMILY)
    swimmer_id = client.get("/api/customer/swimmers").json()["swimmers"][0]["id"]
    body = {"class_id": create.json()["id"], "swimmer_id": swimmer_id}
    headers = {"X-CSRF-Token": family_csrf}
    first = client.post("/api/customer/bookings", json=body, headers=headers)
    assert first.status_code == 200, first.text
    assert client.delete(f"/api/customer/bookings/{first.json()['booking_id']}", headers=headers).status_code == 200
    second = client.post("/api/customer/bookings", json=body, headers=headers)
    assert second.status_code == 200, second.text
    assert client.delete(f"/api/customer/bookings/{second.json()['booking_id']}", headers=headers).status_code == 200


def test_two_clock_in_requests_leave_only_one_open_shift(client):
    from backend.database import db_session

    client.cookies.clear()
    csrf = sign_in(client, STAFF)
    staff_id = client.get("/api/auth/me").json()["user"]["id"]
    headers = {"X-CSRF-Token": csrf}
    first = client.post("/api/staff/clock", json={"action": "in", "location_slug": "wood-street"}, headers=headers)
    second = client.post("/api/staff/clock", json={"action": "in", "location_slug": "wood-street"}, headers=headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 409, second.text
    with db_session() as db:
        assert db.execute(
            "SELECT COUNT(*) FROM time_entries WHERE staff_id=? AND clock_out IS NULL", (staff_id,)
        ).fetchone()[0] == 1
    assert client.post("/api/staff/clock", json={"action": "out", "location_slug": "wood-street"}, headers=headers).status_code == 200


# --- input validation ----------------------------------------------------------------

def test_class_times_must_be_real_times(client):
    """Times are stored and ordered as text, so a malformed one corrupts the timetable order."""
    client.cookies.clear()
    csrf = sign_in(client, ADMIN)
    base = {"code": "HV-TEST", "title": "Test Class", "level": "Level 1",
            "location_slug": "wood-street", "weekday": 1, "duration_minutes": 30,
            "capacity": 6, "price_cents": 2200}
    for bad in ("25:99", "banana", "9:30", "24:00", "16:00:00", ""):
        response = client.post("/api/admin/classes", json={**base, "start_time": bad},
                               headers={"X-CSRF-Token": csrf})
        assert response.status_code == 422, f"{bad!r} was accepted as a class start time"


def test_a_shift_cannot_finish_before_it_starts(client):
    client.cookies.clear()
    csrf = sign_in(client, ADMIN)
    staff = client.get("/api/admin/staff").json()["staff"]
    if not staff:
        pytest.skip("no staff in the seed data")
    response = client.post(
        "/api/admin/roster",
        json={"staff_id": staff[0]["id"], "location_slug": "wood-street",
              "shift_date": "2026-09-01", "start_time": "17:45", "end_time": "08:45"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 422


def test_clock_in_rejects_impossible_coordinates(client):
    client.cookies.clear()
    csrf = sign_in(client, STAFF)
    response = client.post(
        "/api/staff/clock",
        json={"action": "in", "location_slug": "wood-street", "latitude": 999, "longitude": -999},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 422


def test_pool_temperature_outside_a_plausible_range_is_rejected(client):
    client.cookies.clear()
    csrf = sign_in(client, STAFF)
    for bad in (-5, 80):
        response = client.post(
            "/api/staff/pool-readings",
            json={"location_slug": "wood-street", "temperature": bad, "status": "open"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 422, f"{bad} was accepted as a pool temperature"
