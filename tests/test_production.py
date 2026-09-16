"""Production-startup safety and first-account bootstrap tests."""

from __future__ import annotations

from dataclasses import replace
import sqlite3

import pytest

from backend import config, database, server


def production_settings(**changes):
    values = {
        "app_env": "production",
        "database_url": "postgresql://test:test@database.example.test/hv?sslmode=verify-full",
        "session_secret": "a-unique-production-secret-with-32-plus-characters",
        "data_encryption_key": "a-separate-production-data-key-with-32-plus-characters",
        "public_url": "https://swim.example.test",
        "xero_client_id": "",
        "xero_client_secret": "",
        "xero_redirect_uri": "https://swim.example.test/api/integrations/xero/callback",
        "bootstrap_admin_email": "",
        "bootstrap_admin_password": "",
        "trusted_proxies": ("203.0.113.50",),
    }
    values.update(changes)
    return replace(config.settings, **values)


def test_documented_environment_name_enables_production(monkeypatch):
    monkeypatch.setenv("HV_APP_ENV", "production")
    monkeypatch.delenv("HV_ENVIRONMENT", raising=False)
    assert config.resolved_app_environment() == "production"


def test_conflicting_legacy_environment_names_fail_closed(monkeypatch):
    monkeypatch.setenv("HV_APP_ENV", "production")
    monkeypatch.setenv("HV_ENVIRONMENT", "development")
    with pytest.raises(RuntimeError, match="disagree"):
        config.resolved_app_environment()


@pytest.mark.parametrize(
    "secret",
    (
        "local-demo-secret-change-before-production",
        "replace-with-a-long-random-production-secret",
        "too-short",
    ),
)
def test_production_rejects_placeholder_or_short_session_secrets(secret):
    with pytest.raises(RuntimeError, match="HV_SESSION_SECRET"):
        server.validate_production_config(production_settings(session_secret=secret))


def test_production_requires_a_separate_customer_data_encryption_key():
    with pytest.raises(RuntimeError, match="HV_DATA_ENCRYPTION_KEY"):
        server.validate_production_config(production_settings(data_encryption_key="too-short"))
    with pytest.raises(RuntimeError, match="HV_DATA_ENCRYPTION_KEY"):
        server.validate_production_config(
            production_settings(data_encryption_key="a-unique-production-secret-with-32-plus-characters")
        )


def test_production_requires_trusted_reverse_proxy_configuration():
    with pytest.raises(RuntimeError, match="HV_TRUSTED_PROXIES"):
        server.validate_production_config(production_settings(trusted_proxies=()))


def test_production_requires_https_for_public_and_xero_urls():
    with pytest.raises(RuntimeError, match="HV_PUBLIC_URL"):
        server.validate_production_config(production_settings(public_url="http://swim.example.test"))
    with pytest.raises(RuntimeError, match="XERO_REDIRECT_URI"):
        server.validate_production_config(
            production_settings(
                xero_client_id="client",
                xero_client_secret="secret",
                xero_redirect_uri="http://swim.example.test/api/integrations/xero/callback",
            )
        )


def test_production_rejects_partial_shopify_and_insecure_sensor_configuration():
    with pytest.raises(RuntimeError, match="SHOPIFY_STORE_DOMAIN"):
        server.validate_production_config(
            production_settings(shopify_store_domain="shop.example.test", shopify_storefront_token="")
        )
    with pytest.raises(RuntimeError, match="hostname"):
        server.validate_production_config(
            production_settings(
                shopify_store_domain="http://shop.example.test/catalogue",
                shopify_storefront_token="storefront-token",
            )
        )
    with pytest.raises(RuntimeError, match="POOL_SENSOR_URL"):
        server.validate_production_config(
            production_settings(pool_sensor_url="http://pool-device.local/reading")
        )


