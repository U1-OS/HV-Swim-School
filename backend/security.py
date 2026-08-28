from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

# OWASP's current PBKDF2-HMAC-SHA256 work factor. Existing lower-cost hashes are upgraded
# transparently after the next successful sign-in by password_needs_rehash().
PBKDF2_ITERATIONS = 600_000
SESSION_DAYS = 14
MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def expires_iso(days: int = SESSION_DAYS) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def business_today(at: datetime | None = None):
    """Return HV Swim's calendar date, independent of the server/container timezone."""
    instant = at or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(MELBOURNE_TZ).date()


def business_date_from_timestamp(value: str):
    """Convert an ISO timestamp to the Bendigo payroll/lesson calendar date."""
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(MELBOURNE_TZ).date()


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def password_verify(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations), dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def password_needs_rehash(encoded: str) -> bool:
    try:
        algorithm, iterations, *_ = encoded.split("$", 3)
        return algorithm != "pbkdf2_sha256" or int(iterations) != PBKDF2_ITERATIONS
    except (ValueError, TypeError):
        return True


def new_token(bytes_count: int = 32) -> str:
    return secrets.token_urlsafe(bytes_count)


def public_user(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "role": row["role"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "display_name": f"{row['first_name']} {row['last_name']}".strip(),
        "must_change_password": bool(row["must_change_password"]),
    }
