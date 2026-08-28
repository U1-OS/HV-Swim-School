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


def test_public_site_serves_only_explicitly_approved_files(client):
    for path in ("/", "/index.html", "/assets/styles.css", "/service-worker.js", "/robots.txt"):
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
