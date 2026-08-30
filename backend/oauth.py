from __future__ import annotations

import base64
import binascii
import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import rsa

from .config import settings


class OAuthProviderError(RuntimeError):
    """A safe, provider-neutral authentication failure."""


@dataclass(frozen=True)
class ProviderDefinition:
    provider: str
    label: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    issuer: tuple[str, ...]


PROVIDERS = {
    "google": ProviderDefinition(
        provider="google",
        label="Google",
        authorization_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token",
        jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
        issuer=("https://accounts.google.com", "accounts.google.com"),
    ),
    "apple": ProviderDefinition(
        provider="apple",
        label="Apple",
        authorization_endpoint="https://appleid.apple.com/auth/authorize",
        token_endpoint="https://appleid.apple.com/auth/token",
        jwks_uri="https://appleid.apple.com/auth/keys",
        issuer=("https://appleid.apple.com",),
    ),
}

_JWKS_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_JWKS_LOCK = threading.Lock()


def provider_definition(provider: str) -> ProviderDefinition:
    definition = PROVIDERS.get(provider)
    if not definition:
        raise OAuthProviderError("Unsupported account provider")
    return definition


def redirect_uri(provider: str) -> str:
    if provider == "google":
        return settings.google_redirect_uri or f"{settings.public_url}/api/auth/oauth/google/callback"
    if provider == "apple":
        return settings.apple_redirect_uri or f"{settings.public_url}/api/auth/oauth/apple/callback"
    raise OAuthProviderError("Unsupported account provider")


def provider_ready(provider: str) -> bool:
    if provider == "google":
        return bool(settings.google_client_id and settings.google_client_secret)
    if provider == "apple":
        return bool(settings.apple_client_id and settings.apple_client_secret)
    return False


def provider_public_status() -> list[dict[str, Any]]:
    return [
        {
            "id": provider,
            "label": definition.label,
            "configured": provider_ready(provider),
            "account_role": "customer",
        }
        for provider, definition in PROVIDERS.items()
    ]


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def authorization_url(provider: str, *, state: str, nonce: str, code_verifier: str) -> str:
    definition = provider_definition(provider)
    if not provider_ready(provider):
        raise OAuthProviderError(f"{definition.label} account access is not configured")
    if provider == "google":
        parameters = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri(provider),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": pkce_challenge(code_verifier),
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
    else:
        parameters = {
            "client_id": settings.apple_client_id,
            "redirect_uri": redirect_uri(provider),
            "response_type": "code",
            "response_mode": "form_post",
            "scope": "name email",
            "state": state,
            "nonce": nonce,
        }
    return f"{definition.authorization_endpoint}?{urlencode(parameters)}"


async def exchange_code(provider: str, *, code: str, code_verifier: str) -> dict[str, Any]:
    definition = provider_definition(provider)
    if provider == "google":
        form = {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri(provider),
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        }
    else:
        form = {
            "code": code,
            "client_id": settings.apple_client_id,
            "client_secret": settings.apple_client_secret,
            "redirect_uri": redirect_uri(provider),
            "grant_type": "authorization_code",
        }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(definition.token_endpoint, data=form)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OAuthProviderError("The account provider could not complete sign-in") from exc
    if not isinstance(payload, dict) or not payload.get("id_token"):
        raise OAuthProviderError("The account provider returned an incomplete identity")
    return payload


def base64url_decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError, TypeError) as exc:
        raise OAuthProviderError("The account provider identity is malformed") from exc


def provider_jwks(definition: ProviderDefinition, *, force_refresh: bool = False) -> list[dict[str, Any]]:
    with _JWKS_LOCK:
        cached = _JWKS_CACHE.get(definition.provider)
        if not force_refresh and cached and cached[0] > time.monotonic():
            return cached[1]
    try:
        response = httpx.get(definition.jwks_uri, timeout=10.0)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OAuthProviderError("The account provider verification keys are unavailable") from exc
    keys = payload.get("keys") if isinstance(payload, dict) else None
    if not isinstance(keys, list) or not keys:
        raise OAuthProviderError("The account provider returned no verification keys")
    safe_keys = [key for key in keys if isinstance(key, dict)]
    with _JWKS_LOCK:
        _JWKS_CACHE[definition.provider] = (time.monotonic() + 600, safe_keys)
    return safe_keys


def verify_identity_token(provider: str, token: str, *, nonce: str) -> dict[str, Any]:
    definition = provider_definition(provider)
    client_id = settings.google_client_id if provider == "google" else settings.apple_client_id
    try:
        encoded_header, encoded_claims, encoded_signature = token.split(".")
        header = json.loads(base64url_decode(encoded_header))
        claims = json.loads(base64url_decode(encoded_claims))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OAuthProviderError("The account provider identity is malformed") from exc
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise OAuthProviderError("The account provider identity is malformed")
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise OAuthProviderError("The account provider identity uses an unsupported signature")
    def matching_key(keys: list[dict[str, Any]]) -> dict[str, Any] | None:
        return next(
            (
                item
                for item in keys
                if item.get("kid") == header["kid"]
                and item.get("kty") == "RSA"
                and item.get("use", "sig") == "sig"
                and item.get("alg", "RS256") == "RS256"
            ),
            None,
        )

    key_data = matching_key(provider_jwks(definition))
    if not key_data:
        # Providers rotate keys. Refresh once when a signed token names a new key.
        key_data = matching_key(provider_jwks(definition, force_refresh=True))
    if not key_data or not key_data.get("n") or not key_data.get("e"):
        raise OAuthProviderError("The account provider verification key was not found")
    try:
        public_key = rsa.PublicKey(
            int.from_bytes(base64url_decode(key_data["n"]), "big"),
            int.from_bytes(base64url_decode(key_data["e"]), "big"),
        )
        algorithm = rsa.verify(
            f"{encoded_header}.{encoded_claims}".encode("ascii"),
            base64url_decode(encoded_signature),
            public_key,
        )
    except (UnicodeEncodeError, ValueError, TypeError, rsa.VerificationError) as exc:
        raise OAuthProviderError("The account provider identity could not be verified") from exc
    if algorithm != "SHA-256":
        raise OAuthProviderError("The account provider identity uses an unsupported signature")
    current_time = int(time.time())
    try:
        expires_at = int(claims.get("exp", 0))
        not_before = int(claims.get("nbf", 0)) if claims.get("nbf") is not None else 0
        issued_at = int(claims.get("iat", 0)) if claims.get("iat") is not None else 0
    except (TypeError, ValueError) as exc:
        raise OAuthProviderError("The account provider identity has invalid timing claims") from exc
    if expires_at <= current_time - 60 or not_before > current_time + 60 or issued_at > current_time + 300:
        raise OAuthProviderError("The account provider identity has expired or is not yet valid")
    if claims.get("iss") not in definition.issuer:
        raise OAuthProviderError("The account provider identity has an invalid issuer")
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if not client_id or client_id not in audiences:
        raise OAuthProviderError("The account provider identity has an invalid audience")
    if len(audiences) > 1 and claims.get("azp") != client_id:
        raise OAuthProviderError("The account provider identity has an invalid authorised party")
    if not nonce or claims.get("nonce") != nonce:
        raise OAuthProviderError("The account provider identity failed replay protection")
    if not claims.get("sub"):
        raise OAuthProviderError("The account provider identity is missing its subject")
    email_verified = claims.get("email_verified")
    if isinstance(email_verified, str):
        email_verified = email_verified.lower() == "true"
    if not claims.get("email") or email_verified is not True:
        raise OAuthProviderError("A verified email address is required")
    return dict(claims)
