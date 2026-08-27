from __future__ import annotations

import base64
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

PBKDF2_ITERATIONS = 210_000
SESSION_DAYS = 14


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def expires_iso(days: int = SESSION_DAYS) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITERATIONS).derive(password.encode("utf-8"))
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
        actual = PBKDF2HMAC(algorithm=hashes.SHA256(), length=len(expected), salt=salt, iterations=int(iterations)).derive(password.encode("utf-8"))
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
    }