def test_xero_invoice_transmission_cannot_start_with_partial_accounting_configuration():
    with pytest.raises(RuntimeError, match="complete Xero OAuth"):
        server.validate_production_config(production_settings(xero_sync_enabled=True))
    with pytest.raises(RuntimeError, match="XERO_LESSON_ACCOUNT_CODE"):
        server.validate_production_config(
            production_settings(
                xero_sync_enabled=True,
                xero_client_id="client",
                xero_client_secret="secret",
                xero_redirect_uri="https://swim.example.test/api/integrations/xero/callback",
            )
        )


def test_production_rejects_incomplete_or_insecure_social_signin_configuration():
    with pytest.raises(RuntimeError, match="GOOGLE_CLIENT_ID"):
        server.validate_production_config(production_settings(google_client_id="client"))
    with pytest.raises(RuntimeError, match="GOOGLE_REDIRECT_URI"):
        server.validate_production_config(
            production_settings(
                google_client_id="client",
                google_client_secret="secret",
                google_redirect_uri="http://swim.example.test/api/auth/oauth/google/callback",
            )
        )
    with pytest.raises(RuntimeError, match="APPLE_CLIENT_ID"):
        server.validate_production_config(production_settings(apple_client_id="com.example.web"))
    with pytest.raises(RuntimeError, match="APPLE_REDIRECT_URI"):
        server.validate_production_config(
            production_settings(
                apple_client_id="com.example.web",
                apple_client_secret="signed-client-secret",
                apple_redirect_uri="http://swim.example.test/api/auth/oauth/apple/callback",
            )
        )


def test_data_directory_and_database_use_restrictive_permissions(tmp_path, monkeypatch):
    import stat

    db_path = tmp_path / "secure-data" / "hv_swim.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    database.initialise_database()
    assert stat.S_IMODE(db_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(db_path.stat().st_mode) == 0o600


def test_empty_production_database_requires_and_uses_one_time_admin_bootstrap(tmp_path, monkeypatch):
    db_path = tmp_path / "production.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr(database, "settings", production_settings(database_url=""))
    with pytest.raises(RuntimeError, match="HV_BOOTSTRAP_ADMIN"):
        database.initialise_database()

    monkeypatch.setattr(
        database,
        "settings",
        production_settings(
            database_url="",
            bootstrap_admin_email="owner@example.test",
            bootstrap_admin_password="OneTimeBootstrap!2026",
            bootstrap_admin_name="HV Swim Owner",
        ),
    )
    database.initialise_database()
    with database.db_session() as db:
        users = list(db.execute("SELECT email,role FROM users"))
        locations = list(db.execute("SELECT slug FROM locations ORDER BY slug"))
    assert [(row["email"], row["role"]) for row in users] == [("owner@example.test", "admin")]
    assert not any(row["email"].endswith("@hvswim.demo") for row in users)
    assert [row["slug"] for row in locations] == ["bendigo-east", "wood-street"]


def test_legacy_booking_constraint_is_migrated_without_losing_history(tmp_path):
    db = sqlite3.connect(tmp_path / "legacy.db")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE classes(id INTEGER PRIMARY KEY);
        CREATE TABLE swimmers(id INTEGER PRIMARY KEY);
        INSERT INTO classes(id) VALUES(1);
        INSERT INTO swimmers(id) VALUES(1);
        CREATE TABLE bookings (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          class_id INTEGER NOT NULL REFERENCES classes(id),
          swimmer_id INTEGER NOT NULL REFERENCES swimmers(id),
          status TEXT NOT NULL CHECK (status IN ('confirmed','cancelled','completed')),
          created_at TEXT NOT NULL,
          UNIQUE(class_id, swimmer_id, status)
        );
        CREATE INDEX idx_bookings_class ON bookings(class_id,status);
        INSERT INTO bookings(class_id,swimmer_id,status,created_at) VALUES(1,1,'cancelled','2026-01-01');
        """
    )
    database.migrate_legacy_bookings_table(db)
    table_sql = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='bookings'").fetchone()[0]
    assert "UNIQUE(class_id, swimmer_id, status)" not in table_sql
    db.execute("INSERT INTO bookings(class_id,swimmer_id,status,created_at) VALUES(1,1,'cancelled','2026-02-01')")
    assert db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0] == 2
    db.close()
