from __future__ import annotations

import hashlib
import json
import asyncio
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Any
from urllib.parse import urlencode

import httpx
from nacl.secret import SecretBox

from .config import settings

XERO_AUTHORIZE = "https://login.xero.com/identity/connect/authorize"
XERO_TOKEN = "https://identity.xero.com/connect/token"
XERO_CONNECTIONS = "https://api.xero.com/connections"
XERO_INVOICES = "https://api.xero.com/api.xro/2.0/Invoices"
XERO_SCOPES = "openid profile email offline_access accounting.transactions payroll.employees payroll.timesheets"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_CUSTOMER = "https://customer-api.open-meteo.com/v1/forecast"
PRINTIFY_API = "https://api.printify.com/v1"

_weather_cache: dict[str, Any] | None = None
_weather_cache_expires = 0.0
_weather_cache_stored = 0.0
_weather_lock = asyncio.Lock()
_shopify_cache: list[dict[str, Any]] | None = None
_shopify_cache_expires = 0.0
_shopify_lock = asyncio.Lock()


def _secret_box() -> SecretBox:
    key = hashlib.sha256(settings.session_secret.encode("utf-8")).digest()
    return SecretBox(key)


def encrypt_json(value: dict[str, Any]) -> bytes:
    return bytes(_secret_box().encrypt(json.dumps(value).encode("utf-8")))


def decrypt_json(value: bytes | None) -> dict[str, Any]:
    if not value:
        return {}
    return json.loads(_secret_box().decrypt(bytes(value)).decode("utf-8"))


def xero_ready() -> bool:
    return bool(settings.xero_client_id and settings.xero_client_secret and settings.xero_redirect_uri)


def xero_invoice_configuration_ready() -> bool:
    return bool(
        settings.xero_lesson_account_code
        and settings.xero_lesson_tax_type
        and settings.xero_line_amount_type in {"Exclusive", "Inclusive", "NoTax"}
    )


def xero_authorization_url(state: str) -> str:
    return f"{XERO_AUTHORIZE}?{urlencode({'response_type':'code','client_id':settings.xero_client_id,'redirect_uri':settings.xero_redirect_uri,'scope':XERO_SCOPES,'state':state})}"


