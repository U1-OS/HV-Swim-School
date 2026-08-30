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
import hashlib
import os
import sys
import base64
import binascii
import struct
import zlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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


def make_test_png_base64(width=64, height=64):
    """Create a small valid RGBA PNG with only the Python standard library."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)

    pixels = b"".join(b"\x00" + (b"\x08\x75\xa5\xff" * width) for _ in range(height))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )
    return base64.b64encode(png).decode("ascii")


# --- public surface -------------------------------------------------------------------

def test_health_is_public(client):
    assert client.get("/api/health").status_code == 200


def test_family_account_provider_status_is_public_and_secret_free(client):
    response = client.get("/api/auth/oauth/providers")
    assert response.status_code == 200
    payload = response.json()
    assert payload["signup_role"] == "customer"
    assert payload["team_accounts"] == "invitation_only"
    assert payload["configured_count"] == 0
    assert payload["providers"] == [
        {"id": "google", "label": "Google", "configured": False, "account_role": "customer"},
        {"id": "apple", "label": "Apple", "configured": False, "account_role": "customer"},
    ]
    assert "secret" not in response.text.lower()
    assert client.get("/api/auth/oauth/google/start").status_code == 503


def _oauth_start(client, monkeypatch, server, provider):
    monkeypatch.setattr(server, "oauth_provider_ready", lambda selected: selected == provider)
    monkeypatch.setattr(
        server,
        "oauth_authorization_url",
        lambda selected, **values: f"https://accounts.example.test/authorize?state={values['state']}&provider={selected}",
    )
    response = client.get(f"/api/auth/oauth/{provider}/start", follow_redirects=False)
    assert response.status_code == 302
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    return state


def test_google_signup_creates_only_a_family_identity_and_session(client, monkeypatch):
    from backend import server
    from backend.database import db_session

    client.cookies.clear()
    state = _oauth_start(client, monkeypatch, server, "google")
    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
    with db_session() as db:
        attempt = db.execute("SELECT state_hash,ip_address FROM oauth_login_attempts WHERE state_hash=?", (state_hash,)).fetchone()
    assert attempt["state_hash"] == state_hash
    assert attempt["state_hash"] != state
    assert attempt["ip_address"]

    async def exchange(provider, **_values):
        assert provider == "google"
        return {"id_token": "test-id-token", "access_token": "must-not-be-stored"}

    monkeypatch.setattr(server, "oauth_exchange_code", exchange)
    monkeypatch.setattr(
        server,
        "oauth_verify_identity_token",
        lambda provider, token, **_values: {
            "sub": "google-family-test-1",
            "email": "new.family@example.test",
            "email_verified": True,
            "given_name": "New",
            "family_name": "Family",
        },
    )
    response = client.get(
        f"/api/auth/oauth/google/callback?state={state}&code=one-use-code",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/platform.html?account=connected"
    assert client.get("/api/auth/me").json()["user"]["role"] == "customer"
    with db_session() as db:
        user = db.execute("SELECT * FROM users WHERE email='new.family@example.test'").fetchone()
        identity = db.execute("SELECT * FROM oauth_identities WHERE user_id=?", (user["id"],)).fetchone()
        audit_row = db.execute("SELECT detail FROM audit_log WHERE action='oauth_signup' ORDER BY id DESC LIMIT 1").fetchone()
        database_dump = " ".join(str(value) for row in db.execute("SELECT * FROM oauth_identities") for value in row)
    assert user["role"] == "customer"
    assert identity["provider"] == "google"
    assert identity["subject"] == "google-family-test-1"
    assert "access_token" not in database_dump and "must-not-be-stored" not in database_dump
    assert '"provider": "google"' in audit_row["detail"]


def test_social_identity_cannot_self_link_to_staff(client, monkeypatch):
    from backend import server

    client.cookies.clear()
    state = _oauth_start(client, monkeypatch, server, "google")

    async def exchange(_provider, **_values):
        return {"id_token": "test-id-token"}

    monkeypatch.setattr(server, "oauth_exchange_code", exchange)
    monkeypatch.setattr(
        server,
        "oauth_verify_identity_token",
        lambda *_args, **_values: {"sub": "staff-link-attempt", "email": STAFF[0], "email_verified": True},
    )
    response = client.get(
        f"/api/auth/oauth/google/callback?state={state}&code=one-use-code",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("oauth_error=team_account_requires_approval")


def test_apple_form_post_callback_is_narrowly_allowed(client, monkeypatch):
    from backend import server

    client.cookies.clear()
    state = _oauth_start(client, monkeypatch, server, "apple")

    async def exchange(provider, **_values):
        assert provider == "apple"
        return {"id_token": "apple-test-id-token"}

    monkeypatch.setattr(server, "oauth_exchange_code", exchange)
    monkeypatch.setattr(
        server,
        "oauth_verify_identity_token",
        lambda *_args, **_values: {"sub": "apple-family-test-1", "email": "icloud.family@example.test", "email_verified": True},
    )
    response = client.post(
        "/api/auth/oauth/apple/callback",
        data={"state": state, "code": "one-use-code", "user": '{"name":{"firstName":"iCloud","lastName":"Family"}}'},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/platform.html?account=connected"
    assert client.post("/api/auth/login", data={"email": "x"}).status_code == 415
    assert client.post(
        "/api/auth/oauth/apple/callback",
        content=b"x" * 32_769,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    ).status_code == 413


def test_social_signin_starts_are_rate_limited_per_ip(client, monkeypatch):
    from backend import server
    from backend.database import db_session

    monkeypatch.setattr(server, "oauth_provider_ready", lambda provider: provider == "google")
    monkeypatch.setattr(server, "oauth_authorization_url", lambda _provider, **_values: "https://accounts.example.test")
    with db_session() as db:
        db.execute("DELETE FROM oauth_login_attempts")
    try:
        for _ in range(30):
            assert client.get("/api/auth/oauth/google/start", follow_redirects=False).status_code == 302
        blocked = client.get("/api/auth/oauth/google/start", follow_redirects=False)
        assert blocked.status_code == 429
    finally:
        with db_session() as db:
            db.execute("DELETE FROM oauth_login_attempts")


def test_public_endpoints_need_no_session(client):
    for path in ("/api/public/locations", "/api/public/site-settings", "/api/classes"):
        assert client.get(path).status_code == 200, path


def test_public_site_mode_and_sensitive_features_fail_closed(client):
    response = client.get("/api/public/site-settings")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "preview"
    assert payload["features"] == {"merch_home": False, "association_badges": False}
    assert "feature_merch_home" not in payload["settings"]


def test_management_feature_controls_enforce_real_launch_gates(client):
    from backend.database import db_session

    client.cookies.clear()
    csrf = sign_in(client, ADMIN)
    admin_response = client.get("/api/admin/site-settings")
    assert admin_response.status_code == 200
    admin_payload = admin_response.json()
    assert admin_payload["confirmed_business"]["abn"] == "46 687 937 962"
    assert admin_payload["confirmed_business"]["clock_tracking"] == "Not used"
    assert admin_payload["feature_controls"]["merch_home"]["can_enable"] is False
    assert admin_payload["feature_controls"]["association_badges"]["can_enable"] is False

    settings = admin_payload["settings"]
    update_payload = {
        "announcement_enabled": settings["announcement_enabled"],
        "announcement_text": settings["announcement_text"],
        "enrolment_status": settings["enrolment_status"],
        "hero_eyebrow": settings["hero_eyebrow"],
        "hero_heading": settings["hero_heading"],
        "hero_accent": settings["hero_accent"],
        "hero_intro": settings["hero_intro"],
        "primary_cta": settings["primary_cta"],
        "feature_merch_home": False,
        "feature_association_badges": True,
    }
    association_blocked = client.patch(
        "/api/admin/site-settings", json=update_payload, headers={"X-CSRF-Token": csrf}
    )
    assert association_blocked.status_code == 409
    assert "issued badge files" in association_blocked.json()["detail"]

    update_payload["feature_association_badges"] = False
    update_payload["feature_merch_home"] = True
    merch_blocked = client.patch(
        "/api/admin/site-settings", json=update_payload, headers={"X-CSRF-Token": csrf}
    )
    assert merch_blocked.status_code == 409
    assert "physical-sample" in merch_blocked.json()["detail"]

    with db_session() as db:
        original = dict(
            db.execute(
                """SELECT id,price_cents,cost_cents,status,sample_status,sizes,supplier_route,
                          shopify_gid,printify_product_id,supplier_reference
                   FROM products ORDER BY id LIMIT 1"""
            ).fetchone()
        )
        db.execute(
            """UPDATE products SET price_cents=6500,cost_cents=3000,status='available',
                      sample_status='approved',sizes='[\"Standard\"]',supplier_route='printify',
                      shopify_gid='gid://shopify/Product/test-ready',printify_product_id='printify-ready',
                      supplier_reference=NULL WHERE id=?""",
            (original["id"],),
        )
    try:
        published = client.patch(
            "/api/admin/site-settings", json=update_payload, headers={"X-CSRF-Token": csrf}
        )
        assert published.status_code == 200, published.text
        assert published.json()["feature_controls"]["merch_home"]["effective_enabled"] is True
        assert client.get("/api/public/site-settings").json()["features"]["merch_home"] is True
    finally:
        with db_session() as db:
            db.execute(
                """UPDATE products SET price_cents=?,cost_cents=?,status=?,sample_status=?,sizes=?,
                          supplier_route=?,shopify_gid=?,printify_product_id=?,supplier_reference=?
                   WHERE id=?""",
                (
                    original["price_cents"], original["cost_cents"], original["status"],
                    original["sample_status"], original["sizes"], original["supplier_route"],
                    original["shopify_gid"], original["printify_product_id"],
                    original["supplier_reference"], original["id"],
                ),
            )
            db.execute("UPDATE site_settings SET value='0' WHERE key='feature_merch_home'")
            db.execute("UPDATE site_settings SET value='0' WHERE key='feature_association_badges'")
        client.cookies.clear()


def test_association_artwork_evidence_workflow_is_verified_and_fail_closed(client):
    from backend.database import db_session

    client.cookies.clear()
    csrf = sign_in(client, ADMIN)
    staff_client_response = None

    credentials = client.get("/api/admin/association-badges")
    assert credentials.status_code == 200
    assert len(credentials.json()["credentials"]) == 3
    assert all(not item["ready"] for item in credentials.json()["credentials"])
    assert client.get("/api/public/association-badges").json() == {"badges": [], "published": False}

    invalid = client.patch(
        "/api/admin/association-badges/austswim",
        json={
            "membership_reference": "test-reference",
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=365)).date().isoformat(),
            "usage_rights_confirmed": True,
            "internal_notes": "Test-only evidence",
            "artwork_png_base64": base64.b64encode(b"not a png").decode("ascii"),
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert invalid.status_code == 422
    assert "PNG" in invalid.json()["detail"]

    future = (datetime.now(timezone.utc) + timedelta(days=365)).date().isoformat()
    artwork = make_test_png_base64()
    keys = ("swim_schools_australia", "austswim", "autism_swim")
    for key in keys:
        saved = client.patch(
            f"/api/admin/association-badges/{key}",
            json={
                "membership_reference": f"test-{key}",
                "valid_until": future,
                "usage_rights_confirmed": True,
                "internal_notes": "Automated test evidence only",
                "artwork_png_base64": artwork,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["credential"]["ready"] is True
    assert saved.json()["feature_control"]["can_enable"] is True

    site = client.get("/api/admin/site-settings").json()["settings"]
    publish_payload = {
        "announcement_enabled": site["announcement_enabled"],
        "announcement_text": site["announcement_text"],
        "enrolment_status": site["enrolment_status"],
        "hero_eyebrow": site["hero_eyebrow"],
        "hero_heading": site["hero_heading"],
        "hero_accent": site["hero_accent"],
        "hero_intro": site["hero_intro"],
        "primary_cta": site["primary_cta"],
        "feature_merch_home": False,
        "feature_association_badges": True,
    }
    published = client.patch("/api/admin/site-settings", json=publish_payload, headers={"X-CSRF-Token": csrf})
    assert published.status_code == 200, published.text
    assert published.json()["feature_controls"]["association_badges"]["effective_enabled"] is True
    public_badges = client.get("/api/public/association-badges").json()
    assert public_badges["published"] is True
    assert len(public_badges["badges"]) == 3
    assert "membership_reference" not in public_badges["badges"][0]
    image = client.get(public_badges["badges"][0]["artwork_url"])
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/png")
    assert image.content.startswith(b"\x89PNG")

    expired = client.patch(
        "/api/admin/association-badges/swim_schools_australia",
        json={
            "membership_reference": "test-swim_schools_australia",
            "valid_until": "2020-01-01",
            "usage_rights_confirmed": True,
            "internal_notes": "Expired in test",
            "artwork_png_base64": None,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert expired.status_code == 200
    assert expired.json()["credential"]["ready"] is False
    assert client.get("/api/public/site-settings").json()["features"]["association_badges"] is False
    assert client.get("/api/public/association-badges").json()["badges"] == []
    assert client.get(public_badges["badges"][0]["artwork_url"]).status_code == 404

    try:
        client.cookies.clear()
        sign_in(client, STAFF)
        staff_client_response = client.get("/api/admin/association-badges")
        assert staff_client_response.status_code == 403
    finally:
        with db_session() as db:
            db.execute(
                """UPDATE association_credentials SET membership_reference=NULL,valid_until=NULL,
                          usage_rights_confirmed=0,internal_notes=NULL,artwork_filename=NULL,
                          artwork_sha256=NULL,verified_by=NULL,verified_at=NULL"""
            )
            db.execute("UPDATE site_settings SET value='0' WHERE key='feature_association_badges'")
        client.cookies.clear()


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


def test_database_never_stores_the_reusable_session_cookie(client):
    from backend.database import db_session

    client.cookies.clear()
    response = client.post("/api/auth/login", json={"email": FAMILY[0], "password": FAMILY[1]})
    assert response.status_code == 200
    raw_cookie = client.cookies.get("hv_session")
    assert raw_cookie
    with db_session() as db:
        stored = db.execute("SELECT id FROM sessions ORDER BY created_at DESC LIMIT 1").fetchone()["id"]
    assert raw_cookie != stored
    assert len(stored) == 64


def test_child_safety_details_are_encrypted_at_rest_but_available_to_family(client):
    from backend.database import db_session
    from backend.security import SENSITIVE_VALUE_PREFIX

    client.cookies.clear()
    csrf = sign_in(client, FAMILY)
    swimmer = client.get("/api/customer/swimmers").json()["swimmers"][0]
    payload = {
        "emergency_contact": "Private Contact · 0400 111 222",
        "medical_notes": "Private medical lesson note",
        "allergies": "Private allergy detail",
        "medications": "Private medication detail",
        "support_notes": "Private learning support detail",
    }
    response = client.patch(
        f"/api/customer/swimmers/{swimmer['id']}", json=payload, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 200
    returned = next(item for item in client.get("/api/customer/swimmers").json()["swimmers"] if item["id"] == swimmer["id"])
    assert returned["allergies"] == payload["allergies"]
    with db_session() as db:
        stored = db.execute("SELECT emergency_contact,medical_notes,allergies,medications,support_notes FROM swimmers WHERE id=?", (swimmer["id"],)).fetchone()
    assert all(stored[field].startswith(SENSITIVE_VALUE_PREFIX) for field in stored.keys())
    assert not any(value in " ".join(stored) for value in payload.values())


def test_family_can_control_in_app_lesson_reminders(client):
    client.cookies.clear()
    csrf = sign_in(client, FAMILY)
    response = client.patch(
        "/api/customer/reminder-preferences",
        json={"enabled": True, "hours_before": 48, "channels": ["in_app"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["preferences"]["hours_before"] == 48
    status = client.get("/api/customer/reminder-preferences")
    assert status.status_code == 200
    assert status.json()["delivery"]["in_app"] == "live"
    assert status.json()["delivery"]["email"] == "credentials_and_adapter_required"


def test_confirmed_lesson_creates_xero_only_billing_record(client):
    from backend.database import db_session

    client.cookies.clear()
    csrf = sign_in(client, FAMILY)
    swimmers = client.get("/api/customer/swimmers").json()["swimmers"]
    classes = client.get("/api/classes").json()["classes"]
    with db_session() as db:
        existing = {(row["class_id"], row["swimmer_id"]) for row in db.execute("SELECT class_id,swimmer_id FROM bookings WHERE status='confirmed'")}
    pair = next((item, swimmer) for item in classes for swimmer in swimmers if item["available"] and (item["id"], swimmer["id"]) not in existing)
    with db_session() as db:
        db.execute("UPDATE users SET customer_number=NULL WHERE id=?", (pair[1]["customer_id"],))
        db.execute("UPDATE swimmers SET swimmer_number=NULL WHERE id=?", (pair[1]["id"],))
    response = client.post(
        "/api/customer/bookings",
        json={"class_id": pair[0]["id"], "swimmer_id": pair[1]["id"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["payment"]["provider"] == "Xero"
    assert response.json()["payment"]["family_customer_number"].startswith("HVS-")
    assert response.json()["payment"]["swimmer_number"].startswith("HVS-S-")
    with db_session() as db:
        charge = db.execute("SELECT provider,status,amount_cents,family_customer_number,swimmer_number FROM lesson_charges WHERE booking_id=?", (response.json()["booking_id"],)).fetchone()
    assert dict(charge)["provider"] == "xero"
    assert dict(charge)["status"] == "pending_xero_invoice"
    assert dict(charge)["amount_cents"] > 0
    assert dict(charge)["family_customer_number"] == response.json()["payment"]["family_customer_number"]
    assert dict(charge)["swimmer_number"] == response.json()["payment"]["swimmer_number"]


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


def test_premium_merchandise_catalogue_is_seeded_with_safe_supplier_routes(client):
    from backend.database import db_session

    with db_session() as db:
        products = {row["sku"]: dict(row) for row in db.execute("SELECT * FROM products")}

    requested_skus = {
        "HV-SWIMWEAR", "HV-RASHIE", "HV-SWIM-SHORTS", "HV-TOWEL", "HV-HOODED-TOWEL",
        "HV-BOTTLE", "HV-INSULATED-TUMBLER", "HV-JUNIOR-WARM-CUP", "HV-GOGGLES",
        "HV-TRAINING-MITTS", "HV-BAG", "HV-CAP", "HV-KIDS-SUN-HAT", "HV-STAFF-POLO",
        "HV-STAFF-TEE", "HV-STAFF-SHORTS", "HV-TEAM-HOODIE", "HV-STAFF-PUFFER-VEST",
        "HV-STAFF-PUFFER-JACKET", "HV-STAFF-TRACKPANTS", "HV-INSTRUCTOR-CAP",
        "HV-MINI-HOODED-TOWEL", "HV-FAMILY-TEE", "HV-FAMILY-CREW",
    }
    assert requested_skus <= products.keys()
    assert len(products) >= 24
    assert products["HV-RASHIE"]["supplier_route"] == "specialist_swim"
    assert products["HV-GOGGLES"]["fulfilment_mode"] == "specialist_purchase_order"
    assert products["HV-STAFF-TEE"]["supplier_route"] == "printify"
    assert products["HV-STAFF-TEE"]["audience"] == "staff"
    assert products["HV-FAMILY-TEE"]["supplier_route"] == "printify"
    assert products["HV-FAMILY-CREW"]["fulfilment_mode"] == "printify_shopify"
    assert products["HV-MINI-HOODED-TOWEL"]["category"] == "Towels"
    assert "Hooded Towel Poncho" in products["HV-HOODED-TOWEL"]["title"]
    assert products["HV-INSULATED-TUMBLER"]["category"] == "Drinkware"
    assert "warm, never hot" in products["HV-JUNIOR-WARM-CUP"]["description"]


def test_public_merchandise_catalogue_does_not_expose_costs_or_supplier_references(client, monkeypatch):
    from backend import server

    monkeypatch.setattr(server, "shopify_ready", lambda: False)
    client.cookies.clear()
    response = client.get("/api/products")
    assert response.status_code == 200
    product = response.json()["products"][0]
    for private_field in ("cost_cents", "shopify_gid", "printify_product_id", "supplier_reference"):
        assert private_field not in product
    for public_field in ("sku", "title", "category", "audience", "supplier_route", "sample_status"):
        assert public_field in product
    assert all(item.get("audience") != "staff" for item in response.json()["products"])


def test_staff_merchandise_is_protected_and_staff_only(client, monkeypatch):
    from backend import server

    monkeypatch.setattr(server, "shopify_ready", lambda: False)
    client.cookies.clear()
    assert client.get("/api/staff/merchandise").status_code == 401
    sign_in(client, FAMILY)
    assert client.get("/api/staff/merchandise").status_code == 403
    client.cookies.clear()
    sign_in(client, STAFF)
    response = client.get("/api/staff/merchandise")
    assert response.status_code == 200
    assert response.json()["audience"] == "staff_only"
    assert response.json()["products"]
    assert all(item["audience"] == "staff" for item in response.json()["products"])


def test_merchandise_workspace_reports_real_sync_boundaries(client, monkeypatch):
    from backend import server

    monkeypatch.setattr(server, "printify_ready", lambda: False)
    client.cookies.clear()
    sign_in(client, ADMIN)
    response = client.get("/api/admin/merch-production")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["launch_readiness"]["total_products"] >= 24
    assert payload["catalogue_summary"]["by_audience"]["staff"] >= 7
    assert payload["sync_readiness"]["printify_eligible_products"] >= 3
    assert payload["providers"]["vistaprint"]["integration_mode"] == "manual_purchase_order"
    assert payload["providers"]["vistaprint"]["live_api_supported"] is False
    assert payload["providers"]["premium_teamwear"]["integration_mode"] == "authorised_reseller_manual"
    rashie = next(product for product in payload["catalogue"] if product["sku"] == "HV-RASHIE")
    assert rashie["production"]["supplier"] == "specialist_swim"
    assert rashie["sync"]["printify"] == "not_applicable"
    assert rashie["production_ready"] is False
    assert "Physical sample not approved" in rashie["blocking_reasons"]
    assert "Approved supplier or sample reference missing" in rashie["blocking_reasons"]
    junior_cup = next(product for product in payload["catalogue"] if product["sku"] == "HV-JUNIOR-WARM-CUP")
    assert "parent-supervised warm, never hot" in junior_cup["production"]["method"]


def test_management_can_record_shopify_and_printify_product_mappings(client, monkeypatch):
    from backend import server

    monkeypatch.setattr(server, "printify_ready", lambda: False)
    client.cookies.clear()
    csrf = sign_in(client, ADMIN)
    workspace = client.get("/api/admin/merch-production").json()
    product = next(item for item in workspace["catalogue"] if item["sku"] == "HV-STAFF-TEE")
    response = client.patch(
        f'/api/admin/products/{product["id"]}',
        json={
            "price_cents": product["price_cents"],
            "cost_cents": 2100,
            "status": "sampling",
            "sample_status": "ordered",
            "supplier_route": "printify",
            "personalisation": "Approved front mark; optional staff name after sample sign-off",
            "shopify_gid": "gid://shopify/Product/123456789",
            "printify_product_id": "printify-product-123",
            "supplier_reference": "SAMPLE-PO-001",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text
    refreshed = client.get("/api/admin/merch-production").json()
    updated = next(item for item in refreshed["catalogue"] if item["sku"] == "HV-STAFF-TEE")
    assert updated["shopify_gid"] == "gid://shopify/Product/123456789"
    assert updated["printify_product_id"] == "printify-product-123"
    assert updated["fulfilment_mode"] == "printify_shopify"
    assert updated["sync"] == {
        "shopify": "mapped",
        "printify": "mapped_connection_required",
        "manual_order_reference": "recorded",
    }

    invalid = client.patch(
        f'/api/admin/products/{product["id"]}',
        json={
            "price_cents": product["price_cents"], "status": "sampling", "sample_status": "ordered",
            "supplier_route": "specialist_swim", "personalisation": "None",
            "printify_product_id": "must-not-be-accepted",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert invalid.status_code == 422


def test_merchandise_export_includes_supplier_and_sync_fields(client):
    client.cookies.clear()
    sign_in(client, ADMIN)
    response = client.get("/api/admin/exports/products.csv")
    assert response.status_code == 200
    header = response.text.splitlines()[0]
    for field in ("Audience", "Supplier route", "Fulfilment", "Shopify GID", "Printify product ID", "Supplier reference"):
        assert field in header


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
        json={
            "employee_id": "xero-employee-test",
            "payroll_calendar_id": "xero-calendar-test",
            "shopify_customer_gid": "gid://shopify/Customer/900001",
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert mapped.status_code == 200, mapped.text
    assert mapped.json()["employee_mapped"] is True
    assert mapped.json()["shopify_staff_customer_mapped"] is True
    with db_session() as db:
        identity = db.execute(
            "SELECT staff_number,shopify_customer_gid FROM users WHERE id=?", (staff["id"],)
        ).fetchone()
        assert identity["staff_number"].startswith("HVS-W-")
        assert identity["shopify_customer_gid"] == "gid://shopify/Customer/900001"
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


def test_incident_report_links_family_swimmer_and_worker_numbers_with_encrypted_details(client):
    from backend.database import db_session

    client.cookies.clear()
    sign_in(client, FAMILY)
    family_swimmer_id = client.get("/api/customer/swimmers").json()["swimmers"][0]["id"]
    client.cookies.clear()
    staff_csrf = sign_in(client, STAFF)
    setup = client.get("/api/staff/incidents")
    assert setup.status_code == 200, setup.text
    swimmer = next(item for item in setup.json()["swimmers"] if item["id"] == family_swimmer_id)
    happened = "Swimmer slipped while walking beside the pool and sat down immediately."
    first_aid = "Instructor checked the child, applied a wrapped cold pack and monitored them."
    created = client.post(
        "/api/staff/incidents",
        json={
            "swimmer_id": swimmer["id"],
            "location_slug": "wood-street",
            "incident_at": datetime.now(timezone.utc).isoformat(),
            "incident_type": "injury",
            "what_happened": happened,
            "injury_observed": "Small red area on the left knee; child remained alert.",
            "first_aid_applied": first_aid,
            "further_action": "Parent handover completed and monitoring advised.",
            "witnesses": "Alex Lee, Instructor",
            "parent_notified": True,
        },
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["reference"].startswith("HVS-INC-")
    assert body["swimmer_number"].startswith("HVS-S-")
    assert body["family_customer_number"].startswith("HVS-")
    assert body["staff_number"].startswith("HVS-W-")
    with db_session() as db:
        raw = db.execute("SELECT what_happened,first_aid_applied FROM incident_reports WHERE id=?", (body["id"],)).fetchone()
        assert raw["what_happened"].startswith("enc:v1:") and happened not in raw["what_happened"]
        assert raw["first_aid_applied"].startswith("enc:v1:") and first_aid not in raw["first_aid_applied"]
        audit_detail = db.execute(
            "SELECT detail FROM audit_log WHERE action='create_incident_report' ORDER BY id DESC LIMIT 1"
        ).fetchone()["detail"]
        assert happened not in audit_detail and first_aid not in audit_detail
    staff_report = next(item for item in client.get("/api/staff/incidents").json()["reports"] if item["id"] == body["id"])
    assert staff_report["what_happened"] == happened
    assert staff_report["first_aid_applied"] == first_aid

    client.cookies.clear()
    sign_in(client, FAMILY)
    family_report = next(item for item in client.get("/api/customer/incidents").json()["reports"] if item["id"] == body["id"])
    assert family_report["reference"] == body["reference"]
    assert family_report["parent_notified"] is True
    assert client.get("/api/staff/incidents").status_code == 403

    client.cookies.clear()
    admin_csrf = sign_in(client, ADMIN)
    updated = client.patch(
        f"/api/admin/incidents/{body['id']}",
        json={"status": "follow_up"},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "follow_up"


def test_family_can_update_owned_child_safety_profile_without_auditing_health_text(client):
    from backend.database import db_session

    client.cookies.clear()
    csrf = sign_in(client, FAMILY)
    swimmer_id = client.get("/api/customer/swimmers").json()["swimmers"][0]["id"]
    allergy_text = "Test allergy profile 8421"
    response = client.patch(
        f"/api/customer/swimmers/{swimmer_id}",
        json={
            "emergency_contact": "Jordan Smith · 0413 000 101",
            "allergies": allergy_text,
            "medical_notes": "Lesson safety test note",
            "medications": "Medication test record",
            "support_notes": "Use short, calm instructions",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text
    updated = next(item for item in client.get("/api/customer/swimmers").json()["swimmers"] if item["id"] == swimmer_id)
    assert updated["allergies"] == allergy_text
    assert updated["support_notes"] == "Use short, calm instructions"
    assert client.patch(
        "/api/customer/swimmers/999999",
        json={"emergency_contact": "Someone · 0400 000 000"},
        headers={"X-CSRF-Token": csrf},
    ).status_code == 404
    with db_session() as db:
        audit_detail = db.execute(
            "SELECT detail FROM audit_log WHERE action='update_family_swimmer_safety_profile' ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    assert allergy_text not in audit_detail


def test_family_cannot_book_a_swimmer_it_does_not_own(client):
    client.cookies.clear()
    csrf = sign_in(client, FAMILY)
    response = client.post(
        "/api/customer/bookings",
        json={"class_id": 1, "swimmer_id": 999999},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code in (403, 404), response.text


def test_hv_achievement_templates_are_complete_and_authenticated(client):
    client.cookies.clear()
    assert client.get("/api/achievements/templates").status_code == 401
    sign_in(client, FAMILY)
    response = client.get("/api/achievements/templates")
    assert response.status_code == 200
    payload = response.json()
    templates = payload["templates"]
    assert len(templates) == 8
    assert {template["code"] for template in templates} == {
        "first-splash", "water-confidence", "bubble-breathing", "floating-star",
        "kicking-champion", "stroke-builder", "water-safety-hero", "personal-best",
    }
    assert len({template["certificate_style"] for template in templates}) == 8
    assert all(template["brand_label"] == "HV Swim School Bendigo" for template in templates)
    assert payload["certificate_rendering"] == "html_print"


def test_staff_achievement_eligibility_contains_only_confirmed_classes_they_instruct(client):
    from backend.database import db_session

    client.cookies.clear()
    sign_in(client, STAFF)
    staff_id = client.get("/api/auth/me").json()["user"]["id"]
    response = client.get("/api/staff/achievements")
    assert response.status_code == 200
    payload = response.json()
    assert payload["eligible_swimmers"]
    assert "customer_id" not in response.text
    assert "customer_email" not in response.text
    with db_session() as db:
        for item in payload["eligible_swimmers"]:
            eligible = db.execute(
                """SELECT 1 FROM bookings b JOIN classes c ON c.id=b.class_id
                   WHERE b.swimmer_id=? AND b.class_id=? AND b.status='confirmed' AND c.instructor_id=?""",
                (item["swimmer_id"], item["class_id"], staff_id),
            ).fetchone()
            assert eligible is not None


def test_staff_can_issue_and_revoke_an_achievement_with_family_safe_visibility(client):
    from backend.database import db_session

    private_marker = "Coach-only progression marker 8421"
    evidence = "Stayed relaxed, listened carefully and completed three controlled floats."
    client.cookies.clear()
    staff_csrf = sign_in(client, STAFF)
    eligible = client.get("/api/staff/achievements").json()["eligible_swimmers"][0]
    issued = client.post(
        "/api/staff/achievements",
        json={
            "template_code": "water-confidence",
            "swimmer_id": eligible["swimmer_id"],
            "class_id": eligible["class_id"],
            "evidence_note": evidence,
            "private_staff_note": private_marker,
        },
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert issued.status_code == 200, issued.text
    body = issued.json()
    award = body["achievement"]
    achievement_id = award["id"]
    reference = award["certificate_reference"]
    assert reference.startswith("HV-ACH-")
    assert len(reference.split("-")) >= 4
    assert award["certificate_style"] == "calm-current"
    assert award["private_staff_note"] == private_marker
    assert body["notification"] == {"in_app_delivered": True, "external_channels": {}}

    staff_listing = client.get("/api/staff/achievements").json()["achievements"]
    assert next(item for item in staff_listing if item["id"] == achievement_id)["private_staff_note"] == private_marker

    client.cookies.clear()
    sign_in(client, FAMILY)
    family_response = client.get("/api/customer/achievements")
    assert family_response.status_code == 200
    assert "private_staff_note" not in family_response.text
    assert private_marker not in family_response.text
    family_award = next(item for item in family_response.json()["achievements"] if item["certificate_reference"] == reference)
    assert family_award["evidence_note"] == evidence
    assert family_award["status"] == "active"
    notifications = client.get("/api/notifications").json()["notifications"]
    assert any(item["kind"] == "achievement" and reference in item["message"] for item in notifications)

    client.cookies.clear()
    staff_csrf = sign_in(client, STAFF)
    reason = "Issued against the wrong lesson observation."
    revoked = client.post(
        f"/api/staff/achievements/{achievement_id}/revoke",
        json={"reason": reason},
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["certificate_reference"] == reference

    client.cookies.clear()
    sign_in(client, FAMILY)
    family_award = next(
        item for item in client.get("/api/customer/achievements").json()["achievements"]
        if item["certificate_reference"] == reference
    )
    assert family_award["status"] == "revoked"
    assert family_award["revocation_reason"] == reason
    assert family_award["revoked_at"]

    with db_session() as db:
        issue_audit = db.execute(
            "SELECT detail,ip_address FROM audit_log WHERE action='issue_swimmer_achievement' AND entity_id=?",
            (str(achievement_id),),
        ).fetchone()
        revoke_audit = db.execute(
            "SELECT detail,ip_address FROM audit_log WHERE action='revoke_swimmer_achievement' AND entity_id=?",
            (str(achievement_id),),
        ).fetchone()
    assert issue_audit and reference in issue_audit["detail"] and issue_audit["ip_address"]
    assert revoke_audit and reason in revoke_audit["detail"] and revoke_audit["ip_address"]


def test_staff_cannot_award_outside_a_confirmed_class_they_instruct(client):
    from backend.database import db_session

    client.cookies.clear()
    staff_csrf = sign_in(client, STAFF)
    staff_id = client.get("/api/auth/me").json()["user"]["id"]
    eligible = client.get("/api/staff/achievements").json()["eligible_swimmers"][0]
    missing_class = client.post(
        "/api/staff/achievements",
        json={
            "template_code": "first-splash", "swimmer_id": eligible["swimmer_id"],
            "evidence_note": "A positive first lesson.", "private_staff_note": "",
        },
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert missing_class.status_code == 400

    with db_session() as db:
        foreign_class = db.execute(
            "SELECT id FROM classes WHERE instructor_id IS NOT NULL AND instructor_id<>? ORDER BY id LIMIT 1",
            (staff_id,),
        ).fetchone()
        assert foreign_class is not None
        db.execute(
            "INSERT OR IGNORE INTO bookings(class_id,swimmer_id,status,created_at) VALUES(?,?,?,?)",
            (foreign_class["id"], eligible["swimmer_id"], "confirmed", datetime.now(timezone.utc).isoformat()),
        )
    forbidden = client.post(
        "/api/staff/achievements",
        json={
            "template_code": "first-splash", "swimmer_id": eligible["swimmer_id"],
            "class_id": foreign_class["id"], "evidence_note": "A positive first lesson.",
            "private_staff_note": "Must not be stored",
        },
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert forbidden.status_code == 404


def test_admin_can_award_any_swimmer_but_family_ownership_and_revoke_roles_stay_isolated(client):
    from backend.database import db_session
    from backend.security import now_iso, password_hash

    second_email = "achievement-family@example.com"
    second_password = "AchievementFamily!2026"
    private_marker = "Management-only achievement note 5566"
    with db_session() as db:
        cursor = db.execute(
            """INSERT INTO users(email,password_hash,role,first_name,last_name,created_at)
               VALUES(?,?,?,?,?,?)""",
            (second_email, password_hash(second_password), "customer", "Riley", "Chen", now_iso()),
        )
        second_customer_id = cursor.lastrowid
        swimmer_id = db.execute(
            """INSERT INTO swimmers(customer_id,first_name,last_name,level,created_at)
               VALUES(?,?,?,?,?)""",
            (second_customer_id, "Ari", "Chen", "Program match required", now_iso()),
        ).lastrowid

    client.cookies.clear()
    admin_csrf = sign_in(client, ADMIN)
    issued = client.post(
        "/api/staff/achievements",
        json={
            "template_code": "personal-best", "swimmer_id": swimmer_id, "class_id": None,
            "evidence_note": "Showed persistence and achieved an individual goal.",
            "private_staff_note": private_marker,
        },
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert issued.status_code == 200, issued.text
    achievement_id = issued.json()["achievement"]["id"]
    reference = issued.json()["achievement"]["certificate_reference"]
    assert issued.json()["achievement"]["class_id"] is None
    admin_listing = client.get("/api/staff/achievements")
    assert private_marker in admin_listing.text

    client.cookies.clear()
    sign_in(client, FAMILY)
    assert reference not in client.get("/api/customer/achievements").text
    assert client.get("/api/staff/achievements").status_code == 403

    client.cookies.clear()
    sign_in(client, (second_email, second_password))
    second_family = client.get("/api/customer/achievements")
    assert reference in second_family.text
    assert private_marker not in second_family.text
    assert "private_staff_note" not in second_family.text

    client.cookies.clear()
    staff_csrf = sign_in(client, STAFF)
    staff_revoke = client.post(
        f"/api/staff/achievements/{achievement_id}/revoke",
        json={"reason": "Staff must not revoke a management-issued certificate."},
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert staff_revoke.status_code == 403

    client.cookies.clear()
    admin_csrf = sign_in(client, ADMIN)
    reason = "Management corrected the award recipient after review."
    revoked = client.post(
        f"/api/staff/achievements/{achievement_id}/revoke",
        json={"reason": reason},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert revoked.status_code == 200, revoked.text
    repeated = client.post(
        f"/api/staff/achievements/{achievement_id}/revoke",
        json={"reason": reason},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert repeated.status_code == 409

    client.cookies.clear()
    sign_in(client, (second_email, second_password))
    award = next(
        item for item in client.get("/api/customer/achievements").json()["achievements"]
        if item["certificate_reference"] == reference
    )
    assert award["status"] == "revoked"
    assert award["revocation_reason"] == reason


SUPPORT_WIDGET_PAYLOAD = {
    "category": "lessons",
    "name": "Morgan Rivers",
    "email": "morgan.support@example.com",
    "phone": "0412 345 678",
    "subject": "Help choosing the right lesson",
    "message": "Could the team help us choose the most suitable lesson for next term?",
    "consent_acknowledged": True,
    "website": "",
}


def test_support_portal_routes_require_the_correct_authenticated_role(client):
    client.cookies.clear()
    assert client.get("/api/support-tickets").status_code == 401
    assert client.get("/api/staff/support-tickets").status_code == 401
    sign_in(client, FAMILY)
    assert client.get("/api/staff/support-tickets").status_code == 403
    client.cookies.clear()
    sign_in(client, STAFF)
    assert client.get("/api/support-tickets").status_code == 403


def test_public_support_widget_creates_a_guest_ticket_without_pii_in_audit(client):
    from backend.database import db_session

    client.cookies.clear()
    response = client.post("/api/public/support-tickets", json=SUPPORT_WIDGET_PAYLOAD)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["received"] is True
    assert payload["reference"].startswith("HV-TKT-")
    assert payload["reference"] != f"HV-TKT-{payload['id']:04d}"
    assert payload["delivery"] == {"in_app": "delivered", "email": "not_implemented", "push": "not_implemented"}
    with db_session() as db:
        ticket = db.execute("SELECT * FROM support_tickets WHERE id=?", (payload["id"],)).fetchone()
        message = db.execute("SELECT * FROM support_messages WHERE ticket_id=?", (payload["id"],)).fetchone()
        audit_row = db.execute(
            "SELECT detail FROM audit_log WHERE action='create_public_support_ticket' AND entity_id=?",
            (str(payload["id"]),),
        ).fetchone()
    assert ticket and ticket["customer_id"] is None and ticket["source"] == "public_widget"
    assert message and message["author_role"] == "guest" and message["visibility"] == "customer"
    assert audit_row and payload["reference"] in audit_row["detail"]
    for pii in (SUPPORT_WIDGET_PAYLOAD["name"], SUPPORT_WIDGET_PAYLOAD["email"], SUPPORT_WIDGET_PAYLOAD["phone"], SUPPORT_WIDGET_PAYLOAD["subject"], SUPPORT_WIDGET_PAYLOAD["message"]):
        assert pii not in audit_row["detail"]


def test_support_honeypot_is_swallowed_without_storage_or_audit(client):
    from backend.database import db_session

    with db_session() as db:
        tickets_before = db.execute("SELECT COUNT(*) FROM support_tickets").fetchone()[0]
        audits_before = db.execute("SELECT COUNT(*) FROM audit_log WHERE action='create_public_support_ticket'").fetchone()[0]
    response = client.post(
        "/api/public/support-tickets",
        json={**SUPPORT_WIDGET_PAYLOAD, "email": "bot@example.com", "website": "https://spam.example", "consent_acknowledged": False},
    )
    assert response.status_code == 200
    assert response.json()["id"] == 0
    with db_session() as db:
        assert db.execute("SELECT COUNT(*) FROM support_tickets").fetchone()[0] == tickets_before
        assert db.execute("SELECT COUNT(*) FROM audit_log WHERE action='create_public_support_ticket'").fetchone()[0] == audits_before
    no_consent = client.post(
        "/api/public/support-tickets",
        json={**SUPPORT_WIDGET_PAYLOAD, "consent_acknowledged": False},
    )
    assert no_consent.status_code == 422
    unexpected_field = client.post(
        "/api/public/support-tickets",
        json={**SUPPORT_WIDGET_PAYLOAD, "unexpected": "must be rejected"},
    )
    assert unexpected_field.status_code == 422


def test_customer_support_tickets_require_csrf_and_are_ownership_isolated(client):
    from backend.database import db_session
    from backend.security import now_iso, password_hash

    client.cookies.clear()
    family_csrf = sign_in(client, FAMILY)
    body = {
        "category": "bookings",
        "subject": "Account booking question",
        "message": "Please help us understand the available class booking options.",
        "phone": "",
    }
    assert client.post("/api/support-tickets", json=body).status_code == 403
    created = client.post("/api/support-tickets", json=body, headers={"X-CSRF-Token": family_csrf})
    assert created.status_code == 200, created.text
    ticket_id = created.json()["id"]
    reference = created.json()["reference"]
    assert reference in client.get("/api/support-tickets").text

    other_email = "support-isolation@example.com"
    other_password = "SupportIsolation!2026"
    with db_session() as db:
        db.execute(
            "INSERT INTO users(email,password_hash,role,first_name,last_name,created_at) VALUES(?,?,?,?,?,?)",
            (other_email, password_hash(other_password), "customer", "Sam", "Taylor", now_iso()),
        )
    client.cookies.clear()
    other_csrf = sign_in(client, (other_email, other_password))
    assert reference not in client.get("/api/support-tickets").text
    forbidden = client.post(
        f"/api/support-tickets/{ticket_id}/replies",
        json={"message": "I must not be able to reply to this ticket."},
        headers={"X-CSRF-Token": other_csrf},
    )
    assert forbidden.status_code == 404

    client.cookies.clear()
    family_csrf = sign_in(client, FAMILY)
    reply = client.post(
        f"/api/support-tickets/{ticket_id}/replies",
        json={"message": "Here is the additional booking detail the team requested."},
        headers={"X-CSRF-Token": family_csrf},
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["status"] == "open"


def test_staff_support_queue_keeps_internal_notes_private_and_reports_delivery_boundaries(client):
    from backend.database import db_session

    client.cookies.clear()
    family_csrf = sign_in(client, FAMILY)
    created = client.post(
        "/api/support-tickets",
        json={
            "category": "app_help", "subject": "Portal message test",
            "message": "The family needs help finding a message inside the secure portal.", "phone": "",
        },
        headers={"X-CSRF-Token": family_csrf},
    )
    assert created.status_code == 200, created.text
    ticket_id = created.json()["id"]
    reference = created.json()["reference"]
    private_marker = "Internal investigation marker 7331"
    visible_marker = "The HV Swim team has checked your account message area."

    client.cookies.clear()
    staff_csrf = sign_in(client, STAFF)
    staff_id = client.get("/api/auth/me").json()["user"]["id"]
    queue = client.get("/api/staff/support-tickets")
    assert queue.status_code == 200 and reference in queue.text
    assert queue.json()["summary"]["guest"] >= 1
    assert client.get(f"/api/staff/support-tickets/{ticket_id}").status_code == 200
    assert client.post(
        f"/api/staff/support-tickets/{ticket_id}/replies",
        json={"message": private_marker, "internal_note": True},
    ).status_code == 403
    internal = client.post(
        f"/api/staff/support-tickets/{ticket_id}/replies",
        json={"message": private_marker, "internal_note": True},
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert internal.status_code == 200, internal.text
    assert internal.json()["visibility"] == "internal"
    visible = client.post(
        f"/api/staff/support-tickets/{ticket_id}/replies",
        json={"message": visible_marker, "internal_note": False},
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert visible.status_code == 200, visible.text
    assert visible.json()["delivery"] == {"in_app": "delivered", "email": "not_implemented", "push": "not_implemented"}
    update = client.patch(
        f"/api/staff/support-tickets/{ticket_id}",
        json={"assigned_to": staff_id, "priority": "urgent", "status": "open"},
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert update.status_code == 200, update.text
    assert update.json()["ticket"]["priority"] == "urgent"
    assert update.json()["ticket"]["assigned_to"] == staff_id

    client.cookies.clear()
    sign_in(client, FAMILY)
    family_ticket = next(item for item in client.get("/api/support-tickets").json()["tickets"] if item["id"] == ticket_id)
    family_text = str(family_ticket)
    assert visible_marker in family_text
    assert private_marker not in family_text
    assert "visibility" not in family_text

    client.cookies.clear()
    sign_in(client, STAFF)
    staff_detail = client.get(f"/api/staff/support-tickets/{ticket_id}").json()["ticket"]
    assert private_marker in str(staff_detail)
    with db_session() as db:
        audits = list(db.execute(
            "SELECT action,detail FROM audit_log WHERE entity_type='support_ticket' AND entity_id=?",
            (str(ticket_id),),
        ))
    assert {row["action"] for row in audits} >= {"add_support_internal_note", "reply_staff_support_ticket", "update_support_ticket"}
    assert all(private_marker not in row["detail"] and visible_marker not in row["detail"] for row in audits)


def test_public_support_tickets_are_rate_limited_per_connection(client):
    from backend.database import db_session

    client.cookies.clear()
    with db_session() as db:
        db.execute("DELETE FROM audit_log WHERE action='create_public_support_ticket'")
    statuses = []
    for index in range(5):
        payload = {
            **SUPPORT_WIDGET_PAYLOAD,
            "email": f"rate-{index}@example.com",
            "subject": f"Rate limit support message {index}",
        }
        statuses.append(client.post("/api/public/support-tickets", json=payload).status_code)
    assert statuses[:4] == [200, 200, 200, 200]
    assert statuses[4] == 429


def test_admin_alerts_are_public_only_while_active_and_require_csrf(client):
    from backend.database import db_session

    client.cookies.clear()
    admin_csrf = sign_in(client, ADMIN)
    location_id = client.get("/api/admin/locations").json()["locations"][0]["id"]
    alert_payload = {
        "severity": "information", "title": "Term timetable update",
        "message": "A new term timetable update is available from the HV Swim team.",
        "location_id": location_id,
    }
    assert client.post("/api/admin/alerts", json=alert_payload).status_code == 403
    created = client.post("/api/admin/alerts", json=alert_payload, headers={"X-CSRF-Token": admin_csrf})
    assert created.status_code == 200, created.text
    alert = created.json()["alert"]
    assert set(alert) == {"id", "severity", "title", "message", "location_name", "published_at"}
    assert created.json()["delivery"]["push"] == "not_implemented"
    assert any(item["id"] == alert["id"] for item in client.get("/api/admin/alerts").json()["alerts"])

    client.cookies.clear()
    public = client.get("/api/public/alerts")
    assert any(item["id"] == alert["id"] for item in public.json()["alerts"])
    assert public.json()["delivery"]["push"] == "not_implemented"

    client.cookies.clear()
    staff_csrf = sign_in(client, STAFF)
    assert client.post("/api/admin/alerts", json=alert_payload, headers={"X-CSRF-Token": staff_csrf}).status_code == 403

    client.cookies.clear()
    admin_csrf = sign_in(client, ADMIN)
    resolved = client.post(
        f"/api/admin/alerts/{alert['id']}/resolve",
        json={"reason": "The timetable notice has been acknowledged."},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert resolved.status_code == 200, resolved.text
    assert not any(item["id"] == alert["id"] for item in client.get("/api/public/alerts").json()["alerts"])
    repeated = client.post(
        f"/api/admin/alerts/{alert['id']}/resolve",
        json={"reason": "The timetable notice has been acknowledged."},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert repeated.status_code == 409
    with db_session() as db:
        actions = {row["action"] for row in db.execute("SELECT action FROM audit_log WHERE entity_type='public_alert' AND entity_id=?", (str(alert["id"]),))}
    assert actions >= {"create_public_alert", "resolve_public_alert"}


def test_pool_closure_alert_is_updated_then_resolved_with_a_reopening_notice(client):
    from backend.database import db_session

    client.cookies.clear()
    staff_csrf = sign_in(client, STAFF)
    closed = client.post(
        "/api/staff/pool-readings",
        json={"location_slug": "wood-street", "temperature": None, "status": "closed", "note": "Lessons are paused due to an unexpected pool closure."},
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert closed.status_code == 200, closed.text
    closure = closed.json()["public_alert"]
    assert closure["severity"] == "closure"
    assert closed.json()["delivery"]["push"] == "not_implemented"
    changed = client.post(
        "/api/staff/pool-readings",
        json={"location_slug": "wood-street", "temperature": 28.4, "status": "changed", "note": "Pool access remains changed while the venue team completes checks."},
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["public_alert"]["id"] == closure["id"]
    assert changed.json()["public_alert"]["severity"] == "change"

    reopened = client.post(
        "/api/staff/pool-readings",
        json={"location_slug": "wood-street", "temperature": 29.1, "status": "open", "note": "Pool checks are complete and lessons can resume."},
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert reopened.status_code == 200, reopened.text
    reopening = reopened.json()["public_alert"]
    assert reopening and reopening["severity"] == "reopening"
    assert reopening["id"] != closure["id"]
    active = client.get("/api/public/alerts").json()["alerts"]
    assert not any(item["id"] == closure["id"] for item in active)
    assert any(item["id"] == reopening["id"] for item in active)

    second_open = client.post(
        "/api/staff/pool-readings",
        json={"location_slug": "wood-street", "temperature": 29.2, "status": "open", "note": "Lessons continue as normal."},
        headers={"X-CSRF-Token": staff_csrf},
    )
    assert second_open.status_code == 200
    assert second_open.json()["public_alert"] is None
    with db_session() as db:
        assert db.execute("SELECT status FROM public_alerts WHERE id=?", (closure["id"],)).fetchone()["status"] == "resolved"
        audit_actions = {row["action"] for row in db.execute("SELECT action FROM audit_log WHERE entity_type='public_alert'")}
    assert {"sync_pool_public_alert", "reopen_pool_public_alert"} <= audit_actions


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


def test_staff_clock_records_breaks_and_paid_hours_without_location_tracking(client):
    client.cookies.clear()
    csrf = sign_in(client, STAFF)
    headers = {"X-CSRF-Token": csrf}
    profile = client.get("/api/auth/me").json()["user"]
    assert profile["staff_number"].startswith("HVS-W-")
    clock_on = client.post("/api/staff/clock", json={"action": "in", "location_slug": "wood-street"}, headers=headers)
    assert clock_on.status_code == 200, clock_on.text
    assert clock_on.json()["state"] == "working"
    duplicate = client.post("/api/staff/clock", json={"action": "in", "location_slug": "wood-street"}, headers=headers)
    assert duplicate.status_code == 409
    break_start = client.post("/api/staff/clock", json={"action": "break_start", "location_slug": "wood-street"}, headers=headers)
    assert break_start.status_code == 200, break_start.text
    assert break_start.json()["state"] == "on_break"
    break_end = client.post("/api/staff/clock", json={"action": "break_end", "location_slug": "wood-street"}, headers=headers)
    assert break_end.status_code == 200, break_end.text
    assert break_end.json()["break_minutes"] >= 1
    clock_off = client.post("/api/staff/clock", json={"action": "out", "location_slug": "wood-street"}, headers=headers)
    assert clock_off.status_code == 200, clock_off.text
    assert clock_off.json()["state"] == "clocked_off"
    records = client.get("/api/staff/time-entries").json()["time_entries"]
    recorded = next(item for item in records if item["id"] == clock_on.json()["entry_id"])
    assert recorded["clock_out"]
    assert recorded["break_minutes"] >= 1
    assert recorded["latitude"] is None and recorded["longitude"] is None


def test_family_absence_credit_limit_and_financial_boundary(client):
    client.cookies.clear()
    csrf = sign_in(client, FAMILY)
    data = client.get("/api/customer/absences")
    assert data.status_code == 200, data.text
    payload = data.json()
    assert payload["term"]["configured"] is True
    assert payload["term"]["is_preview"] is True
    assert payload["policy"]["financial_boundary"].startswith("An eligible absence credit")
    booking = next(item for item in payload["bookings"] if item["title"] == "Learn to Swim 3")
    first_date = date.fromisoformat(booking["next_occurrence"])
    statuses = []
    for week in range(3):
        response = client.post(
            "/api/customer/absences",
            json={
                "booking_id": booking["booking_id"],
                "occurrence_date": (first_date + timedelta(days=7 * week)).isoformat(),
                "reason_category": "family",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200, response.text
        assert response.json()["financial_adjustment"] == "not_automatic"
        statuses.append(response.json()["credit_status"])
    assert statuses == ["credited", "credited", "recorded_no_credit"]

    duplicate = client.post(
        "/api/customer/absences",
        json={"booking_id": booking["booking_id"], "occurrence_date": first_date.isoformat(), "reason_category": "other"},
        headers={"X-CSRF-Token": csrf},
    )
    assert duplicate.status_code == 409


def test_lesson_register_enforces_assignment_parent_and_photo_rules(client):
    client.cookies.clear()
    sign_in(client, FAMILY)
    absence_data = client.get("/api/customer/absences").json()
    booking = next(item for item in absence_data["bookings"] if item["title"] == "Learn to Swim 3")
    term_start = date.fromisoformat(absence_data["term"]["start_date"])
    occurrence = (term_start + timedelta(days=(3 - term_start.weekday()) % 7)).isoformat()

    client.cookies.clear()
    csrf = sign_in(client, STAFF)
    register = client.get(f"/api/staff/lesson-register?occurrence_date={occurrence}")
    assert register.status_code == 200, register.text
    class_item = next(item for item in register.json()["classes"] if item["title"] == "Learn to Swim 3")
    swimmer = next(item for item in class_item["register"] if item["booking_id"] == booking["booking_id"])
    assert class_item["parent_onsite_required"] is True
    assert swimmer["reported_absence"] is False
    assert swimmer["photo_consent"] is True

    future = client.post(
        "/api/staff/lesson-register",
        json={"booking_id": booking["booking_id"], "occurrence_date": booking["next_occurrence"], "attendance_status": "excused", "parent_onsite_confirmed": None, "private_note": ""},
        headers={"X-CSRF-Token": csrf},
    )
    assert future.status_code == 422

    missing_parent = client.post(
        "/api/staff/lesson-register",
        json={"booking_id": booking["booking_id"], "occurrence_date": occurrence, "attendance_status": "present", "parent_onsite_confirmed": None, "private_note": ""},
        headers={"X-CSRF-Token": csrf},
    )
    assert missing_parent.status_code == 422
    saved = client.post(
        "/api/staff/lesson-register",
        json={"booking_id": booking["booking_id"], "occurrence_date": occurrence, "attendance_status": "present", "parent_onsite_confirmed": True, "private_note": "Test-only safe lesson note"},
        headers={"X-CSRF-Token": csrf},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["photo_clearance"] is True

    client.cookies.clear()
    sign_in(client, FAMILY)
    assert client.get(f"/api/staff/lesson-register?occurrence_date={occurrence}").status_code == 403


def test_management_term_and_payment_routes_are_explicit(client):
    client.cookies.clear()
    csrf = sign_in(client, ADMIN)
    terms = client.get("/api/admin/term-operations")
    assert terms.status_code == 200
    assert terms.json()["policy"]["payment_route"] == "xero_invoice_workflow"
    draft = client.post(
        "/api/admin/terms",
        json={"name": "Test future term", "start_date": "2030-01-01", "end_date": "2030-03-31", "absence_credit_limit": 2, "activate": False},
        headers={"X-CSRF-Token": csrf},
    )
    assert draft.status_code == 200, draft.text
    assert draft.json()["status"] == "draft"
    activated = client.post(
        f"/api/admin/terms/{draft.json()['id']}/activate",
        headers={"X-CSRF-Token": csrf},
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"
    assert client.get("/api/classes").json()["term_calendar"]["name"] == "Test future term"
    routes = client.get("/api/admin/integrations").json()["payment_routing"]
    assert {(item["category"], item["provider"]) for item in routes} == {
        ("Lesson enrolments & term fees", "Xero"),
        ("Absence credits", "Xero"),
        ("Merchandise & staff uniforms", "Shopify"),
    }


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


def test_staff_clock_rejects_location_coordinates_in_payload(client):
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
