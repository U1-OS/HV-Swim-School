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
    for path in ("/api/staff/roster", "/api/staff/time-entries", "/api/admin/metrics", "/api/admin/dashboard"):
        assert client.get(path).status_code == 403, path


def test_staff_account_cannot_reach_management(client):
    client.cookies.clear()
    sign_in(client, STAFF)
    for path in ("/api/admin/metrics", "/api/admin/dashboard"):
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


def test_management_can_reach_its_own_surfaces(client):
    client.cookies.clear()
    sign_in(client, ADMIN)
    for path in ("/api/admin/metrics", "/api/admin/dashboard"):
        assert client.get(path).status_code == 200, path


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


# --- secrets --------------------------------------------------------------------------

def test_integration_status_never_returns_credentials(client):
    client.cookies.clear()
    sign_in(client, ADMIN)
    body = client.get("/api/admin/dashboard").text.lower()
    for secret in ("client_secret", "storefront_token", "api_token", "password_hash", "csrf_token"):
        assert secret not in body, f"{secret} is exposed in the management dashboard payload"
