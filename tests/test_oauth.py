"""Cryptographic and claim checks for family provider identity tokens."""

from __future__ import annotations

import base64
from dataclasses import replace
import json
import time

import pytest
import rsa

from backend import config, oauth


def encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def signed_token(private_key: rsa.PrivateKey, claims: dict, *, key_id: str = "test-key") -> str:
    header = encoded(json.dumps({"alg": "RS256", "kid": key_id, "typ": "JWT"}, separators=(",", ":")).encode())
    payload = encoded(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    return f"{header}.{payload}.{encoded(rsa.sign(signing_input, private_key, 'SHA-256'))}"


@pytest.fixture
def google_identity(monkeypatch):
    public_key, private_key = rsa.newkeys(1024)
    key = {
        "kid": "test-key",
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "n": encoded(public_key.n.to_bytes((public_key.n.bit_length() + 7) // 8, "big")),
        "e": encoded(public_key.e.to_bytes((public_key.e.bit_length() + 7) // 8, "big")),
    }
    monkeypatch.setattr(oauth, "settings", replace(config.settings, google_client_id="google-client-test"))
    monkeypatch.setattr(oauth, "provider_jwks", lambda _definition, force_refresh=False: [key])
    return private_key


def test_verified_google_identity_accepts_valid_rs256_token(google_identity):
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "google-client-test",
        "sub": "subject-1",
        "email": "family@example.test",
        "email_verified": True,
        "nonce": "expected-nonce",
        "iat": now,
        "exp": now + 300,
    }
    verified = oauth.verify_identity_token(
        "google", signed_token(google_identity, claims), nonce="expected-nonce"
    )
    assert verified["sub"] == "subject-1"
    assert verified["email"] == "family@example.test"


@pytest.mark.parametrize("claim,value", (("nonce", "wrong"), ("aud", "another-client"), ("email_verified", False)))
def test_verified_google_identity_rejects_invalid_security_claim(google_identity, claim, value):
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "google-client-test",
        "sub": "subject-1",
        "email": "family@example.test",
        "email_verified": True,
        "nonce": "expected-nonce",
        "iat": now,
        "exp": now + 300,
    }
    claims[claim] = value
    with pytest.raises(oauth.OAuthProviderError):
        oauth.verify_identity_token("google", signed_token(google_identity, claims), nonce="expected-nonce")


def test_verified_google_identity_rejects_tampering(google_identity):
    now = int(time.time())
    token = signed_token(
        google_identity,
        {
            "iss": "https://accounts.google.com",
            "aud": "google-client-test",
            "sub": "subject-1",
            "email": "family@example.test",
            "email_verified": True,
            "nonce": "expected-nonce",
            "iat": now,
            "exp": now + 300,
        },
    )
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload[:-1]}A.{signature}"
    with pytest.raises(oauth.OAuthProviderError):
        oauth.verify_identity_token("google", tampered, nonce="expected-nonce")
