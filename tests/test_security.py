"""Tests for the password and token layer.

These use only Python's standard library. They can be driven by pytest, or straight from
the command line if pytest is not installed:

    pytest tests/test_security.py -q
    python3 tests/test_security.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.security import (  # noqa: E402
    PBKDF2_ITERATIONS,
    SENSITIVE_VALUE_PREFIX,
    business_date_from_timestamp,
    business_today,
    decrypt_sensitive,
    encrypt_sensitive,
    new_token,
    password_hash,
    password_needs_rehash,
    password_verify,
    token_digest,
)

PASSWORD = "FamilyDemo!26"


def test_hashes_are_salted():
    """Two users with the same password must not share a hash."""
    assert password_hash(PASSWORD) != password_hash(PASSWORD)


def test_correct_password_verifies():
    assert password_verify(PASSWORD, password_hash(PASSWORD))


def test_wrong_password_is_rejected():
    assert not password_verify("FamilyDemo!27", password_hash(PASSWORD))


def test_empty_password_is_rejected():
    assert not password_verify("", password_hash(PASSWORD))


def test_iterations_meet_current_guidance():
    """OWASP's current floor for PBKDF2-HMAC-SHA256 is 600,000. Raise, never lower."""
    assert PBKDF2_ITERATIONS >= 600_000
    assert password_hash(PASSWORD).startswith(f"pbkdf2_sha256${PBKDF2_ITERATIONS}$")


def test_malformed_stored_hash_returns_false_rather_than_raising():
    """A corrupt row must fail the sign-in, not crash the endpoint."""
    for broken in ("", "not-a-hash", "pbkdf2_sha256$abc$x$y", "$$$"):
        assert password_verify(PASSWORD, broken) is False


def test_outdated_hashes_are_flagged_for_rehash():
    assert password_needs_rehash("md5$1$x$y")
    assert password_needs_rehash("pbkdf2_sha256$1000$x$y")
    assert password_needs_rehash("")


def test_current_hashes_are_not_flagged_for_rehash():
    assert not password_needs_rehash(password_hash(PASSWORD))


def test_unusual_passwords_round_trip():
    for password in ("pässwörd–ok✓", "a" * 200, "   spaces   ", "🏊‍♀️swim"):
        assert password_verify(password, password_hash(password))


def test_session_tokens_are_unique_and_long_enough():
    tokens = {new_token() for _ in range(500)}
    assert len(tokens) == 500
    assert min(len(token) for token in tokens) >= 32


def test_session_tokens_are_one_way_digested_for_database_storage():
    token = new_token(32)
    digest = token_digest(token)
    assert token not in digest
    assert len(digest) == 64
    assert token_digest(token) == digest


def test_sensitive_customer_text_is_authenticated_encrypted_and_round_trips():
    value = "Severe allergy · private lesson safety note"
    encrypted = encrypt_sensitive(value)
    assert encrypted.startswith(SENSITIVE_VALUE_PREFIX)
    assert value not in encrypted
    assert decrypt_sensitive(encrypted) == value
    assert decrypt_sensitive("legacy preview text") == "legacy preview text"


def test_business_date_uses_melbourne_not_the_server_timezone():
    utc_late = datetime(2026, 8, 28, 15, 30, tzinfo=timezone.utc)
    assert business_today(utc_late).isoformat() == "2026-08-29"
    assert business_date_from_timestamp("2026-08-28T15:30:00+00:00").isoformat() == "2026-08-29"


if __name__ == "__main__":
    failures = 0
    for name, function in sorted(globals().items()):
        if not name.startswith("test_") or not callable(function):
            continue
        try:
            function()
            print(f"PASS  {name}")
        except AssertionError as problem:
            failures += 1
            print(f"FAIL  {name}  {problem}")
    print(f"\n{'all checks passed' if not failures else f'{failures} failing'}")
    sys.exit(1 if failures else 0)
