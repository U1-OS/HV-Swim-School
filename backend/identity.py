"""Account lifecycle and optional authenticator MFA for the existing session model."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import smtplib
import ssl
import struct
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Literal
from urllib.parse import quote

from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .database import audit, db_session, rows
from .config import settings
from .security import (
    decrypt_sensitive,
    encrypt_sensitive,
    management_account_requires_mfa,
    new_token,
    now_iso,
    password_hash,
    password_verify,
    token_digest,
)


def migrate():
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        columns = {r[1] for r in db.execute("PRAGMA table_info(users)")}
        for key, definition in {
            "management_scope": "TEXT NOT NULL DEFAULT 'none'",
            "last_login_at": "TEXT",
            "email_verified_at": "TEXT",
            "invitation_pending": "INTEGER NOT NULL DEFAULT 0",
            "mfa_enabled": "INTEGER NOT NULL DEFAULT 0",
        }.items():
            if key not in columns:
                db.execute(f"ALTER TABLE users ADD COLUMN {key} {definition}")
        db.execute("UPDATE users SET management_scope='owner' WHERE role='admin'")
        for statement in [
            """CREATE TABLE IF NOT EXISTS manager_assignments(manager_id INTEGER NOT NULL REFERENCES users(id),staff_id INTEGER NOT NULL REFERENCES users(id),PRIMARY KEY(manager_id,staff_id),CHECK(manager_id<>staff_id))""",
            """CREATE TABLE IF NOT EXISTS account_tokens(digest TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),purpose TEXT NOT NULL CHECK(purpose IN ('invite','recovery')),created_at TEXT NOT NULL,expires_at TEXT NOT NULL,used_at TEXT,delivery TEXT NOT NULL DEFAULT 'manual')""",
            """CREATE TABLE IF NOT EXISTS account_requests(id INTEGER PRIMARY KEY,email TEXT NOT NULL,ip_address TEXT NOT NULL,created_at TEXT NOT NULL,resolved INTEGER NOT NULL DEFAULT 0)""",
            "CREATE INDEX IF NOT EXISTS idx_account_requests_limit ON account_requests(ip_address,created_at)",
            "CREATE TABLE IF NOT EXISTS account_proof_attempts(user_id INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)",
            "CREATE INDEX IF NOT EXISTS idx_account_proof_limit ON account_proof_attempts(user_id,created_at)",
            """CREATE TABLE IF NOT EXISTS account_mfa(user_id INTEGER PRIMARY KEY REFERENCES users(id),secret TEXT NOT NULL,pending_secret TEXT,last_counter INTEGER NOT NULL DEFAULT -1)""",
        ]:
            db.execute(statement)


def totp(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8))
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    return str(
        (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    ).zfill(6)


def current_counter():
    return int(time.time()) // 30


def proof_attempt(user_id):
    """Persist a rate-limit debit before checking a sensitive-action proof.

    This separate committed transaction also counts failed proofs, whose handler
    transactions roll back. Never record passwords, tokens or authenticator codes.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        if (
            db.execute(
                "SELECT COUNT(*) FROM account_proof_attempts WHERE user_id=? AND created_at>?",
                (user_id, cutoff),
            ).fetchone()[0]
            >= 10
        ):
            raise HTTPException(
                429,
                "Too many security attempts. Try again in 15 minutes.",
                headers={"Retry-After": "900"},
            )
        db.execute("DELETE FROM account_proof_attempts WHERE created_at<?", (cutoff,))
        db.execute(
            "INSERT INTO account_proof_attempts VALUES(?,?)", (user_id, now_iso())
        )


def matching_counter(secret, code, last=-1):
    counter = current_counter()
    if not code or len(code) != 6 or not code.isdigit():
        return None
    for candidate in (counter, counter - 1, counter + 1):
        if candidate > last and hmac.compare_digest(totp(secret, candidate), code):
            return candidate
    return None


