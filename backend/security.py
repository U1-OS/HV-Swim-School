from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from nacl.exceptions import CryptoError
from nacl.secret import SecretBox

from .config import settings

# OWASP's current PBKDF2-HMAC-SHA256 work factor. Existing lower-cost hashes are upgraded
# transparently after the next successful sign-in by password_needs_rehash().
PBKDF2_ITERATIONS = 600_000
SESSION_DAYS = 14
MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
SENSITIVE_VALUE_PREFIX = "enc:v1:"


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


def token_digest(token: str) -> str:
    """Store bearer-style session identifiers as one-way digests, never reusable tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _data_secret_box() -> SecretBox:
    # Development uses the stable preview secret so the demo remains self-contained.
    # Production validation requires a separate, deployment-only encryption key.
    material = settings.data_encryption_key or settings.session_secret
    key = hashlib.sha256(f"hv-swim-sensitive-data-v1:{material}".encode("utf-8")).digest()
    return SecretBox(key)


def encrypt_sensitive(value: str | None) -> str | None:
    """Authenticated field encryption for medical, allergy and emergency-contact text."""
    if value is None or value == "":
        return value
    encrypted = bytes(_data_secret_box().encrypt(value.encode("utf-8")))
    return SENSITIVE_VALUE_PREFIX + base64.urlsafe_b64encode(encrypted).decode("ascii")


def decrypt_sensitive(value: str | None) -> str | None:
    """Read encrypted values while allowing a controlled migration from legacy plaintext."""
    if value is None or value == "" or not value.startswith(SENSITIVE_VALUE_PREFIX):
        return value
    try:
        raw = base64.urlsafe_b64decode(value[len(SENSITIVE_VALUE_PREFIX):].encode("ascii"))
        return _data_secret_box().decrypt(raw).decode("utf-8")
    except (ValueError, UnicodeDecodeError, CryptoError) as exc:
        raise RuntimeError("Sensitive customer data could not be decrypted") from exc



PRIVATE_FILE_PREFIX = b"HVFILE1"


def encrypt_private_file(value: bytes) -> bytes:
    """Authenticated private document encryption using the deployment data key."""
    return PRIVATE_FILE_PREFIX + bytes(_data_secret_box().encrypt(value))


def decrypt_private_file(value: bytes) -> bytes:
    if not value.startswith(PRIVATE_FILE_PREFIX):
        raise ValueError("Private document encryption format is invalid")
    try:
        return _data_secret_box().decrypt(value[len(PRIVATE_FILE_PREFIX):])
    except CryptoError as exc:
        raise ValueError("Private document could not be decrypted") from exc


def public_user(row: Any) -> dict[str, Any]:
    payload = {
        "id": row["id"],
        "email": row["email"],
        "role": row["role"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "display_name": f"{row['first_name']} {row['last_name']}".strip(),
        "must_change_password": bool(row["must_change_password"]),
    }
    if "customer_number" in row.keys() and row["role"] == "customer":
        payload["customer_number"] = row["customer_number"]
    if "staff_number" in row.keys() and row["role"] in ("staff", "admin"):
        payload["staff_number"] = row["staff_number"]
    for field in ("management_scope", "mfa_enabled", "created_at", "last_login_at", "email_verified_at"):
        if field in row.keys():
            payload[field] = bool(row[field]) if field == "mfa_enabled" else row[field]
    return payload
