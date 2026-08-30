"""Small integration-boundary tests that never make external network calls."""

import asyncio
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from nacl.secret import SecretBox

from backend import integrations
from backend.integrations import decrypt_json, encrypt_json


def test_integration_tokens_are_authenticated_encrypted_and_round_trip():
    token = {
        "access_token": "private-access-token",
        "refresh_token": "private-refresh-token",
        "tenant_id": "tenant-123",
    }
    encrypted = encrypt_json(token)
    assert isinstance(encrypted, bytes)
    assert b"private-access-token" not in encrypted
    assert b"private-refresh-token" not in encrypted
    assert decrypt_json(encrypted) == token


def test_legacy_integration_tokens_are_read_then_rewritten_with_the_data_key(monkeypatch):
    configured = replace(
        integrations.settings,
        session_secret="legacy-session-secret-for-token-migration",
        data_encryption_key="separate-production-data-key-for-integrations",
    )
    monkeypatch.setattr(integrations, "settings", configured)
    token = {"access_token": "legacy-access", "tenant_id": "tenant-legacy"}
    legacy_box = SecretBox(hashlib.sha256(configured.session_secret.encode("utf-8")).digest())
    legacy = bytes(legacy_box.encrypt(json.dumps(token).encode("utf-8")))

    assert not integrations.integration_token_encryption_current(legacy)
    assert decrypt_json(legacy) == token
    migrated = encrypt_json(token)
    assert integrations.integration_token_encryption_current(migrated)
    assert decrypt_json(migrated) == token


def test_reviewed_xero_invoice_is_draft_idempotent_and_uses_configured_accounting_codes(monkeypatch):
    captured = {}

    class Response:
        is_success = True

        def raise_for_status(self):
            return None

        def json(self):
            return {"Invoices": [{"InvoiceID": "invoice-101", "Status": "DRAFT"}]}

    class Client:
        def __init__(self, **_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url, *, json, headers):
            captured.update({"url": url, "json": json, "headers": headers})
            return Response()

    monkeypatch.setattr(integrations.httpx, "AsyncClient", Client)
    monkeypatch.setattr(
        integrations,
        "settings",
        replace(
            integrations.settings,
            xero_lesson_account_code="200",
            xero_lesson_tax_type="OUTPUT",
            xero_line_amount_type="Inclusive",
            public_url="https://swim.example.test",
        ),
    )
    token = {
        "access_token": "access",
        "tenant_id": "tenant-101",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat(),
    }
    invoice = {
        "xero_contact_id": "contact-101",
        "issue_date": "2026-08-31",
        "due_date": "2026-08-31",
        "invoice_number": "HVS-2026-00001",
        "customer_number": "HVS-000001",
        "idempotency_key": "hv-invoice-fixed-test-key",
    }
    lines = [{"description": "Term lessons · HVS-S-000001", "quantity": 8, "unit_amount_cents": 2250}]

    _, result = asyncio.run(integrations.xero_create_draft_invoice(token, invoice=invoice, lines=lines))

    assert result["InvoiceID"] == "invoice-101"
    assert captured["url"] == integrations.XERO_INVOICES
    assert captured["headers"]["Idempotency-Key"] == "hv-invoice-fixed-test-key"
    assert captured["headers"]["Xero-tenant-id"] == "tenant-101"
    draft = captured["json"]["Invoices"][0]
    assert draft["Status"] == "DRAFT"
    assert draft["Contact"] == {"ContactID": "contact-101"}
    assert draft["Reference"] == "HVS-000001"
    assert draft["LineAmountTypes"] == "Inclusive"
    assert draft["LineItems"] == [
        {
            "Description": "Term lessons · HVS-S-000001",
            "Quantity": 8,
            "UnitAmount": 22.5,
            "AccountCode": "200",
            "TaxType": "OUTPUT",
        }
    ]


def test_xero_refresh_rejects_a_different_invoice_id(monkeypatch):
    class Response:
        is_success = False

        def raise_for_status(self):
            return None

        def json(self):
            return {"Invoices": [{"InvoiceID": "unexpected-invoice", "Status": "DRAFT"}]}

    class Client:
        def __init__(self, **_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(integrations.httpx, "AsyncClient", Client)
    token = {
        "access_token": "access",
        "tenant_id": "tenant-101",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat(),
    }
    with pytest.raises(RuntimeError, match="different invoice"):
        asyncio.run(integrations.xero_get_invoice(token, "expected-invoice"))


def test_xero_online_invoice_url_accepts_only_the_xero_customer_host():
    assert integrations.safe_xero_online_invoice_url("https://in.xero.com/Invoice/abc") == "https://in.xero.com/Invoice/abc"
    assert integrations.safe_xero_online_invoice_url("http://in.xero.com/Invoice/abc") is None
    assert integrations.safe_xero_online_invoice_url("https://in.xero.com.evil.example/Invoice/abc") is None
    assert integrations.safe_xero_online_invoice_url("https://user@in.xero.com/Invoice/abc") is None


def test_shopify_cart_rejects_top_level_graphql_errors(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"errors": [{"message": "Variant is unavailable"}]}

    class Client:
        def __init__(self, **_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(integrations.httpx, "AsyncClient", Client)
    monkeypatch.setattr(
        integrations,
        "settings",
        replace(integrations.settings, shopify_store_domain="shop.example", shopify_storefront_token="token"),
    )
    with pytest.raises(RuntimeError, match="Variant is unavailable"):
        asyncio.run(integrations.shopify_create_cart("gid://shopify/ProductVariant/123", 1))