def verify_mfa(db, user, code) -> bool:
    if not user["mfa_enabled"]:
        return True
    record = db.execute(
        "SELECT * FROM account_mfa WHERE user_id=?", (user["id"],)
    ).fetchone()
    if not record:
        return False
    counter = matching_counter(
        decrypt_sensitive(record["secret"]), code, record["last_counter"]
    )
    if counter is None:
        return False
    changed = db.execute(
        "UPDATE account_mfa SET last_counter=? WHERE user_id=? AND last_counter<?",
        (counter, user["id"], counter),
    ).rowcount
    return changed == 1


def email_configured():
    return settings.production and os.getenv("HV_EMAIL_LIVE_APPROVED")=="true" and all(
        os.getenv(key)
        for key in ("HV_SMTP_HOST", "HV_SMTP_USER", "HV_SMTP_PASSWORD", "HV_SMTP_FROM")
    )


def deliver_link(recipient, link, purpose):
    """SMTP TLS submission only. Acceptance is not a promise of inbox delivery."""
    if not email_configured():
        return False
    msg = EmailMessage()
    msg["From"] = os.environ["HV_SMTP_FROM"]
    msg["To"] = recipient
    msg["Subject"] = (
        "HV Swim secure account invitation"
        if purpose == "invite"
        else "HV Swim password recovery"
    )
    msg.set_content(
        f"Use this one-time HV Swim link to {'activate your account' if purpose=='invite' else 'reset your password'}:\n\n{link}\n\nIt expires in 24 hours. If you did not request this, contact bendigo@hvswimschool.com. Never share your password or authenticator code."
    )
    try:
        with smtplib.SMTP_SSL(
            os.environ["HV_SMTP_HOST"],
            int(os.getenv("HV_SMTP_PORT", "465")),
            timeout=15,
            context=ssl.create_default_context(),
        ) as smtp:
            smtp.login(os.environ["HV_SMTP_USER"], os.environ["HV_SMTP_PASSWORD"])
            refused = smtp.send_message(msg)
            return not refused
    except (OSError, smtplib.SMTPException, ValueError):
        return False


def issue_token(db, account_id, purpose, *, origin):
    token = new_token(32)
    db.execute(
        "UPDATE account_tokens SET used_at=? WHERE user_id=? AND purpose=? AND used_at IS NULL",
        (now_iso(), account_id, purpose),
    )
    db.execute(
        "INSERT INTO account_tokens(digest,user_id,purpose,created_at,expires_at) VALUES(?,?,?,?,?)",
        (
            token_digest(token),
            account_id,
            purpose,
            now_iso(),
            (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        ),
    )
    # Fragment is not sent in HTTP requests or Referer headers.
    return token, f"{origin}/login.html#{purpose}={token}"


class InviteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    role: Literal["customer", "staff", "admin"] = "staff"
    delivery: Literal["manual", "email"] = "manual"


class RecoveryRequest(BaseModel):
    email: EmailStr


class RedeemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=100)
    password: str = Field(min_length=12, max_length=200)


class AccessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    management_scope: Literal["none", "manager", "owner"]
    staff_ids: list[int] = Field(default_factory=list, max_length=200)
    reason: str = Field(min_length=8, max_length=500)


class PasswordProof(BaseModel):
    password: str = Field(min_length=8, max_length=200)
    code: str = Field(default="", max_length=6)


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=30)


