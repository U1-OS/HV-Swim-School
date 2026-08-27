from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet

from .config import settings

XERO_AUTHORIZE = "https://login.xero.com/identity/connect/authorize"
XERO_TOKEN = "https://identity.xero.com/connect/token"
XERO_CONNECTIONS = "https://api.xero.com/connections"
XERO_SCOPES = "openid profile email offline_access accounting.transactions payroll.employees payroll.timesheets"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
PRINTIFY_API = "https://api.printify.com/v1"


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.session_secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_json(value: dict[str, Any]) -> bytes:
    return _fernet().encrypt(json.dumps(value).encode("utf-8"))


def decrypt_json(value: bytes | None) -> dict[str, Any]:
    if not value:
        return {}
    return json.loads(_fernet().decrypt(value).decode("utf-8"))


def xero_ready() -> bool:
    return bool(settings.xero_client_id and settings.xero_client_secret and settings.xero_redirect_uri)


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


async def xero_post_timesheets(token: dict[str, Any], payload: list[dict[str, Any]]) -> dict[str, Any]:
    if not settings.xero_sync_enabled:
        return {"dry_run": True, "payload": payload, "message": "XERO_SYNC_ENABLED is false; no financial data was transmitted."}
    token = await xero_token_valid(token)
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.post(
            "https://api.xero.com/payroll.xro/1.0/timesheets",
            json=payload,
            headers={"Authorization": f"Bearer {token['access_token']}", "Xero-tenant-id": token["tenant_id"], "Accept": "application/json", "Content-Type": "application/json"},
        )
        response.raise_for_status()
        return {"dry_run": False, "response": response.json(), "token": token}


def shopify_ready() -> bool:
    return bool(settings.shopify_store_domain)


def printify_ready() -> bool:
    return bool(settings.printify_api_token and settings.printify_shop_id)


async def printify_products() -> list[dict[str, Any]]:
    if not printify_ready():
        return []
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{PRINTIFY_API}/shops/{settings.printify_shop_id}/products.json",
            headers={"Authorization": f"Bearer {settings.printify_api_token}", "Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", []) if isinstance(payload, dict) else []


async def shopify_products() -> list[dict[str, Any]]:
    if not shopify_ready():
        return []
    query = """
      query HVSwimProducts {
        products(first: 40) {
          edges { node { id title handle description featuredImage { url altText } variants(first: 30) { edges { node { id title availableForSale price { amount currencyCode } } } } } }
        }
      }
    """
    headers = {"Content-Type": "application/json"}
    if settings.shopify_storefront_token:
        headers["X-Shopify-Storefront-Access-Token"] = settings.shopify_storefront_token
    endpoint = f"https://{settings.shopify_store_domain}/api/{settings.shopify_api_version}/graphql.json"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(endpoint, json={"query": query}, headers=headers)
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(payload["errors"][0].get("message", "Shopify query failed"))
        return [edge["node"] for edge in payload.get("data", {}).get("products", {}).get("edges", [])]


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
    params = {
        "latitude": -36.757,
        "longitude": 144.279,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,precipitation",
        "timezone": "Australia/Melbourne",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(OPEN_METEO, params=params)
        response.raise_for_status()
        return response.json().get("current", {})


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
