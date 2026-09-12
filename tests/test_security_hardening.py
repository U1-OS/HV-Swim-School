"""Controlled negative tests against synthetic databases; no external provider calls."""
import csv
import io
from dataclasses import replace

import pytest

from test_api import client, sign_in, FAMILY
from test_production import production_settings


def test_unsafe_production_settings_fail_closed():
    from backend import server
    cases = [
        ({"database_url": ""}, "HV_DATABASE_URL"),
        ({"public_url": "https://"}, "HV_PUBLIC_URL"),
        ({"public_url": "https://user:password@site.example.test"}, "HV_PUBLIC_URL"),
        ({"public_url": "https://site.example.test/path"}, "HV_PUBLIC_URL"),
        ({"public_url": "https://site.example.test?redirect=evil"}, "HV_PUBLIC_URL"),
        ({"data_encryption_key": "replace-with-a-separate-random-data-encryption-key"}, "HV_DATA_ENCRYPTION_KEY"),
        ({"app_env": "prod"}, "HV_APP_ENV"),
    ]
    for values, message in cases:
        with pytest.raises(RuntimeError, match=message):
            server.validate_production_config(production_settings(**values))
    server.validate_production_config(production_settings(shopify_store_domain="swim.myshopify.com", shopify_storefront_token="synthetic-token"))


def test_environment_names_are_normalized_and_staging_is_hardened(monkeypatch):
    from backend import config
    monkeypatch.delenv("HV_ENVIRONMENT", raising=False)
    monkeypatch.setenv("HV_APP_ENV", "Production ")
    assert config.resolved_app_environment() == "production"
    monkeypatch.setenv("HV_APP_ENV", "prod")
    with pytest.raises(RuntimeError, match="HV_APP_ENV"):
        config.resolved_app_environment()
    assert replace(config.settings, app_env="staging").production


def test_production_rejects_preview_database_without_deleting_it(tmp_path, monkeypatch):
    from backend import database
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "preview.db")
    monkeypatch.setattr(database, "settings", replace(database.settings, app_env="development", database_url=""))
    database.initialise_database()
    with database.db_session() as db:
        before = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    monkeypatch.setattr(database, "settings", production_settings(database_url=""))
    with pytest.raises(RuntimeError, match="preview database"):
        database.initialise_database()
    with database.db_session() as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == before


def test_login_budgets_survive_ip_rotation_and_account_spraying(client):
    from backend import server
    from backend.database import db_session
    from backend.security import now_iso

    email = "isolated-throttle@example.com"
    with db_session() as db:
        db.execute("DELETE FROM login_attempts")
    try:
        with db_session() as db:
            for index in range(server.LOGIN_FAILURE_LIMIT_ACCOUNT):
                db.execute(
                    "INSERT INTO login_attempts(email,ip_address,success,created_at) VALUES(?,?,0,?)",
                    (email, f"192.0.2.{index}", now_iso()),
                )
            assert server.login_throttle_reason(db, email, "192.0.2.250") == "account"
            for index in range(server.LOGIN_FAILURE_LIMIT_IP):
                db.execute(
                    "INSERT INTO login_attempts(email,ip_address,success,created_at) VALUES(?,?,0,?)",
                    (f"spray{index}@example.com", "198.51.100.1", now_iso()),
                )
            assert server.login_throttle_reason(db, "new-account@example.com", "198.51.100.1") == "ip"
    finally:
        with db_session() as db:
            db.execute("DELETE FROM login_attempts")


def test_non_ascii_mfa_codes_are_rejected_without_exception():
    from backend.identity import matching_counter
    for code in ("١٢٣٤٥٦", "１２３４５６", "12345a"):
        assert matching_counter("JBSWY3DPEHPK3PXP", code) is None


def test_validation_errors_do_not_echo_private_input(client):
    response = client.post("/api/auth/login", json={"email": "invalid-private-email", "password": "Z!q7"})
    assert response.status_code == 422
    assert "invalid-private-email" not in response.text and "Z!q7" not in response.text
    assert all("input" not in error and "ctx" not in error for error in response.json()["detail"])


def test_csv_formula_protection_includes_whitespace():
    from backend.server import csv_download
    values = ["=1+1", " =1+1", "\n=1+1", "\u00a0=1+1", "normal text"]
    response = csv_download("test.csv", ["Value"], [[value] for value in values])
    exported = list(csv.reader(io.StringIO(response.body.decode())))[1:]
    assert [row[0] for row in exported] == ["'" + value for value in values[:-1]] + [values[-1]]