def register(app, session_user, csrf_guard):
    def owner(user):
        if user["role"] != "admin":
            raise HTTPException(403, "Owner access required")

    @app.get("/api/account/profile")
    def profile(user=Depends(session_user)):
        return {
            k: user.get(k)
            for k in (
                "id",
                "email",
                "first_name",
                "last_name",
                "phone",
                "role",
                "management_scope",
                "created_at",
                "last_login_at",
                "email_verified_at",
                "mfa_enabled",
                "staff_number",
                "customer_number",
            )
        }

    @app.patch("/api/account/profile")
    def update_profile(
        payload: ProfileInput,
        request: Request,
        user=Depends(session_user),
        x_csrf_token: str | None = Header(default=None),
    ):
        csrf_guard(request, user, x_csrf_token)
        if not payload.first_name.strip():
            raise HTTPException(422, "Enter your first name")
        with db_session() as db:
            db.execute(
                "UPDATE users SET first_name=?,last_name=?,phone=? WHERE id=?",
                (
                    payload.first_name.strip(),
                    payload.last_name.strip(),
                    payload.phone.strip(),
                    user["id"],
                ),
            )
            audit(db, user["id"], "update_profile", "user", user["id"])
        return {"saved": True}

    @app.get("/api/account/sessions")
    def sessions(user=Depends(session_user)):
        with db_session() as db:
            return {
                "sessions": [
                    {
                        "current": r["id"] == user["session_id"],
                        "created_at": r["created_at"],
                        "expires_at": r["expires_at"],
                    }
                    for r in db.execute(
                        "SELECT * FROM sessions WHERE user_id=? AND expires_at>?",
                        (user["id"], now_iso()),
                    )
                ]
            }

    @app.post("/api/account/revoke-other-sessions")
    def revoke(
        request: Request,
        user=Depends(session_user),
        x_csrf_token: str | None = Header(default=None),
    ):
        csrf_guard(request, user, x_csrf_token)
        with db_session() as db:
            count = db.execute(
                "DELETE FROM sessions WHERE user_id=? AND id<>?",
                (user["id"], user["session_id"]),
            ).rowcount
            audit(db, user["id"], "revoke_other_sessions", "user", user["id"])
        return {"revoked": count}

    @app.get("/api/account/team")
    def team(user=Depends(session_user)):
        owner(user)
        with db_session() as db:
            return {
                "accounts": rows(
                    db.execute(
                        "SELECT id,email,first_name,last_name,role,management_scope,active,invitation_pending,created_at,last_login_at,email_verified_at,mfa_enabled,staff_number,customer_number FROM users ORDER BY first_name"
                    )
                ),
                "assignments": rows(db.execute("SELECT * FROM manager_assignments")),
                "recovery_requests": rows(
                    db.execute(
                        "SELECT id,email,created_at FROM account_requests WHERE resolved=0 ORDER BY id DESC LIMIT 100"
                    )
                ),
                "email_configured": email_configured(),
            }

    @app.post("/api/account/invitations")
    def invite(
        payload: InviteInput,
        request: Request,
        user=Depends(session_user),
        x_csrf_token: str | None = Header(default=None),
    ):
        from .config import settings

        csrf_guard(request, user, x_csrf_token)
        owner(user)
        email = str(payload.email).lower().strip()
        if settings.production and email.endswith("@hvswim.demo"):
            raise HTTPException(422, "Sample identities are disabled in production")
        if payload.delivery == "email" and not email_configured():
            raise HTTPException(
                409, "Email delivery is not configured. Use reviewed manual handover."
            )
        with db_session() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM users WHERE email=?", (email,)
            ).fetchone()
            if existing and not existing["invitation_pending"]:
                raise HTTPException(
                    409,
                    "An account already exists. Use recovery or account management.",
                )
            if existing:
                account_id = existing["id"]
                if existing["role"] != payload.role:
                    raise HTTPException(
                        409, "Reissuing an invitation cannot change its role"
                    )
            else:
                account_id = db.execute(
                    "INSERT INTO users(email,password_hash,role,first_name,last_name,active,invitation_pending,created_at,management_scope) VALUES(?,?,?,?,?,0,1,?,?)",
                    (
                        email,
                        password_hash(new_token(40)),
                        payload.role,
                        payload.first_name.strip(),
                        payload.last_name.strip(),
                        now_iso(),
                        "owner" if payload.role == "admin" else "none",
                    ),
                ).lastrowid
                column, prefix = (
                    ("customer_number", "HVS-")
                    if payload.role == "customer"
                    else ("staff_number", "HVS-W-")
                )
                db.execute(
                    f"UPDATE users SET {column}=? WHERE id=?",
                    (f"{prefix}{account_id:06d}", account_id),
                )
            token, link = issue_token(
                db, account_id, "invite", origin=settings.public_url
            )
            audit(
                db,
                user["id"],
                "invite_account",
                "user",
                account_id,
                {"role": payload.role, "delivery": payload.delivery},
            )
        accepted = (
            deliver_link(email, link, "invite")
            if payload.delivery == "email"
            else False
        )
        if accepted:
            with db_session() as db:
                db.execute(
                    "UPDATE account_tokens SET delivery='email_accepted' WHERE digest=?",
                    (token_digest(token),),
                )
        return {
            "account_id": account_id,
            "email_accepted": accepted,
            "link": link if not accepted else None,
            "message": (
                "Email server accepted the invitation"
                if accepted
                else "Invitation created. Deliver this private one-time link only to the verified recipient; no email was sent."
            ),
        }

    @app.post("/api/account/{account_id}/access")
    def access(
        account_id: int,
        payload: AccessInput,
        request: Request,
        user=Depends(session_user),
        x_csrf_token: str | None = Header(default=None),
    ):
        csrf_guard(request, user, x_csrf_token)
        owner(user)
        if account_id == user["id"]:
            raise HTTPException(
                409, "Another owner must review changes to your own access"
            )
        with db_session() as db:
            db.execute("BEGIN IMMEDIATE")
            account = db.execute(
                "SELECT * FROM users WHERE id=?", (account_id,)
            ).fetchone()
            if not account or account["role"] == "customer":
                raise HTTPException(404, "Team account not found")
            if (
                account["role"] == "admin"
                and payload.management_scope != "owner"
                and db.execute(
                    "SELECT COUNT(*) FROM users WHERE role='admin' AND active=1", ()
                ).fetchone()[0]
                <= 1
            ):
                raise HTTPException(409, "The final active owner cannot be demoted")
            ids = set(payload.staff_ids)
            if payload.management_scope != "manager" and ids:
                raise HTTPException(422, "Only managers have assigned staff")
            for staff_id in ids:
                member = db.execute(
                    "SELECT role FROM users WHERE id=? AND active=1", (staff_id,)
                ).fetchone()
                if not member or member[0] != "staff" or staff_id == account_id:
                    raise HTTPException(422, "Assign other active staff accounts only")
            db.execute(
                "UPDATE users SET role=?,management_scope=? WHERE id=?",
                (
                    "admin" if payload.management_scope == "owner" else "staff",
                    payload.management_scope,
                    account_id,
                ),
            )
            db.execute(
                "DELETE FROM manager_assignments WHERE manager_id=?", (account_id,)
            )
            for staff_id in ids:
                db.execute(
                    "INSERT INTO manager_assignments VALUES(?,?)",
                    (account_id, staff_id),
                )
            db.execute("DELETE FROM sessions WHERE user_id=?", (account_id,))
            db.execute(
                "UPDATE account_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL",
                (now_iso(), account_id),
            )
            audit(
                db,
                user["id"],
                "change_management_access",
                "user",
                account_id,
                {
                    "from": account["management_scope"],
                    "to": payload.management_scope,
                    "assigned_staff": sorted(ids),
                    "reason": payload.reason,
                },
            )
        return {"saved": True, "sessions_revoked": True}

    @app.post("/api/auth/recovery")
    def recovery(payload: RecoveryRequest, request: Request):
        from .config import settings

        email = str(payload.email).lower().strip()
        ip = request.client.host if request.client else "unknown"
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        link = None
        token = None
        with db_session() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                db.execute(
                    "SELECT COUNT(*) FROM account_requests WHERE (ip_address=? OR email=?) AND created_at>?",
                    (ip, email, cutoff),
                ).fetchone()[0]
                >= 5
            ):
                raise HTTPException(
                    429, "Too many recovery requests. Try again in 15 minutes."
                )
            db.execute(
                "INSERT INTO account_requests(email,ip_address,created_at) VALUES(?,?,?)",
                (email, ip, now_iso()),
            )
            account = db.execute(
                "SELECT id FROM users WHERE email=? AND active=1 AND invitation_pending=0",
                (email,),
            ).fetchone()
            if account and email_configured():
                token, link = issue_token(
                    db, account[0], "recovery", origin=settings.public_url
                )
        if link and deliver_link(email, link, "recovery"):
            with db_session() as db:
                db.execute(
                    "UPDATE account_tokens SET delivery='email_accepted' WHERE digest=?",
                    (token_digest(token),),
                )
                db.execute(
                    "UPDATE account_requests SET resolved=1 WHERE email=?", (email,)
                )
        return {
            "message": "If your account is eligible, a recovery email will be requested when delivery is available. Otherwise contact HV Swim for verified account recovery.",
            "email_delivery_configured": email_configured(),
        }

    @app.post("/api/account/{account_id}/recovery-link")
    def recovery_link(
        account_id: int,
        payload: PasswordProof,
        request: Request,
        user=Depends(session_user),
        x_csrf_token: str | None = Header(default=None),
    ):
        from .config import settings

        csrf_guard(request, user, x_csrf_token)
        owner(user)
        proof_attempt(user["id"])
        if not password_verify(payload.password, user["password_hash"]):
            raise HTTPException(403, "Confirm your current password")
        with db_session() as db:
            db.execute("BEGIN IMMEDIATE")
            account = db.execute(
                "SELECT * FROM users WHERE id=? AND active=1", (account_id,)
            ).fetchone()
            if not account:
                raise HTTPException(404, "Active account not found")
            _, link = issue_token(
                db, account_id, "recovery", origin=settings.public_url
            )
            audit(
                db,
                user["id"],
                "manual_recovery_link",
                "user",
                account_id,
                {"delivery": "verified_manual_handover_required"},
            )
            db.execute(
                "UPDATE account_requests SET resolved=1 WHERE email=?",
                (account["email"],),
            )
        return {
            "link": link,
            "email_accepted": False,
            "message": "Verify this person's identity before private handover. No email was sent.",
        }

    @app.post("/api/auth/redeem")
    def redeem(payload: RedeemInput):
        with db_session() as db:
            db.execute("BEGIN IMMEDIATE")
            token = db.execute(
                "SELECT * FROM account_tokens WHERE digest=? AND used_at IS NULL AND expires_at>?",
                (token_digest(payload.token), now_iso()),
            ).fetchone()
            if not token:
                raise HTTPException(
                    400, "Link expired or already used. Request a new link."
                )
            user = db.execute(
                "SELECT * FROM users WHERE id=?", (token["user_id"],)
            ).fetchone()
            if (token["purpose"] == "invite" and not user["invitation_pending"]) or (
                token["purpose"] == "recovery" and not user["active"]
            ):
                raise HTTPException(400, "Account is not available for this link")
            db.execute(
                "UPDATE users SET password_hash=?,must_change_password=0,active=1,invitation_pending=0,email_verified_at=CASE WHEN ?='email_accepted' THEN ? ELSE email_verified_at END WHERE id=?",
                (
                    password_hash(payload.password),
                    token["delivery"],
                    now_iso(),
                    user["id"],
                ),
            )
            db.execute(
                "UPDATE account_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL",
                (now_iso(), user["id"]),
            )
            db.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
            audit(db, user["id"], "redeem_" + token["purpose"], "user", user["id"])
        return {
            "saved": True,
            "message": "Password saved. Sign in with your new password. Authenticator protection, if enabled, remains required.",
        }

    @app.post("/api/account/mfa/setup")
    def mfa_setup(
        payload: PasswordProof,
        request: Request,
        user=Depends(session_user),
        x_csrf_token: str | None = Header(default=None),
    ):
        csrf_guard(request, user, x_csrf_token)
        proof_attempt(user["id"])
        if not password_verify(payload.password, user["password_hash"]):
            raise HTTPException(403, "Confirm your current password")
        if user["mfa_enabled"]:
            raise HTTPException(409, "Authenticator already enabled")
        secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
        with db_session() as db:
            db.execute(
                "INSERT INTO account_mfa(user_id,secret,pending_secret) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET pending_secret=excluded.pending_secret",
                (user["id"], "", encrypt_sensitive(secret)),
            )
        return {
            "secret": secret,
            "uri": f"otpauth://totp/{quote('HV Swim:'+user['email'])}?secret={secret}&issuer=HV%20Swim&algorithm=SHA1&digits=6&period=30",
            "message": "Add this key to your authenticator, then confirm a current code. Keep the key private.",
        }

    @app.post("/api/account/mfa/confirm")
    def mfa_confirm(
        payload: PasswordProof,
        request: Request,
        user=Depends(session_user),
        x_csrf_token: str | None = Header(default=None),
    ):
        csrf_guard(request, user, x_csrf_token)
        proof_attempt(user["id"])
        if not password_verify(payload.password, user["password_hash"]):
            raise HTTPException(403, "Confirm your current password")
        with db_session() as db:
            db.execute("BEGIN IMMEDIATE")
            record = db.execute(
                "SELECT * FROM account_mfa WHERE user_id=?", (user["id"],)
            ).fetchone()
            if not record or not record["pending_secret"]:
                raise HTTPException(409, "Start authenticator setup first")
            counter = matching_counter(
                decrypt_sensitive(record["pending_secret"]), payload.code
            )
            if counter is None:
                raise HTTPException(400, "Use the current six-digit authenticator code")
            db.execute(
                "UPDATE account_mfa SET secret=pending_secret,pending_secret=NULL,last_counter=? WHERE user_id=?",
                (counter, user["id"]),
            )
            db.execute("UPDATE users SET mfa_enabled=1 WHERE id=?", (user["id"],))
            db.execute(
                "DELETE FROM sessions WHERE user_id=? AND id<>?",
                (user["id"], user["session_id"]),
            )
            audit(db, user["id"], "enable_mfa", "user", user["id"])
        return {"enabled": True}

    @app.post("/api/account/mfa/disable")
    def mfa_disable(
        payload: PasswordProof,
        request: Request,
        user=Depends(session_user),
        x_csrf_token: str | None = Header(default=None),
    ):
        csrf_guard(request, user, x_csrf_token)
        proof_attempt(user["id"])
        with db_session() as db:
            db.execute("BEGIN IMMEDIATE")
            fresh = db.execute(
                "SELECT * FROM users WHERE id=?", (user["id"],)
            ).fetchone()
            if management_account_requires_mfa(fresh["role"]):
                raise HTTPException(
                    403,
                    "Management accounts must keep authenticator protection enabled",
                )
            if not password_verify(
                payload.password, fresh["password_hash"]
            ) or not verify_mfa(db, fresh, payload.code):
                raise HTTPException(
                    403, "Current password and a fresh authenticator code are required"
                )
            db.execute("UPDATE users SET mfa_enabled=0 WHERE id=?", (user["id"],))
            db.execute("DELETE FROM account_mfa WHERE user_id=?", (user["id"],))
            db.execute(
                "DELETE FROM sessions WHERE user_id=? AND id<>?",
                (user["id"], user["session_id"]),
            )
            audit(db, user["id"], "disable_mfa", "user", user["id"])
        return {"enabled": False}
