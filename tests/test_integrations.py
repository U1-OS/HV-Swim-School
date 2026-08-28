"""Small integration-boundary tests that never make external network calls."""

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