async def xero_exchange_code(code: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            XERO_TOKEN,
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": settings.xero_redirect_uri},
            auth=(settings.xero_client_id, settings.xero_client_secret),
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        token = response.json()
        token["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=int(token.get("expires_in", 1800)))).isoformat()
        connection_response = await client.get(XERO_CONNECTIONS, headers={"Authorization": f"Bearer {token['access_token']}", "Accept": "application/json"})
        connection_response.raise_for_status()
        token["connections"] = connection_response.json()
        if token["connections"]:
            token["tenant_id"] = token["connections"][0].get("tenantId")
            token["tenant_name"] = token["connections"][0].get("tenantName")
        return token


async def xero_refresh(token: dict[str, Any]) -> dict[str, Any]:
    if not token.get("refresh_token"):
        raise RuntimeError("Xero refresh token is unavailable; reconnect the organisation.")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            XERO_TOKEN,
            data={"grant_type": "refresh_token", "refresh_token": token["refresh_token"]},
            auth=(settings.xero_client_id, settings.xero_client_secret),
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        refreshed = response.json()
        refreshed["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=int(refreshed.get("expires_in", 1800)))).isoformat()
        refreshed["tenant_id"] = token.get("tenant_id")
        refreshed["tenant_name"] = token.get("tenant_name")
        refreshed["connections"] = token.get("connections", [])
        return refreshed


async def xero_token_valid(token: dict[str, Any]) -> dict[str, Any]:
    expires = token.get("expires_at")
    if not expires or datetime.fromisoformat(expires) <= datetime.now(timezone.utc) + timedelta(minutes=2):
        return await xero_refresh(token)
    return token


def _xero_headers(token: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, str]:
    if not token.get("access_token") or not token.get("tenant_id"):
        raise RuntimeError("The Xero connection is missing its access token or organisation tenant.")
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "Xero-tenant-id": str(token["tenant_id"]),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _xero_invoice_result(payload: dict[str, Any]) -> dict[str, Any]:
    invoices = payload.get("Invoices") or []
    if not invoices:
        raise RuntimeError("Xero returned no invoice record.")
    invoice = invoices[0]
    errors = invoice.get("ValidationErrors") or []
    if errors:
        message = "; ".join(str(item.get("Message") or "Invoice validation failed") for item in errors[:5])
        raise RuntimeError(message[:500])
    if not invoice.get("InvoiceID"):
        raise RuntimeError("Xero did not return an invoice identifier.")
    return invoice


async def xero_create_draft_invoice(
    token: dict[str, Any],
    *,
    invoice: dict[str, Any],
    lines: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create one reviewed DRAFT sales invoice in the connected Xero organisation."""
    if not xero_invoice_configuration_ready():
        raise RuntimeError("Confirm the Xero lesson account code, tax type and line-amount setting first.")
    current_token = await xero_token_valid(token)
    line_items = [
        {
            "Description": line["description"],
            "Quantity": line["quantity"],
            "UnitAmount": round(int(line["unit_amount_cents"]) / 100, 2),
            "AccountCode": settings.xero_lesson_account_code,
            "TaxType": settings.xero_lesson_tax_type,
        }
        for line in lines
    ]
    xero_invoice = {
        "Type": "ACCREC",
        "Contact": {"ContactID": invoice["xero_contact_id"]},
        "Date": invoice["issue_date"],
        "DueDate": invoice["due_date"],
        "LineAmountTypes": settings.xero_line_amount_type,
        "InvoiceNumber": invoice["invoice_number"],
        "Reference": invoice["customer_number"],
        "LineItems": line_items,
        "Status": "DRAFT",
    }
    if settings.public_url.startswith("https://"):
        xero_invoice["Url"] = f"{settings.public_url}/platform.html#billing"
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.post(
            XERO_INVOICES,
            json={"Invoices": [xero_invoice]},
            headers=_xero_headers(current_token, idempotency_key=invoice["idempotency_key"]),
        )
        response.raise_for_status()
        result = _xero_invoice_result(response.json())
    return current_token, result


async def xero_get_invoice(
    token: dict[str, Any], invoice_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_token = await xero_token_valid(token)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{XERO_INVOICES}/{invoice_id}",
            headers=_xero_headers(current_token),
        )
        response.raise_for_status()
        result = _xero_invoice_result(response.json())
        if result.get("Status") in {"AUTHORISED", "PAID"}:
            online = await client.get(
                f"{XERO_INVOICES}/{invoice_id}/OnlineInvoice",
                headers=_xero_headers(current_token),
            )
            if online.is_success:
                links = online.json().get("OnlineInvoices") or []
                if links:
                    result["OnlineInvoiceUrl"] = links[0].get("OnlineInvoiceUrl")
    return current_token, result


def shopify_ready() -> bool:
    return bool(settings.shopify_store_domain and settings.shopify_storefront_token)


def weather_ready() -> bool:
    return bool(settings.weather_api_key) if settings.production else True


def printify_ready() -> bool:
    return bool(settings.printify_api_token and settings.printify_shop_id)


async def printify_products() -> list[dict[str, Any]]:
    if not printify_ready():
        return []
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{PRINTIFY_API}/shops/{settings.printify_shop_id}/products.json",
            headers={
                "Authorization": f"Bearer {settings.printify_api_token}",
                "Accept": "application/json",
                "User-Agent": "HV-Swim-Bendigo/5.5",
            },
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", []) if isinstance(payload, dict) else []


async def shopify_products() -> list[dict[str, Any]]:
    global _shopify_cache, _shopify_cache_expires
    if not shopify_ready():
        return []
    now = monotonic()
    if _shopify_cache is not None and now < _shopify_cache_expires:
        return _shopify_cache
    query = """
      query HVSwimProducts {
        products(first: 40) {
          edges { node { id title handle description productType tags featuredImage { url altText } variants(first: 30) { edges { node { id title availableForSale selectedOptions { name value } price { amount currencyCode } } } } } }
        }
      }
    """
    headers = {"Content-Type": "application/json"}
    if settings.shopify_storefront_token:
        headers["X-Shopify-Storefront-Access-Token"] = settings.shopify_storefront_token
    endpoint = f"https://{settings.shopify_store_domain}/api/{settings.shopify_api_version}/graphql.json"
    async with _shopify_lock:
        now = monotonic()
        if _shopify_cache is not None and now < _shopify_cache_expires:
            return _shopify_cache
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(endpoint, json={"query": query}, headers=headers)
            response.raise_for_status()
            payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(payload["errors"][0].get("message", "Shopify query failed"))
        _shopify_cache = [edge["node"] for edge in payload.get("data", {}).get("products", {}).get("edges", [])]
        _shopify_cache_expires = now + settings.shopify_cache_seconds
        return _shopify_cache


async def shopify_create_cart(variant_id: str, quantity: int = 1) -> dict[str, Any]:
    if not shopify_ready():
        raise RuntimeError("Shopify store domain is not configured.")
    mutation = """
      mutation CreateCart($input: CartInput!) {
        cartCreate(input: $input) { cart { id checkoutUrl totalQuantity } userErrors { field message } }
      }
    """
    headers = {"Content-Type": "application/json"}
    if settings.shopify_storefront_token:
        headers["X-Shopify-Storefront-Access-Token"] = settings.shopify_storefront_token
    endpoint = f"https://{settings.shopify_store_domain}/api/{settings.shopify_api_version}/graphql.json"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(endpoint, json={"query": mutation, "variables": {"input": {"lines": [{"merchandiseId": variant_id, "quantity": max(1, quantity)}]}}}, headers=headers)
        response.raise_for_status()
        payload = response.json()
        result = payload.get("data", {}).get("cartCreate", {})
        if result.get("userErrors"):
            raise RuntimeError(result["userErrors"][0]["message"])
        return result.get("cart", {})


async def current_bendigo_weather() -> dict[str, Any]:
    global _weather_cache, _weather_cache_expires, _weather_cache_stored
    now = monotonic()
    if _weather_cache and now < _weather_cache_expires:
        return {**_weather_cache, "cached": True, "stale": False}

    if settings.production and not settings.weather_api_key:
        raise RuntimeError("OPEN_METEO_API_KEY is required for commercial production weather")

    params = {
        "latitude": -36.757,
        "longitude": 144.279,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,precipitation",
        "timezone": "Australia/Melbourne",
    }
    endpoint = OPEN_METEO_CUSTOMER if settings.weather_api_key else OPEN_METEO
    if settings.weather_api_key:
        params["apikey"] = settings.weather_api_key

    async with _weather_lock:
        now = monotonic()
        if _weather_cache and now < _weather_cache_expires:
            return {**_weather_cache, "cached": True, "stale": False}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(endpoint, params=params)
                response.raise_for_status()
                current = response.json().get("current", {})
            if not current:
                raise RuntimeError("Weather provider returned no current conditions")
            _weather_cache = {
                "source": "Open-Meteo",
                "location": "Bendigo",
                "current": current,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "attribution_url": "https://open-meteo.com/",
                "commercial_endpoint": bool(settings.weather_api_key),
            }
            _weather_cache_stored = now
            _weather_cache_expires = now + max(60, min(settings.weather_cache_seconds, 3600))
            return {**_weather_cache, "cached": False, "stale": False}
        except Exception:
            # A short stale-on-error window keeps the public page useful during a provider
            # blip while labelling the observation honestly.
            if _weather_cache and now - _weather_cache_stored <= 3600:
                return {**_weather_cache, "cached": True, "stale": True}
            raise


async def pool_sensor_reading() -> dict[str, Any] | None:
    if not settings.pool_sensor_url:
        return None
    headers = {"Accept": "application/json"}
    if settings.pool_sensor_token:
        headers["Authorization"] = f"Bearer {settings.pool_sensor_token}"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(settings.pool_sensor_url, headers=headers)
        response.raise_for_status()
        return response.json()