def test_cart_rejects_unapproved_variant_before_provider_call(client, monkeypatch):
    from backend import server
    client.cookies.clear()
    csrf = sign_in(client, FAMILY)
    monkeypatch.setattr(server, "shopify_ready", lambda: True)
    async def forbidden(*args, **kwargs):
        pytest.fail("Unapproved option reached Shopify")
    monkeypatch.setattr(server, "shopify_create_cart", forbidden)
    monkeypatch.setattr(server, "shopify_products", forbidden)
    response = client.post("/api/products/cart", json={"variant_id": "gid://shopify/ProductVariant/UNAPPROVED_SYNTHETIC", "quantity": 1}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 409, response.text


def test_existing_family_email_cannot_silently_link_new_provider_identity(client, monkeypatch):
    from backend import server
    from backend.database import db_session
    from test_api import _oauth_start
    client.cookies.clear()
    state = _oauth_start(client, monkeypatch, server, "google")
    async def exchange(*args, **kwargs): return {"id_token": "synthetic"}
    monkeypatch.setattr(server, "oauth_exchange_code", exchange)
    monkeypatch.setattr(server, "oauth_verify_identity_token", lambda *args, **kwargs: {"sub": "unlinked-synthetic-subject", "email": FAMILY[0], "email_verified": True})
    result = client.get(f"/api/auth/oauth/google/callback?state={state}&code=synthetic", follow_redirects=False)
    assert result.headers["location"].endswith("oauth_error=account_link_required")
    assert client.get("/api/auth/me").status_code == 401
    with db_session() as db:
        assert not db.execute("SELECT 1 FROM oauth_identities WHERE subject='unlinked-synthetic-subject'").fetchone()


def test_mfa_setup_is_session_bound_expiring_and_cannot_replace_enabled_secret(client, monkeypatch):
    from backend import identity
    from backend.database import db_session
    from test_api import STAFF
    client.cookies.clear()
    csrf = sign_in(client, STAFF)
    user_id = client.get("/api/auth/me").json()["user"]["id"]
    first_cookie = client.cookies.get("hv_session")
    result = client.post("/api/account/mfa/setup", json={"password": STAFF[1]}, headers={"X-CSRF-Token": csrf})
    assert result.status_code == 200
    secret = result.json()["secret"]
    code = identity.totp(secret, identity.current_counter())
    try:
        client.cookies.clear()
        second_csrf = sign_in(client, STAFF)
        assert client.post("/api/account/mfa/confirm", json={"password": STAFF[1], "code": code}, headers={"X-CSRF-Token": second_csrf}).status_code == 409
        client.cookies.clear()
        client.cookies.set("hv_session", first_cookie)
        with db_session() as db:
            db.execute("UPDATE account_mfa SET pending_expires_at='2000-01-01' WHERE user_id=?", (user_id,))
        assert client.post("/api/account/mfa/confirm", json={"password": STAFF[1], "code": code}, headers={"X-CSRF-Token": csrf}).status_code == 409
        with db_session() as db:
            db.execute("UPDATE account_mfa SET pending_expires_at='2999-01-01' WHERE user_id=?", (user_id,))
            db.execute("UPDATE users SET mfa_enabled=1 WHERE id=?", (user_id,))
        assert client.post("/api/account/mfa/confirm", json={"password": STAFF[1], "code": code}, headers={"X-CSRF-Token": csrf}).status_code == 409
        assert client.post("/api/account/mfa/setup", json={"password": STAFF[1]}, headers={"X-CSRF-Token": csrf}).status_code == 409
    finally:
        with db_session() as db:
            db.execute("UPDATE users SET mfa_enabled=0 WHERE id=?", (user_id,))
            db.execute("DELETE FROM account_mfa WHERE user_id=?", (user_id,))


def test_cart_requires_approval_audience_and_live_variant(client, monkeypatch):
    from backend import server
    from backend.database import db_session
    client.cookies.clear()
    csrf = sign_in(client, FAMILY)
    monkeypatch.setattr(server, "settings", replace(server.settings, commerce_live_approved=True))
    monkeypatch.setattr(server, "shopify_ready", lambda: True)
    monkeypatch.setattr(server, "public_feature_controls", lambda db: {"merch_home": {"effective_enabled": True}})
    with db_session() as db:
        record = dict(db.execute("SELECT * FROM products ORDER BY id LIMIT 1").fetchone())
        db.execute("UPDATE products SET status='available',sample_status='approved',price_cents=5000,cost_cents=2000,sizes='[\"Standard\"]',shopify_gid='gid://shopify/Product/QA',supplier_route='vistaprint',supplier_reference='synthetic proof',audience='staff' WHERE id=?", (record["id"],))
    variant = "gid://shopify/ProductVariant/APPROVED_SYNTHETIC"
    available = False
    calls = []
    async def catalogue():
        return [{"id": "gid://shopify/Product/QA", "variants": {"edges": [{"node": {"id": variant, "availableForSale": available}}]}}]
    async def cart(*args): calls.append(args); return {"id": "synthetic-cart", "checkoutUrl": "https://shop.example.test/checkout"}
    monkeypatch.setattr(server, "shopify_products", catalogue)
    monkeypatch.setattr(server, "shopify_create_cart", cart)
    try:
        payload = {"variant_id": variant, "quantity": 1}
        headers = {"X-CSRF-Token": csrf}
        assert client.post("/api/products/cart", json=payload, headers=headers).status_code == 409
        with db_session() as db: db.execute("UPDATE products SET audience='family' WHERE id=?", (record["id"],))
        assert client.post("/api/products/cart", json=payload, headers=headers).status_code == 409
        assert not calls
        available = True
        assert client.post("/api/products/cart", json=payload, headers=headers).status_code == 200
        assert calls == [(variant, 1)]
    finally:
        with db_session() as db:
            columns = [key for key in record if key != "id"]
            db.execute("UPDATE products SET " + ",".join(key + "=?" for key in columns) + " WHERE id=?", [record[key] for key in columns] + [record["id"]])
