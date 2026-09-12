from __future__ import annotations

import asyncio
import base64
import binascii
import csv
import hashlib
import hmac
import io
import json
import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import parse_qs, quote, urlparse
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from .config import DATA_DIR, ROOT, settings
from . import identity, payroll_adapter, workforce
from .database import audit, db_session, initialise_database, rows
from .integrations import (
    current_bendigo_weather,
    decrypt_json,
    encrypt_json,
    integration_token_encryption_current,
    pool_sensor_reading,
    printify_products,
    printify_ready,
    safe_xero_online_invoice_url,
    shopify_create_cart,
    shopify_products,
    shopify_ready,
    weather_ready,
    xero_authorization_url,
    xero_create_draft_invoice,
    xero_exchange_code,
    xero_get_invoice,
    xero_invoice_configuration_ready,
    xero_ready,
    xero_token_valid,
)
from .oauth import (
    OAuthProviderError,
    authorization_url as oauth_authorization_url,
    exchange_code as oauth_exchange_code,
    provider_public_status as oauth_provider_public_status,
    provider_ready as oauth_provider_ready,
    verify_identity_token as oauth_verify_identity_token,
)
from .security import business_date_from_timestamp, business_today, decrypt_sensitive, encrypt_sensitive, expires_iso, new_token, now_iso, password_hash, password_needs_rehash, password_verify, public_user, token_digest

SESSION_COOKIE = "hv_session"
MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")
SWIMMER_SENSITIVE_FIELDS = ("emergency_contact", "medical_notes", "allergies", "medications", "support_notes")
INCIDENT_SENSITIVE_FIELDS = ("what_happened", "injury_observed", "first_aid_applied", "further_action", "witnesses", "first_aider", "supporting_notes")
LOGGER = logging.getLogger("hv_swim.backend")
DEFAULT_API_BODY_LIMIT = 2_000_000
QUALIFICATION_API_BODY_LIMIT = 7_100_000
APPLE_CALLBACK_BODY_LIMIT = 32_768

SUPPLIER_ROUTE_DETAILS: dict[str, dict[str, str]] = {
    "specialist_swim": {
        "label": "Specialist swim supplier",
        "automation": "manual_purchase_order",
        "boundary": "Swimwear and training equipment require fit, material, safety and chlorine testing before Shopify publication.",
    },
    "specialist_uniform": {
        "label": "Specialist uniform supplier",
        "automation": "manual_purchase_order",
        "boundary": "A controlled uniform quote and approved physical sample are required before ordering.",
    },
    "vistaprint": {
        "label": "VistaPrint manual / bulk",
        "automation": "manual_bulk_order",
        "boundary": "No live VistaPrint API sync is implemented; quote, proof and order references are recorded manually before Shopify stock is published.",
    },
    "printify": {
        "label": "Printify → Shopify",
        "automation": "printify_shopify",
        "boundary": "API mapping becomes available only after HV Swim supplies its Printify shop ID and token and approves a physical sample.",
    },
    "printify_or_vistaprint": {
        "label": "Printify or VistaPrint comparison",
        "automation": "supplier_comparison",
        "boundary": "Compare approved samples and landed costs before locking either automated Printify or manual VistaPrint fulfilment.",
    },
    "vistaprint_or_specialist": {
        "label": "VistaPrint or specialist comparison",
        "automation": "supplier_comparison",
        "boundary": "Use a manual quote and sample workflow; the chosen stock item can be sold through Shopify after approval.",
    },
    "manual_review": {
        "label": "Supplier review required",
        "automation": "manual_review",
        "boundary": "Confirm a suitable supplier, specification and physical sample before offering this product.",
    },
}

PRODUCT_PRODUCTION_METHODS: dict[str, str] = {
    "HV-SWIMWEAR": "Sample chlorine-resistant team swimwear, verify the full size range and approve every logo placement.",
    "HV-RASHIE": "Use a specialist UV/chlorine-resistant rashie supplier; test fabric, seams, print durability and sizing.",
    "HV-SWIM-SHORTS": "Use a specialist aquatic-apparel supplier and approve waist, liner, movement and chlorine durability.",
    "HV-TOWEL": "Compare embroidered and printed towel samples for absorbency, colour fastness and delivered cost.",
    "HV-HOODED-TOWEL": "Sample child-sized hooded towels and verify hood fit, absorbency, decoration comfort and wash durability.",
    "HV-MINI-HOODED-TOWEL": "Sample little-swimmer hooded wraps and verify fibre shedding, hood fit, absorbency, stitch backing and wash durability.",
    "HV-BOTTLE": "Obtain a bulk branded-bottle proof; verify food-contact documentation, lid quality and wash/rub durability.",
    "HV-INSULATED-TUMBLER": "Compare premium insulated cups and verify food-contact documentation, lid seal, heat cycles, hand comfort and wash durability.",
    "HV-JUNIOR-WARM-CUP": "Specialist sample gate: verify food-contact documentation, spill resistance and safe grip; label for parent-supervised warm, never hot, drinks.",
    "HV-GOGGLES": "Source compliant swimming goggles from a specialist; test junior fit, seal, materials and packaging.",
    "HV-TRAINING-MITTS": "Specialist review is mandatory; approve sizing, flexible material and coach-directed safe-use guidance.",
    "HV-BAG": "Compare wet-gear durability, ventilation and print quality before selecting Printify or a manual bulk supplier.",
    "HV-CAP": "Use a specialist silicone-cap printer and approve fit, colour and chlorine-resistant decoration.",
    "HV-KIDS-SUN-HAT": "Compare embroidered/transfer samples for fit, shade coverage and poolside durability.",
    "HV-STAFF-POLO": "Approve one embroidered performance-polo sample, then place controlled staff-size bulk orders.",
    "HV-STAFF-TEE": "Map an approved performance shirt to Printify and Shopify only after a wear, wash and logo sample passes.",
    "HV-STAFF-SHORTS": "Compare quick-dry uniform suppliers and approve movement, pockets, sizing and logo durability.",
    "HV-TEAM-HOODIE": "Map the approved hoodie to Printify and Shopify with manual order approval enabled at launch.",
    "HV-STAFF-PUFFER-VEST": "Obtain a controlled uniform quote and approve embroidery, warmth, movement and sizing.",
    "HV-STAFF-PUFFER-JACKET": "Obtain a controlled outerwear quote and approve embroidery, weather resistance and sizing.",
    "HV-STAFF-TRACKPANTS": "Approve a uniform sample for movement, warmth, pockets, wash performance and logo placement.",
    "HV-INSTRUCTOR-CAP": "Compare embroidered samples for fit, sun coverage and outdoor pool-deck durability.",
    "HV-FAMILY-TEE": "Map one approved premium tee blank to Printify and Shopify after print, fit, wash and Australian fulfilment tests pass.",
    "HV-FAMILY-CREW": "Map one approved premium crew blank to Printify and Shopify after decoration, pilling, shrinkage and wash tests pass.",
}


def fulfilment_mode_for_route(route: str) -> str:
    return SUPPLIER_ROUTE_DETAILS.get(route, SUPPLIER_ROUTE_DETAILS["manual_review"])["automation"]


def validate_production_config(candidate=settings) -> None:
    if candidate.database_url:
        raise RuntimeError("DATABASE_URL / HV_DATABASE_URL is unsupported by this SQLite build. Configure HV_DATA_DIR on a protected persistent disk; PostgreSQL requires a separately tested storage migration.")
    if not candidate.production:
        return
    insecure_secrets = {
        "local-demo-secret-change-before-production",
        "replace-with-a-long-random-production-secret",
    }
    if candidate.session_secret in insecure_secrets or len(candidate.session_secret) < 32:
        raise RuntimeError("HV_SESSION_SECRET must be a unique random value of at least 32 characters")
    if len(candidate.data_encryption_key) < 32 or candidate.data_encryption_key == candidate.session_secret:
        raise RuntimeError("HV_DATA_ENCRYPTION_KEY must be a separate random value of at least 32 characters")
    if not candidate.public_url.startswith("https://"):
        raise RuntimeError("HV_PUBLIC_URL must use HTTPS in production")
    xero_configured = bool(candidate.xero_client_id and candidate.xero_client_secret and candidate.xero_redirect_uri)
    if xero_configured and not candidate.xero_redirect_uri.startswith("https://"):
        raise RuntimeError("XERO_REDIRECT_URI must use HTTPS in production")
    if candidate.xero_sync_enabled and not xero_configured:
        raise RuntimeError("XERO_SYNC_ENABLED requires the complete Xero OAuth configuration")
    if candidate.xero_sync_enabled and (
        not candidate.xero_lesson_account_code
        or not candidate.xero_lesson_tax_type
        or candidate.xero_line_amount_type not in {"Exclusive", "Inclusive", "NoTax"}
    ):
        raise RuntimeError(
            "XERO_SYNC_ENABLED requires XERO_LESSON_ACCOUNT_CODE, XERO_LESSON_TAX_TYPE "
            "and a valid XERO_LINE_AMOUNT_TYPE"
        )
    shopify_fields = (candidate.shopify_store_domain, candidate.shopify_storefront_token)
    if any(shopify_fields) and not all(shopify_fields):
        raise RuntimeError("SHOPIFY_STORE_DOMAIN and SHOPIFY_STOREFRONT_TOKEN must be configured together")
    shopify_domain = candidate.shopify_store_domain
    if shopify_domain and (
        "://" in shopify_domain
        or "/" in shopify_domain
        or "@" in shopify_domain
        or not urlparse(f"https://{shopify_domain}").hostname
    ):
        raise RuntimeError("SHOPIFY_STORE_DOMAIN must be a hostname without a scheme or path")
    if candidate.pool_sensor_url and not candidate.pool_sensor_url.startswith("https://"):
        raise RuntimeError("POOL_SENSOR_URL must use HTTPS in production")
    google_fields = (candidate.google_client_id, candidate.google_client_secret)
    if any(google_fields) and not all(google_fields):
        raise RuntimeError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be configured together")
    google_redirect = candidate.google_redirect_uri or f"{candidate.public_url}/api/auth/oauth/google/callback"
    if all(google_fields) and not google_redirect.startswith("https://"):
        raise RuntimeError("GOOGLE_REDIRECT_URI must use HTTPS in production")
    apple_fields = (candidate.apple_client_id, candidate.apple_client_secret)
    if any(apple_fields) and not all(apple_fields):
        raise RuntimeError("APPLE_CLIENT_ID and APPLE_CLIENT_SECRET must be configured together")
    apple_redirect = candidate.apple_redirect_uri or f"{candidate.public_url}/api/auth/oauth/apple/callback"
    if all(apple_fields) and not apple_redirect.startswith("https://"):
        raise RuntimeError("APPLE_REDIRECT_URI must use HTTPS in production")


def migrate_integration_token_encryption() -> int:
    """Move legacy OAuth tokens onto the dedicated data-encryption key at startup."""
    migrated = 0
    with db_session() as db:
        for record in db.execute(
            "SELECT provider,encrypted_tokens FROM integration_connections WHERE encrypted_tokens IS NOT NULL"
        ):
            if integration_token_encryption_current(record["encrypted_tokens"]):
                continue
            token = decrypt_json(record["encrypted_tokens"])
            db.execute(
                "UPDATE integration_connections SET encrypted_tokens=?,updated_at=? WHERE provider=?",
                (encrypt_json(token), now_iso(), record["provider"]),
            )
            audit(
                db,
                None,
                "migrate_integration_token_encryption",
                "integration",
                record["provider"],
                {"format": "enc:v2"},
            )
            migrated += 1
    return migrated


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_production_config()
    initialise_database()
    identity.migrate()
    workforce.migrate()
    payroll_adapter.migrate()
    migrate_integration_token_encryption()
    yield


app = FastAPI(
    title="HV Swim Bendigo Platform API",
    version="5.13.0",
    docs_url="/api/docs" if not settings.production else None,
    openapi_url="/openapi.json" if not settings.production else None,
    redoc_url=None,
    lifespan=lifespan,
)

# Capacitor serves its bundled shell from a local app origin before opening the connected
# HTTPS platform. Allow only the documented native origins; API sessions and CSRF checks
# still apply normally to protected routes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["capacitor://localhost", "http://localhost", "https://localhost"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "X-CSRF-Token"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
if settings.production:
    production_host = urlparse(settings.public_url).hostname
    if production_host:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=[production_host])




@app.middleware("http")
async def security_headers(request: Request, call_next):
    request_id = new_token(12)
    request.state.request_id = request_id
    request_path = str(request.scope.get("path") or "")
    raw_path = request.scope.get("raw_path", b"")
    host = request.headers.get("host", "")
    invalid_target = (
        not request_path.startswith("/")
        or "\\" in request_path
        or (isinstance(raw_path, bytes) and b"\\" in raw_path)
        or any(character in host for character in ("/", "\\", "@", "#", "?", "\r", "\n", "\t", " "))
    )
    if invalid_target:
        response = JSONResponse(status_code=400, content={"detail": "Invalid request target"})
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = request_id
        return response
    content_length = request.headers.get("content-length")
    body_limit = (
        QUALIFICATION_API_BODY_LIMIT
        if request_path == "/api/staff/qualifications"
        else APPLE_CALLBACK_BODY_LIMIT
        if request_path == "/api/auth/oauth/apple/callback"
        else DEFAULT_API_BODY_LIMIT
    )
    if request_path.startswith("/api/") and content_length:
        try:
            if int(content_length) < 0:
                raise ValueError
            if int(content_length) > body_limit:
                response = JSONResponse(status_code=413, content={"detail": "Request body is too large"})
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["Cache-Control"] = "no-store"
                response.headers["X-Request-ID"] = request_id
                return response
        except ValueError:
            response = JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})
            response.headers["X-Request-ID"] = request_id
            return response
    elif request_path.startswith("/api/"):
        # Do not let HTTP/1.1 chunked requests bypass the Content-Length gate.
        # Starlette replays this cached body to the route handler after the check.
        if len(await request.body()) > body_limit:
            response = JSONResponse(status_code=413, content={"detail": "Request body is too large"})
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Request-ID"] = request_id
            return response
    content_type = request.headers.get("content-type", "").lower()
    if request_path.startswith("/api/") and request_path != "/api/auth/oauth/apple/callback" and content_type.startswith(
        ("application/x-www-form-urlencoded", "multipart/form-data")
    ):
        response = JSONResponse(status_code=415, content={"detail": "API requests must use JSON"})
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = request_id
        return response
    try:
        response = await call_next(request)
    except Exception:
        if not settings.production:
            raise
        LOGGER.exception("Unhandled request failure", extra={"request_id": request_id, "path": request_path})
        response = JSONResponse(
            status_code=500,
            content={"detail": "The request could not be completed", "request_id": request_id},
        )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Origin-Agent-Cluster"] = "?1"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; object-src 'none'; connect-src 'self'; frame-src https://www.facebook.com; "
        "form-action 'self' mailto:; base-uri 'self'; frame-ancestors 'self'"
    )
    if settings.production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    path = request_path
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif path.startswith("/assets/") and not settings.production:
        response.headers["Cache-Control"] = "no-store"
    elif path.startswith("/assets/") and request.url.query.startswith("v="):
        # Versioned asset URLs change whenever the file changes, so they can be cached hard.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path.startswith("/assets/"):
        response.headers.setdefault("Cache-Control", "public, max-age=86400")
    elif path.endswith(".html") or path in {"/", ""}:
        # Always revalidate pages so corrected copy and prices are never served stale.
        response.headers["Cache-Control"] = "no-cache"
    return response


# Times are stored as text and ordered as text in the timetable queries, so the format has
# to be exact: zero-padded 24-hour HH:MM and nothing else.
TimeOfDay = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]
SupportCategory = Literal["lessons", "bookings", "billing", "merchandise", "pool_conditions", "accessibility_support", "app_help", "other"]
SupportStatus = Literal["new", "open", "waiting_customer", "resolved", "closed"]
SupportPriority = Literal["low", "normal", "high", "urgent"]
AlertSeverity = Literal["closure", "change", "reopening", "information"]


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    code: str = Field(default="", max_length=6)


class ChangePasswordInput(BaseModel):
    current_password: str = Field(min_length=8, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)


class BookingInput(BaseModel):
    class_id: int
    swimmer_id: int


class AbsenceReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    booking_id: int = Field(ge=1)
    occurrence_date: date
    reason_category: Literal["illness", "family", "school", "other"]


class LessonAttendanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    booking_id: int = Field(ge=1)
    occurrence_date: date
    attendance_status: Literal["present", "absent", "late", "excused"]
    parent_onsite_confirmed: bool | None = None
    private_note: str = Field(default="", max_length=600)

    @model_validator(mode="after")
    def clean_attendance_note(self) -> "LessonAttendanceInput":
        self.private_note = self.private_note.strip()
        return self


class SchoolTermInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=100)
    start_date: date
    end_date: date
    absence_credit_limit: int = Field(default=2, ge=0, le=10)
    activate: bool = False

    @model_validator(mode="after")
    def validate_term(self) -> "SchoolTermInput":
        self.name = self.name.strip()
        if self.end_date < self.start_date:
            raise ValueError("Term end date must be on or after its start date")
        return self


class AchievementAwardInput(BaseModel):
    template_code: str = Field(min_length=3, max_length=50, pattern=r"^[a-z0-9-]+$")
    swimmer_id: int = Field(ge=1)
    class_id: int | None = Field(default=None, ge=1)
    evidence_note: str = Field(min_length=3, max_length=600)
    private_staff_note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def clean_achievement_notes(self) -> "AchievementAwardInput":
        self.evidence_note = self.evidence_note.strip()
        self.private_staff_note = self.private_staff_note.strip()
        if len(self.evidence_note) < 3:
            raise ValueError("Family-visible evidence must describe the achievement")
        return self


class AchievementRevokeInput(BaseModel):
    reason: str = Field(min_length=5, max_length=400)

    @model_validator(mode="after")
    def clean_revocation_reason(self) -> "AchievementRevokeInput":
        self.reason = self.reason.strip()
        if len(self.reason) < 5:
            raise ValueError("A clear revocation reason is required")
        return self


class PublicSupportTicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: SupportCategory
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(default="", max_length=40)
    subject: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=10, max_length=2000)
    consent_acknowledged: bool
    website: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def require_support_consent(self) -> "PublicSupportTicketInput":
        self.name = self.name.strip()
        self.phone = self.phone.strip()
        self.subject = self.subject.strip()
        self.message = self.message.strip()
        if len(self.name) < 2 or len(self.subject) < 3 or len(self.message) < 10:
            raise ValueError("Complete the required support fields")
        if not self.website.strip() and not self.consent_acknowledged:
            raise ValueError("Consent is required before sending a support request")
        return self


class CustomerSupportTicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: SupportCategory
    subject: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=10, max_length=2000)
    phone: str = Field(default="", max_length=40)

    @model_validator(mode="after")
    def clean_customer_ticket(self) -> "CustomerSupportTicketInput":
        self.subject = self.subject.strip()
        self.message = self.message.strip()
        self.phone = self.phone.strip()
        if len(self.subject) < 3 or len(self.message) < 10:
            raise ValueError("Complete the required support fields")
        return self


class CustomerSupportReplyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=2, max_length=2000)

    @model_validator(mode="after")
    def clean_customer_reply(self) -> "CustomerSupportReplyInput":
        self.message = self.message.strip()
        if len(self.message) < 2:
            raise ValueError("Enter a reply")
        return self


class StaffSupportReplyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=2, max_length=3000)
    internal_note: bool = False

    @model_validator(mode="after")
    def clean_staff_reply(self) -> "StaffSupportReplyInput":
        self.message = self.message.strip()
        if len(self.message) < 2:
            raise ValueError("Enter a reply or internal note")
        return self


class SupportTicketUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SupportStatus | None = None
    priority: SupportPriority | None = None
    assigned_to: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_support_change(self) -> "SupportTicketUpdateInput":
        if not self.model_fields_set:
            raise ValueError("Choose at least one ticket field to update")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Status cannot be empty")
        if "priority" in self.model_fields_set and self.priority is None:
            raise ValueError("Priority cannot be empty")
        return self


class PublicAlertInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: AlertSeverity
    title: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=5, max_length=600)
    location_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def clean_alert(self) -> "PublicAlertInput":
        self.title = self.title.strip()
        self.message = self.message.strip()
        if len(self.title) < 3 or len(self.message) < 5:
            raise ValueError("Complete the alert title and message")
        return self


class PublicAlertResolveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=5, max_length=300)

    @model_validator(mode="after")
    def clean_alert_resolution(self) -> "PublicAlertResolveInput":
        self.reason = self.reason.strip()
        if len(self.reason) < 5:
            raise ValueError("A clear resolution reason is required")
        return self


class ClockInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["in", "break_start", "break_end", "out"]
    location_slug: str = "wood-street"
    request_id: str | None = Field(default=None, min_length=16, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    entry_id: int | None = Field(default=None, gt=0)
    paid_break: bool = False


class PoolReadingInput(BaseModel):
    location_slug: str
    temperature: float | None = Field(default=None, ge=10, le=45)
    status: Literal["open", "changed", "closed"]
    note: str = Field(default="", max_length=500)


class ChecklistInput(BaseModel):
    location_slug: str
    deck_safe: bool
    first_aid_ready: bool
    equipment_ready: bool
    water_checked: bool
    notes: str = Field(default="", max_length=800)


class SubmitTimesheetInput(BaseModel):
    entry_ids: list[int]


class DailyHoursInput(BaseModel):
    work_date: date
    hours: float = Field(gt=0, le=16)


class HoursEntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week_start: date
    location_slug: str
    entry_mode: Literal["weekly", "daily"]
    total_hours: float | None = Field(default=None, gt=0, le=80)
    daily_entries: list[DailyHoursInput] = Field(default_factory=list, max_length=7)
    notes: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_hours(self) -> "HoursEntryInput":
        if self.week_start.weekday() != 0:
            raise ValueError("Week start must be a Monday")
        week_end = self.week_start + timedelta(days=6)
        if self.entry_mode == "weekly":
            if self.total_hours is None:
                raise ValueError("Enter the total hours for the week")
            self.daily_entries = []
        else:
            if not self.daily_entries:
                raise ValueError("Enter hours for at least one day")
            dates = [entry.work_date for entry in self.daily_entries]
            if len(set(dates)) != len(dates):
                raise ValueError("Each work date can appear only once")
            if any(value < self.week_start or value > week_end for value in dates):
                raise ValueError("Daily hours must fall inside the selected payroll week")
            if sum(entry.hours for entry in self.daily_entries) > 80:
                raise ValueError("Weekly hours cannot exceed 80")
            self.total_hours = None
        self.notes = self.notes.strip()
        return self


class ApproveTimesheetInput(BaseModel):
    entry_id: int


class QualificationDocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_id: int | None = Field(default=None, ge=1)
    qualification_type: str = Field(min_length=2, max_length=100)
    expiry_date: date
    original_filename: str = Field(min_length=1, max_length=180)
    document_media_type: Literal["application/pdf", "image/png", "image/jpeg", "image/webp"]
    document_base64: str = Field(min_length=20, max_length=7_000_000)
    reminder_days: int = Field(default=60, ge=7, le=120)

    @model_validator(mode="after")
    def clean_qualification(self) -> "QualificationDocumentInput":
        self.qualification_type = self.qualification_type.strip()
        self.original_filename = Path(self.original_filename).name.strip()
        if not self.original_filename:
            raise ValueError("A document filename is required")
        return self


class StudentSkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    swimmer_id: int = Field(ge=1)
    skill_name: str = Field(min_length=2, max_length=100)
    skill_status: Literal["practising", "developing", "achieved"]
    feedback: str = Field(min_length=3, max_length=1000)
    next_step: str = Field(default="", max_length=500)


class IncidentReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    swimmer_id: int = Field(ge=1)
    location_slug: str
    incident_at: datetime
    incident_type: Literal["injury", "illness", "behaviour", "near_miss", "safeguarding", "other"]
    what_happened: str = Field(min_length=10, max_length=3000)
    injury_observed: str = Field(default="", max_length=2000)
    first_aid_applied: str = Field(default="", max_length=2000)
    further_action: str = Field(default="", max_length=2000)
    witnesses: str = Field(default="", max_length=500)
    parent_notified: bool = False
    severity: Literal["unassessed", "minor", "moderate", "serious", "critical"] = "unassessed"
    first_aider: str = Field(default="", max_length=200)
    emergency_services: bool = False
    supporting_notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def clean_incident(self) -> "IncidentReportInput":
        for field_name in ("what_happened", "injury_observed", "first_aid_applied", "further_action", "witnesses"):
            setattr(self, field_name, getattr(self, field_name).strip())
        return self


class IncidentStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["open", "follow_up", "closed"]
    manager_review: str = Field(default="", max_length=2000)


class AdminUserInput(BaseModel):
    email: EmailStr
    temporary_password: str = Field(min_length=12, max_length=200)
    role: Literal["customer", "staff", "admin"]
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=40)


class AdminSwimmerInput(BaseModel):
    customer_id: int
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    date_of_birth: date | None = None
    level: str = Field(default="Program match required", max_length=80)
    emergency_contact: str = Field(default="", max_length=180)
    medical_notes: str = Field(default="", max_length=800)
    allergies: str = Field(default="", max_length=600)
    medications: str = Field(default="", max_length=600)
    support_notes: str = Field(default="", max_length=800)
    photo_consent: bool = False


class FamilySwimmerProfileInput(BaseModel):
    emergency_contact: str = Field(min_length=3, max_length=180)
    medical_notes: str = Field(default="", max_length=800)
    allergies: str = Field(default="", max_length=600)
    medications: str = Field(default="", max_length=600)
    support_notes: str = Field(default="", max_length=800)


class AccountStatusInput(BaseModel):
    active: bool


class AdminPasswordResetInput(BaseModel):
    temporary_password: str = Field(min_length=12, max_length=200)


class XeroStaffMappingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: str = Field(default="", max_length=80)
    payroll_calendar_id: str = Field(default="", max_length=80)
    shopify_customer_gid: str = Field(default="", max_length=160)

    @model_validator(mode="after")
    def validate_staff_mapping(self) -> "XeroStaffMappingInput":
        self.employee_id = self.employee_id.strip()
        self.payroll_calendar_id = self.payroll_calendar_id.strip()
        self.shopify_customer_gid = self.shopify_customer_gid.strip()
        if self.shopify_customer_gid and not self.shopify_customer_gid.startswith("gid://shopify/Customer/"):
            raise ValueError("Use the full Shopify Customer GID")
        return self


class CustomerIntegrationMappingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    xero_contact_id: str = Field(default="", max_length=100)
    shopify_customer_gid: str = Field(default="", max_length=160)

    @model_validator(mode="after")
    def validate_customer_mapping(self) -> "CustomerIntegrationMappingInput":
        self.xero_contact_id = self.xero_contact_id.strip()
        self.shopify_customer_gid = self.shopify_customer_gid.strip()
        if self.shopify_customer_gid and not self.shopify_customer_gid.startswith("gid://shopify/Customer/"):
            raise ValueError("Use the full Shopify Customer GID")
        return self


class InvoiceDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: int = Field(ge=1)
    charge_ids: list[int] = Field(min_length=1, max_length=50)
    due_date: date
    management_note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_invoice_draft(self) -> "InvoiceDraftInput":
        if len(set(self.charge_ids)) != len(self.charge_ids):
            raise ValueError("Each lesson charge can appear only once")
        if self.due_date < business_today():
            raise ValueError("Invoice due date cannot be in the past")
        if self.due_date > business_today() + timedelta(days=365):
            raise ValueError("Invoice due date must be within the next year")
        self.management_note = self.management_note.strip()
        return self


class ClassInput(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    title: str = Field(min_length=3, max_length=80)
    level: str = Field(min_length=2, max_length=80)
    location_slug: str
    instructor_id: int | None = None
    weekday: int = Field(ge=0, le=6)
    start_time: TimeOfDay
    duration_minutes: int = Field(ge=15, le=180)
    capacity: int = Field(ge=1, le=20)
    price_cents: int = Field(ge=0, le=100_000)


class RosterInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    staff_id: int = Field(ge=1)
    location_slug: str
    shift_date: date
    start_time: TimeOfDay
    end_time: TimeOfDay
    role_label: str = Field(default="Instructor", min_length=1, max_length=80)

    @model_validator(mode="after")
    def check_shift_order(self):
        if self.end_time <= self.start_time:
            raise ValueError("A shift must finish after it starts")
        return self


class NotificationInput(BaseModel):
    user_id: int | None = None
    audience_role: Literal["customer", "staff", "admin"] | None = None
    title: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=3, max_length=800)
    kind: str = Field(default="info", max_length=30)
    channels: list[Literal["in_app", "email", "sms", "push"]] = Field(default_factory=lambda: ["in_app"])


class ReminderPreferencesInput(BaseModel):
    enabled: bool = True
    hours_before: int = Field(default=24, ge=2, le=72)
    channels: list[Literal["in_app", "email", "sms", "push"]] = Field(default_factory=lambda: ["in_app"])

    @model_validator(mode="after")
    def keep_in_app_delivery(self):
        if "in_app" not in self.channels:
            raise ValueError("In-app lesson reminders must remain enabled")
        self.channels = list(dict.fromkeys(self.channels))
        return self


class EnquiryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    enquiry_type: Literal["lesson", "merchandise", "general", "existing_customer", "lesson_question", "private_lesson", "billing", "feedback", "other"] = "lesson"
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(default="", max_length=40)
    swimmer_name: str = Field(default="", max_length=100)
    swimmer_age: str = Field(default="", max_length=50)
    program_interest: str = Field(default="", max_length=100)
    preferred_class: str = Field(default="", max_length=180)
    preferred_days: str = Field(default="", max_length=180)
    contact_method: Literal["email", "phone", "sms"] = "email"
    experience: str = Field(default="", max_length=500)
    support_needs: str = Field(default="", max_length=500)
    # Honeypot. The form renders this hidden and off-screen, so a person never fills it in.
    website: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def validate_reply_details(self):
        if self.contact_method in {"phone", "sms"} and not 8 <= sum(character.isdecimal() for character in self.phone) <= 15:
            raise ValueError("Enter a complete phone number for your selected reply method")
        return self


class EnquiryStatusInput(BaseModel):
    status: Literal["new", "contacted", "trial_booked", "closed"]
    revision: int = Field(ge=0)
    assigned_to: int | None = Field(default=None, gt=0)
    next_action: Literal["review", "contact", "confirm_preferences", "arrange_assessment", "confirm_placement", "none"] = "review"
    follow_up_on: date | None = None



class SiteSettingsInput(BaseModel):
    announcement_enabled: bool = False
    announcement_text: str = Field(min_length=3, max_length=180)
    enrolment_status: Literal["open", "limited", "waitlist"] = "open"
    hero_eyebrow: str = Field(min_length=3, max_length=90)
    hero_heading: str = Field(min_length=3, max_length=80)
    hero_accent: str = Field(min_length=3, max_length=80)
    hero_intro: str = Field(min_length=20, max_length=360)
    primary_cta: str = Field(min_length=3, max_length=50)
    feature_merch_home: bool = False
    feature_association_badges: bool = False


class AssociationCredentialInput(BaseModel):
    membership_reference: str = Field(default="", max_length=160)
    valid_until: date | None = None
    usage_rights_confirmed: bool = False
    internal_notes: str = Field(default="", max_length=800)
    artwork_png_base64: str | None = Field(default=None, max_length=1_400_000)

    @model_validator(mode="after")
    def clean_evidence(self) -> "AssociationCredentialInput":
        self.membership_reference = self.membership_reference.strip()
        self.internal_notes = self.internal_notes.strip()
        return self


class ProductUpdateInput(BaseModel):
    price_cents: int = Field(ge=0, le=100_000)
    status: Literal["planned", "sampling", "approved", "available", "paused"]
    sample_status: Literal["not_ordered", "ordered", "received", "changes_required", "approved"] = "not_ordered"
    cost_cents: int | None = Field(default=None, ge=0, le=100_000)
    supplier_route: Literal["specialist_swim", "specialist_uniform", "vistaprint", "printify", "printify_or_vistaprint", "vistaprint_or_specialist", "manual_review"] = "manual_review"
    personalisation: str = Field(default="", max_length=240)
    shopify_gid: str | None = Field(default=None, max_length=180)
    printify_product_id: str | None = Field(default=None, max_length=120)
    supplier_reference: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def validate_supplier_mapping(self) -> "ProductUpdateInput":
        if self.printify_product_id and "printify" not in self.supplier_route:
            raise ValueError("A Printify product ID can only be set for a Printify-capable supplier route")
        if self.shopify_gid and not self.shopify_gid.startswith("gid://shopify/Product/"):
            raise ValueError("Shopify product mapping must use a Shopify Product GID")
        return self


class LocationUpdateInput(BaseModel):
    public_status: str = Field(min_length=3, max_length=80)
    venue_type: str = Field(min_length=3, max_length=140)
    parking: str = Field(min_length=3, max_length=240)
    accessibility: str = Field(min_length=3, max_length=320)


class WaitlistActionInput(BaseModel):
    action: Literal["promote", "remove"]


class CartInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_id: str = Field(
        min_length=30,
        max_length=180,
        pattern=r"^gid://shopify/ProductVariant/[A-Za-z0-9_-]+$",
    )
    quantity: int = Field(default=1, ge=1, le=20)


LOGIN_ATTEMPT_RETENTION_DAYS = 30
OAUTH_ATTEMPT_MINUTES = 10


def login_attempt_cutoff() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=LOGIN_ATTEMPT_RETENTION_DAYS)).isoformat()


def issue_session(
    db: sqlite3.Connection,
    user: sqlite3.Row,
    response: Response,
    *,
    ip_address: str,
    action: str,
    audit_detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session_id, csrf = new_token(32), new_token(24)
    stored_session_id = token_digest(session_id)
    db.execute("DELETE FROM sessions WHERE expires_at<=?", (now_iso(),))
    db.execute(
        "INSERT INTO sessions(id,user_id,csrf_token,created_at,expires_at) VALUES(?,?,?,?,?)",
        (stored_session_id, user["id"], csrf, now_iso(), expires_iso()),
    )
    audit(db, user["id"], action, "session", stored_session_id[-12:], audit_detail, ip_address)
    db.execute("UPDATE users SET last_login_at=? WHERE id=?", (now_iso(), user["id"]))
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=14 * 24 * 60 * 60,
        httponly=True,
        secure=settings.production,
        samesite="strict",
        path="/",
    )
    return {"user": public_user(user), "csrf_token": csrf}


def client_ip(request: Request) -> str:
    # Uvicorn should be configured with explicit trusted proxy IPs in production.
    # Never trust a client-supplied X-Forwarded-For header directly.
    return request.client.host if request.client else "unknown"


def session_user(request: Request) -> dict[str, Any]:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        raise HTTPException(status_code=401, detail="Sign in required")
    with db_session() as db:
        row = db.execute(
            """SELECT s.id session_id,s.csrf_token,s.expires_at,u.* FROM sessions s
               JOIN users u ON u.id=s.user_id WHERE s.id=? AND s.expires_at>? AND u.active=1""",
            (token_digest(session_id), now_iso()),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Session expired")
        if row["must_change_password"] and request.url.path not in {"/api/auth/me", "/api/auth/logout", "/api/auth/change-password"}:
            raise HTTPException(status_code=403, detail="Change your temporary password before using the workspace")
        return dict(row)


def require_roles(*roles: str):
    def dependency(user: dict[str, Any] = Depends(session_user)) -> dict[str, Any]:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="You do not have access to this action")
        return user
    return dependency


def csrf_guard(request: Request, user: dict[str, Any], token: str | None) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if not token or not hmac.compare_digest(token, user["csrf_token"] or ""):
        raise HTTPException(status_code=403, detail="Security token is missing or expired")


def location_by_slug(db: sqlite3.Connection, slug: str) -> sqlite3.Row:
    row = db.execute("SELECT * FROM locations WHERE slug=?", (slug,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Location not found")
    return row


def term_for_date(db: sqlite3.Connection, occurrence: date) -> sqlite3.Row | None:
    """Return the single configured term covering a business date.

    Closed terms remain valid for historical registers. Draft terms never drive family or
    staff operations, and the partial unique index ensures only one active term exists.
    """
    return db.execute(
        """SELECT * FROM school_terms
           WHERE status IN ('active','closed') AND start_date<=? AND end_date>=?
           ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,id DESC LIMIT 1""",
        (occurrence.isoformat(), occurrence.isoformat()),
    ).fetchone()


def active_term(db: sqlite3.Connection) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM school_terms WHERE status='active' LIMIT 1").fetchone()


def public_term_context(db: sqlite3.Connection) -> dict[str, Any]:
    term = active_term(db)
    if not term:
        return {
            "configured": False,
            "in_session": False,
            "message": "Management term dates have not been published yet.",
        }
    today = business_today()
    data = dict(term)
    data["configured"] = True
    data["in_session"] = term["start_date"] <= today.isoformat() <= term["end_date"]
    data["is_preview"] = term["source"] == "preview"
    # Never expose internal user references or imply a preview range is an official date.
    for field in ("created_by", "created_at", "updated_at"):
        data.pop(field, None)
    data["message"] = (
        "Preview calendar for local testing only."
        if data["is_preview"]
        else ("Lessons are operating within the published term." if data["in_session"] else "The published term is outside today's date.")
    )
    return data


def next_class_occurrence(weekday: int, start: date, term_end: date) -> date | None:
    candidate = start + timedelta(days=(weekday - start.weekday()) % 7)
    return candidate if candidate <= term_end else None


def reminder_preferences(db: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    row = db.execute("SELECT * FROM reminder_preferences WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        return {"user_id": user_id, "enabled": True, "hours_before": 24, "channels": ["in_app"]}
    item = dict(row)
    item["enabled"] = bool(item["enabled"])
    item["channels"] = json.loads(item["channels"] or '["in_app"]')
    return item


def materialise_due_lesson_reminders(db: sqlite3.Connection, user_id: int) -> int:
    preferences = reminder_preferences(db, user_id)
    if not preferences["enabled"]:
        return 0
    term = active_term(db)
    if not term:
        return 0
    local_now = datetime.now(MELBOURNE_TZ)
    window_end = local_now + timedelta(hours=preferences["hours_before"])
    created = 0
    bookings = db.execute(
        """SELECT b.id booking_id,s.first_name swimmer_first,c.title,c.weekday,c.start_time,l.name location_name
           FROM bookings b JOIN swimmers s ON s.id=b.swimmer_id JOIN classes c ON c.id=b.class_id
           JOIN locations l ON l.id=c.location_id
           WHERE s.customer_id=? AND b.status='confirmed' AND c.active=1""",
        (user_id,),
    )
    term_start = date.fromisoformat(term["start_date"])
    term_end = date.fromisoformat(term["end_date"])
    for booking in bookings:
        occurrence = next_class_occurrence(booking["weekday"], max(local_now.date(), term_start), term_end)
        if not occurrence:
            continue
        lesson_time = datetime.strptime(booking["start_time"], "%H:%M").time()
        lesson_at = datetime.combine(occurrence, lesson_time, tzinfo=MELBOURNE_TZ)
        if lesson_at <= local_now:
            occurrence += timedelta(days=7)
            lesson_at += timedelta(days=7)
        if occurrence > term_end or lesson_at > window_end:
            continue
        existing = db.execute(
            "SELECT 1 FROM lesson_reminder_dispatches WHERE booking_id=? AND occurrence_date=? AND user_id=?",
            (booking["booking_id"], occurrence.isoformat(), user_id),
        ).fetchone()
        if existing:
            continue
        notification_id = db.execute(
            """INSERT INTO notifications(user_id,title,message,kind,delivery_channels,created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                user_id,
                f"Lesson reminder · {booking['swimmer_first']}",
                f"{booking['title']} is at {booking['start_time']} on {occurrence.strftime('%A')} at {booking['location_name']}.",
                "lesson_reminder",
                json.dumps(preferences["channels"]),
                now_iso(),
            ),
        ).lastrowid
        db.execute(
            """INSERT INTO lesson_reminder_dispatches
               (booking_id,user_id,occurrence_date,notification_id,status,created_at)
               VALUES(?,?,?,?,?,?)""",
            (booking["booking_id"], user_id, occurrence.isoformat(), notification_id, "delivered_in_app", now_iso()),
        )
        created += 1
    return created


def create_xero_lesson_charge(
    db: sqlite3.Connection,
    *,
    booking_id: int,
    customer_id: int,
    term: sqlite3.Row,
    swim_class: sqlite3.Row,
) -> dict[str, Any]:
    existing = db.execute("SELECT * FROM lesson_charges WHERE booking_id=?", (booking_id,)).fetchone()
    if existing:
        return dict(existing)
    first = next_class_occurrence(swim_class["weekday"], date.fromisoformat(term["start_date"]), date.fromisoformat(term["end_date"]))
    if not first:
        raise HTTPException(status_code=409, detail="This class has no lesson dates in the active term")
    lesson_count = ((date.fromisoformat(term["end_date"]) - first).days // 7) + 1
    # Guarantee the permanent identifiers inside the enrolment transaction. New family
    # and swimmer records receive them earlier, while this closes the gap for migrated or
    # legacy records before an invoice reference is created.
    db.execute(
        """UPDATE users SET customer_number=printf('HVS-%06d',id)
           WHERE id=? AND role='customer' AND (customer_number IS NULL OR customer_number='')""",
        (customer_id,),
    )
    db.execute(
        """UPDATE swimmers SET swimmer_number=printf('HVS-S-%06d',id)
           WHERE id=(SELECT swimmer_id FROM bookings WHERE id=?)
             AND (swimmer_number IS NULL OR swimmer_number='')""",
        (booking_id,),
    )
    identity = db.execute(
        """SELECT u.customer_number,u.xero_contact_id,s.swimmer_number,s.first_name,s.last_name
           FROM bookings b JOIN swimmers s ON s.id=b.swimmer_id
           JOIN users u ON u.id=s.customer_id
           WHERE b.id=? AND u.id=?""",
        (booking_id, customer_id),
    ).fetchone()
    if not identity or not identity["customer_number"] or not identity["swimmer_number"]:
        raise HTTPException(status_code=409, detail="Family and swimmer numbers could not be issued for this enrolment")
    for _ in range(10):
        fragment = new_token(5).replace("-", "").replace("_", "").upper()[:6]
        reference = (
            f"{identity['customer_number']}-{identity['swimmer_number'].replace('HVS-S-', 'S')}-"
            f"{business_today().year}-{fragment}"
        )
        if not db.execute("SELECT 1 FROM lesson_charges WHERE reference=?", (reference,)).fetchone():
            break
    else:
        raise HTTPException(status_code=503, detail="A secure Xero billing reference could not be created")
    charge_id = db.execute(
        """INSERT INTO lesson_charges
           (reference,booking_id,customer_id,term_id,provider,per_lesson_cents,lesson_count,amount_cents,
            family_customer_number,swimmer_number,xero_contact_id,invoice_description,status,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            reference, booking_id, customer_id, term["id"], "xero", swim_class["price_cents"], lesson_count,
            swim_class["price_cents"] * lesson_count, identity["customer_number"], identity["swimmer_number"],
            identity["xero_contact_id"],
            f"{term['name']} · {swim_class['title']} · {identity['first_name']} {identity['last_name']} "
            f"({identity['swimmer_number']}) · {lesson_count} lessons at $22.50",
            "pending_xero_invoice", now_iso(),
        ),
    ).lastrowid
    return dict(db.execute("SELECT * FROM lesson_charges WHERE id=?", (charge_id,)).fetchone())


def billing_invoice_number(db: sqlite3.Connection) -> str:
    for _ in range(12):
        fragment = "".join(character for character in new_token(8).upper() if character.isalnum())[:8]
        if len(fragment) < 6:
            continue
        number = f"HVS-INV-{business_today().year}-{fragment}"
        if not db.execute("SELECT 1 FROM billing_invoices WHERE invoice_number=?", (number,)).fetchone():
            return number
    raise HTTPException(status_code=503, detail="A unique invoice number could not be created")


def record_billing_event(
    db: sqlite3.Connection,
    invoice_id: int,
    event_type: str,
    *,
    from_status: str | None,
    to_status: str | None,
    created_by: int | None,
    detail: dict[str, Any] | None = None,
) -> None:
    db.execute(
        """INSERT INTO billing_invoice_events
           (invoice_id,event_type,from_status,to_status,detail,created_by,created_at)
           VALUES(?,?,?,?,?,?,?)""",
        (
            invoice_id,
            event_type,
            from_status,
            to_status,
            json.dumps(detail or {}),
            created_by,
            now_iso(),
        ),
    )


def billing_invoice_payload(db: sqlite3.Connection, invoice_id: int) -> dict[str, Any]:
    invoice = db.execute(
        """SELECT bi.*,u.first_name customer_first,u.last_name customer_last,u.email customer_email,
                  t.name term_name,creator.first_name created_by_first,creator.last_name created_by_last,
                  approver.first_name approved_by_first,approver.last_name approved_by_last
           FROM billing_invoices bi JOIN users u ON u.id=bi.customer_id
           LEFT JOIN school_terms t ON t.id=bi.term_id
           JOIN users creator ON creator.id=bi.created_by
           LEFT JOIN users approver ON approver.id=bi.approved_by
           WHERE bi.id=?""",
        (invoice_id,),
    ).fetchone()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    result = dict(invoice)
    result["management_note"] = decrypt_sensitive(result.get("management_note")) or ""
    result["lines"] = rows(
        db.execute(
            """SELECT bil.id,bil.lesson_charge_id,bil.description,bil.quantity,bil.unit_amount_cents,
                      bil.line_amount_cents,bil.student_number,lc.reference charge_reference
               FROM billing_invoice_lines bil JOIN lesson_charges lc ON lc.id=bil.lesson_charge_id
               WHERE bil.invoice_id=? ORDER BY bil.id""",
            (invoice_id,),
        )
    )
    result["events"] = rows(
        db.execute(
            """SELECT bie.event_type,bie.from_status,bie.to_status,bie.detail,bie.created_at,
                      u.first_name actor_first,u.last_name actor_last
               FROM billing_invoice_events bie LEFT JOIN users u ON u.id=bie.created_by
               WHERE bie.invoice_id=? ORDER BY bie.created_at,bie.id""",
            (invoice_id,),
        )
    )
    return result


def cents_from_xero(value: Any) -> int:
    try:
        return max(0, int(round(float(value or 0) * 100)))
    except (TypeError, ValueError):
        return 0


def reconcile_xero_amounts(invoice: sqlite3.Row, xero_invoice: dict[str, Any]) -> tuple[int, int]:
    """Reject provider amounts that cannot safely fit the reviewed local ledger."""
    local_total = int(invoice["total_cents"])
    if xero_invoice.get("Total") is not None:
        provider_total = cents_from_xero(xero_invoice.get("Total"))
        if provider_total != local_total:
            raise RuntimeError("Xero invoice total does not match the approved local invoice")
    amount_paid = cents_from_xero(xero_invoice.get("AmountPaid"))
    amount_due = cents_from_xero(xero_invoice.get("AmountDue"))
    if amount_paid > local_total or amount_due > local_total or amount_paid + amount_due > local_total:
        raise RuntimeError("Xero payment totals exceed the approved local invoice")
    xero_status = str(xero_invoice.get("Status") or "").upper()
    if xero_status == "PAID" and (amount_paid != local_total or amount_due != 0):
        raise RuntimeError("Xero marked the invoice paid without a matching paid balance")
    return amount_paid, amount_due


async def refresh_and_store_xero_token(token: dict[str, Any]) -> dict[str, Any]:
    """Persist a rotated Xero refresh token before the next accounting API call."""
    current = await xero_token_valid(token)
    if current != token:
        with db_session() as db:
            db.execute(
                "UPDATE integration_connections SET encrypted_tokens=?,updated_at=? WHERE provider='xero'",
                (encrypt_json(current), now_iso()),
            )
    return current


def validate_class_occurrence(db: sqlite3.Connection, class_row: sqlite3.Row, occurrence: date) -> sqlite3.Row:
    term = term_for_date(db, occurrence)
    if not term:
        raise HTTPException(status_code=409, detail="This date is not inside a published school term")
    if occurrence.weekday() != class_row["weekday"]:
        raise HTTPException(status_code=422, detail="The selected date does not match this class day")
    return term


def certificate_reference(db: sqlite3.Connection) -> str:
    """Create a short, non-sequential certificate reference without exposing record IDs."""
    for _ in range(10):
        fragment = "".join(character for character in new_token(9).upper() if character.isalnum())[:10]
        if len(fragment) < 8:
            continue
        reference = f"HV-ACH-{business_today().year}-{fragment}"
        if not db.execute(
            "SELECT 1 FROM swimmer_achievements WHERE certificate_reference=?", (reference,)
        ).fetchone():
            return reference
    raise HTTPException(status_code=503, detail="A certificate reference could not be created; try again")


def incident_reference(db: sqlite3.Connection) -> str:
    for _ in range(10):
        fragment = "".join(character for character in new_token(8).upper() if character.isalnum())[:8]
        reference = f"HVS-INC-{business_today().year}-{fragment}"
        if len(fragment) == 8 and not db.execute(
            "SELECT 1 FROM incident_reports WHERE reference=?", (reference,)
        ).fetchone():
            return reference
    raise HTTPException(status_code=503, detail="An incident reference could not be created; try again")


def incident_payloads(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    payload = rows(cursor)
    for record in payload:
        for field_name in (*INCIDENT_SENSITIVE_FIELDS, "manager_review"):
            if field_name in record:
                record[field_name] = decrypt_sensitive(record[field_name]) or ""
        record["parent_notified"] = bool(record["parent_notified"])
        if "emergency_services" in record:
            record["emergency_services"] = bool(record["emergency_services"])
    return payload


def skill_progress_rows(db: sqlite3.Connection, user: dict[str, Any]) -> list[dict[str, Any]]:
    if user["role"] == "customer":
        permitted = [row["id"] for row in db.execute("SELECT id FROM swimmers WHERE customer_id=? AND active=1", (user["id"],))]
    else:
        permitted = sorted({row["swimmer_id"] for row in eligible_achievement_swimmers(db, user)})
    if not permitted:
        return []
    placeholders = ",".join("?" for _ in permitted)
    result = rows(db.execute(
        f"""SELECT p.*,s.first_name swimmer_first,s.last_name swimmer_last,s.level,
                   TRIM(u.first_name || ' ' || u.last_name) instructor_name
            FROM swimmer_skill_updates p JOIN swimmers s ON s.id=p.swimmer_id
            JOIN users u ON u.id=p.recorded_by
            WHERE p.swimmer_id IN ({placeholders}) AND p.id IN
              (SELECT MAX(id) FROM swimmer_skill_updates GROUP BY swimmer_id,LOWER(skill_name))
            ORDER BY s.first_name,s.last_name,p.skill_name""", tuple(permitted)))
    for record in result:
        record["feedback"] = decrypt_sensitive(record["feedback"])
        record["next_step"] = decrypt_sensitive(record["next_step"])
    return result


def achievement_template_rows(db: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows(
        db.execute(
            """SELECT code,title,description,certificate_style,badge_symbol,brand_label,sort_order
               FROM achievement_templates WHERE active=1 ORDER BY sort_order,title"""
        )
    )


def eligible_achievement_swimmers(db: sqlite3.Connection, user: dict[str, Any]) -> list[dict[str, Any]]:
    base_fields = """s.id swimmer_id,s.first_name swimmer_first,s.last_name swimmer_last,s.level,
                     c.id class_id,c.code class_code,c.title class_title"""
    if user["role"] == "admin":
        query = f"""SELECT {base_fields}
                    FROM swimmers s
                    LEFT JOIN bookings b ON b.swimmer_id=s.id AND b.status='confirmed'
                    LEFT JOIN classes c ON c.id=b.class_id
                    WHERE s.active=1
                    ORDER BY s.first_name,s.last_name,c.title"""
        return rows(db.execute(query))
    query = f"""SELECT DISTINCT {base_fields}
                FROM swimmers s
                JOIN bookings b ON b.swimmer_id=s.id AND b.status='confirmed'
                JOIN classes c ON c.id=b.class_id AND c.instructor_id=?
                WHERE s.active=1
                ORDER BY s.first_name,s.last_name,c.title"""
    return rows(db.execute(query, (user["id"],)))


def reveal_swimmer_record(record: dict[str, Any]) -> dict[str, Any]:
    """Decrypt only after the caller's family/staff/management authorisation has passed."""
    for field in SWIMMER_SENSITIVE_FIELDS:
        if field in record:
            record[field] = decrypt_sensitive(record.get(field))
    return record


def protect_swimmer_fields(values: dict[str, str]) -> dict[str, str | None]:
    return {field: encrypt_sensitive(values.get(field, "").strip()) for field in SWIMMER_SENSITIVE_FIELDS}


def staff_achievement_rows(db: sqlite3.Connection, user: dict[str, Any]) -> list[dict[str, Any]]:
    where = "1=1"
    params: tuple[Any, ...] = ()
    if user["role"] == "staff":
        where = """(a.awarded_by=? OR EXISTS (
                     SELECT 1 FROM bookings eligible_booking
                     JOIN classes eligible_class ON eligible_class.id=eligible_booking.class_id
                     WHERE eligible_booking.swimmer_id=a.swimmer_id
                       AND eligible_booking.status='confirmed' AND eligible_class.instructor_id=?
                   ))"""
        params = (user["id"], user["id"])
    query = f"""SELECT a.id,a.certificate_reference,a.certificate_style,a.evidence_note,a.private_staff_note,
                       a.status,a.awarded_by,a.awarded_at,a.revoked_by,a.revoked_at,a.revocation_reason,
                       t.code template_code,t.title template_title,t.description template_description,
                       t.badge_symbol,t.brand_label,s.id swimmer_id,s.first_name swimmer_first,
                       s.last_name swimmer_last,s.level,c.id class_id,c.code class_code,c.title class_title,
                       TRIM(awarder.first_name || ' ' || awarder.last_name) awarded_by_name,
                       TRIM(COALESCE(revoker.first_name,'') || ' ' || COALESCE(revoker.last_name,'')) revoked_by_name
                FROM swimmer_achievements a
                JOIN achievement_templates t ON t.id=a.template_id
                JOIN swimmers s ON s.id=a.swimmer_id
                LEFT JOIN classes c ON c.id=a.class_id
                JOIN users awarder ON awarder.id=a.awarded_by
                LEFT JOIN users revoker ON revoker.id=a.revoked_by
                WHERE {where}
                ORDER BY a.awarded_at DESC,a.id DESC"""
    return rows(db.execute(query, params))


def support_ticket_reference(db: sqlite3.Connection) -> str:
    for _ in range(10):
        fragment = "".join(character for character in new_token(9).upper() if character.isalnum())[:10]
        if len(fragment) < 8:
            continue
        reference = f"HV-TKT-{business_today().year}-{fragment}"
        if not db.execute("SELECT 1 FROM support_tickets WHERE reference=?", (reference,)).fetchone():
            return reference
    raise HTTPException(status_code=503, detail="A support reference could not be created; try again")


def optional_customer_session(db: sqlite3.Connection, request: Request) -> sqlite3.Row | None:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        return None
    return db.execute(
        """SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
           WHERE s.id=? AND s.expires_at>? AND u.active=1 AND u.role='customer'""",
        (token_digest(session_id), now_iso()),
    ).fetchone()


def support_messages(db: sqlite3.Connection, ticket_id: int, *, include_internal: bool) -> list[dict[str, Any]]:
    visibility_clause = "" if include_internal else "AND m.visibility='customer'"
    records = rows(
        db.execute(
            f"""SELECT m.id,m.author_user_id,m.author_role,m.message,m.visibility,m.created_at,
                       TRIM(COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'')) author_name
                FROM support_messages m LEFT JOIN users u ON u.id=m.author_user_id
                WHERE m.ticket_id=? {visibility_clause}
                ORDER BY m.created_at,m.id""",
            (ticket_id,),
        )
    )
    if include_internal:
        return records
    for record in records:
        record["author_type"] = "team" if record["author_role"] in {"staff", "admin", "system"} else "customer"
        record["author_label"] = "HV Swim team" if record["author_type"] == "team" else "You"
        for private_field in ("author_user_id", "author_role", "author_name", "visibility"):
            record.pop(private_field, None)
    return records


def customer_support_tickets(db: sqlite3.Connection, user: dict[str, Any]) -> list[dict[str, Any]]:
    tickets = rows(
        db.execute(
            """SELECT t.id,t.reference,t.category,t.name,t.email,t.phone,t.subject,t.status,t.priority,
                      t.source,t.created_at,t.updated_at,t.resolved_at
               FROM support_tickets t
               WHERE t.customer_id=? OR (t.customer_id IS NULL AND LOWER(t.email)=LOWER(?))
               ORDER BY t.updated_at DESC,t.id DESC""",
            (user["id"], user["email"]),
        )
    )
    for ticket in tickets:
        ticket["messages"] = support_messages(db, ticket["id"], include_internal=False)
    return tickets


def staff_support_ticket(db: sqlite3.Connection, ticket_id: int) -> dict[str, Any] | None:
    record = db.execute(
        """SELECT t.*,TRIM(COALESCE(assigned.first_name,'') || ' ' || COALESCE(assigned.last_name,'')) assigned_name
           FROM support_tickets t LEFT JOIN users assigned ON assigned.id=t.assigned_to WHERE t.id=?""",
        (ticket_id,),
    ).fetchone()
    if not record:
        return None
    ticket = dict(record)
    ticket["messages"] = support_messages(db, ticket_id, include_internal=True)
    return ticket


def delivery_boundary(*, in_app_delivered: bool) -> dict[str, str]:
    return {
        "in_app": "delivered" if in_app_delivered else "not_available",
        "email": "not_implemented",
        "push": "not_implemented",
    }


def public_alert_record(db: sqlite3.Connection, alert_id: int) -> dict[str, Any] | None:
    record = db.execute(
        """SELECT a.id,a.severity,a.title,a.message,
                  COALESCE(l.name,'All HV Swim locations') location_name,a.published_at
           FROM public_alerts a LEFT JOIN locations l ON l.id=a.location_id WHERE a.id=?""",
        (alert_id,),
    ).fetchone()
    return dict(record) if record else None


def sync_pool_public_alert(
    db: sqlite3.Connection,
    *,
    location: sqlite3.Row,
    pool_status: str,
    note: str,
    actor_id: int,
    pool_reading_id: int,
    ip_address: str,
    changed_at: str,
) -> dict[str, Any] | None:
    if pool_status in {"closed", "changed"}:
        severity = "closure" if pool_status == "closed" else "change"
        title = f"{location['name']} {'closed' if pool_status == 'closed' else 'conditions changed'}"
        message = note or ("Lessons are currently paused. Check this alert again before travelling." if pool_status == "closed" else "Pool conditions have changed. Check the latest lesson information before travelling.")
        existing = db.execute(
            """SELECT id FROM public_alerts
               WHERE location_id=? AND source='pool_status' AND status='active'
                 AND severity IN ('closure','change') ORDER BY updated_at DESC LIMIT 1""",
            (location["id"],),
        ).fetchone()
        # A new closure supersedes a previous reopening notice for this location.
        reopening_ids = [row["id"] for row in db.execute(
            """SELECT id FROM public_alerts WHERE location_id=? AND source='pool_status'
               AND status='active' AND severity='reopening'""",
            (location["id"],),
        )]
        for alert_id in reopening_ids:
            db.execute(
                """UPDATE public_alerts SET status='resolved',resolved_by=?,resolved_at=?,resolution_note=?,updated_by=?,updated_at=?
                   WHERE id=?""",
                (actor_id, changed_at, "Superseded by a new pool condition update", actor_id, changed_at, alert_id),
            )
        if existing:
            alert_id = existing["id"]
            db.execute(
                """UPDATE public_alerts SET severity=?,title=?,message=?,published_at=?,updated_by=?,updated_at=?
                   WHERE id=?""",
                (severity, title, message, changed_at, actor_id, changed_at, alert_id),
            )
            operation = "updated"
        else:
            alert_id = db.execute(
                """INSERT INTO public_alerts
                   (severity,title,message,location_id,status,source,published_by,published_at,updated_by,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (severity, title, message, location["id"], "active", "pool_status", actor_id, changed_at, actor_id, changed_at),
            ).lastrowid
            operation = "created"
        audit(
            db, actor_id, "sync_pool_public_alert", "public_alert", alert_id,
            {
                "operation": operation, "location_id": location["id"], "severity": severity,
                "pool_reading_id": pool_reading_id, "resolved_reopening_ids": reopening_ids,
            },
            ip_address,
        )
        return public_alert_record(db, alert_id)

    active_condition_ids = [row["id"] for row in db.execute(
        """SELECT id FROM public_alerts WHERE location_id=? AND source='pool_status'
           AND status='active' AND severity IN ('closure','change')""",
        (location["id"],),
    )]
    if not active_condition_ids:
        return None
    for alert_id in active_condition_ids:
        db.execute(
            """UPDATE public_alerts SET status='resolved',resolved_by=?,resolved_at=?,resolution_note=?,updated_by=?,updated_at=?
               WHERE id=?""",
            (actor_id, changed_at, "Pool status verified open", actor_id, changed_at, alert_id),
        )
    reopening = db.execute(
        """SELECT id FROM public_alerts WHERE location_id=? AND source='pool_status'
           AND status='active' AND severity='reopening' ORDER BY updated_at DESC LIMIT 1""",
        (location["id"],),
    ).fetchone()
    reopening_title = f"{location['name']} reopened"
    reopening_message = note or "The pool is open and lessons can resume. Check your usual booking details before travelling."
    if reopening:
        reopening_id = reopening["id"]
        db.execute(
            """UPDATE public_alerts SET title=?,message=?,published_at=?,updated_by=?,updated_at=? WHERE id=?""",
            (reopening_title, reopening_message, changed_at, actor_id, changed_at, reopening_id),
        )
    else:
        reopening_id = db.execute(
            """INSERT INTO public_alerts
               (severity,title,message,location_id,status,source,published_by,published_at,updated_by,updated_at)
               VALUES('reopening',?,?,?,'active','pool_status',?,?,?,?)""",
            (reopening_title, reopening_message, location["id"], actor_id, changed_at, actor_id, changed_at),
        ).lastrowid
    audit(
        db, actor_id, "reopen_pool_public_alert", "public_alert", reopening_id,
        {"resolved_alert_ids": active_condition_ids, "location_id": location["id"], "pool_reading_id": pool_reading_id},
        ip_address,
    )
    return public_alert_record(db, reopening_id)


def integration_summary(db: sqlite3.Connection) -> list[dict[str, Any]]:
    output = []
    configuration = {
        "xero": {
            "configured": xero_ready(),
            "oauth_implemented": True,
            "payroll_transmission_implemented": False,
            "transmission_locked": True,
            "description": "Existing Xero organisation · secure OAuth connection and payroll-readiness preview",
        },
        "shopify": {"configured": shopify_ready(), "description": "Storefront catalogue, cart and checkout"},
        "weather": {"configured": weather_ready(), "implemented": True, "description": "Cached Bendigo conditions · commercial key required in production"},
        "printify": {"configured": printify_ready(), "description": "POD products, mockups and Shopify fulfilment"},
        "vistaprint": {"configured": False, "description": "Manual uniforms and promotional-product supplier workflow"},
        "email": {"configured": False, "credentials_present": bool(settings.email_provider and settings.email_api_key), "implemented": False, "description": "Provider adapter required; in-app notices work now"},
        "sms": {"configured": False, "credentials_present": bool(settings.sms_provider and settings.sms_api_key), "implemented": False, "description": "Provider adapter required; in-app notices work now"},
        "web_push": {"configured": False, "credentials_present": bool(settings.web_push_public_key and settings.web_push_private_key), "implemented": False, "description": "Push adapter and consent flow required; in-app notices work now"},
        "pool_sensor": {"configured": bool(settings.pool_sensor_url), "implemented": bool(settings.pool_sensor_url), "description": "Optional sensor connectivity probe; staff publication remains authoritative"},
    }
    for row in db.execute("SELECT provider,status,metadata,updated_at FROM integration_connections ORDER BY provider"):
        item = dict(row)
        item.update(configuration.get(row["provider"], {"configured": False, "description": ""}))
        item["metadata"] = json.loads(item["metadata"] or "{}")
        output.append(item)
    return output


def site_settings_payload(db: sqlite3.Connection) -> dict[str, Any]:
    settings_rows = {row["key"]: row["value"] for row in db.execute("SELECT key,value FROM site_settings")}
    settings_rows["announcement_enabled"] = settings_rows.get("announcement_enabled") == "1"
    settings_rows["feature_merch_home"] = settings_rows.get("feature_merch_home") == "1"
    settings_rows["feature_association_badges"] = settings_rows.get("feature_association_badges") == "1"
    return settings_rows


ASSOCIATION_BADGE_DIR = DATA_DIR / "association-badges"
ASSOCIATION_BADGE_KEYS = {"swim_schools_australia", "austswim", "autism_swim"}
QUALIFICATION_DOCUMENT_DIR = DATA_DIR / "staff-qualification-documents"
QUALIFICATION_DOCUMENT_TYPES = {
    "application/pdf": (".pdf", b"%PDF-"),
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
    "image/webp": (".webp", b"RIFF"),
}
MAX_QUALIFICATION_DOCUMENT_BYTES = 5_000_000
MAX_QUALIFICATION_BASE64_LENGTH = 4 * ((MAX_QUALIFICATION_DOCUMENT_BYTES + 2) // 3)


def validate_qualification_document(encoded: str, media_type: str) -> tuple[bytes, str, str]:
    if len(encoded) > MAX_QUALIFICATION_BASE64_LENGTH:
        raise HTTPException(status_code=413, detail="Certificate document must be no larger than 5 MB")
    try:
        document = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(status_code=422, detail="Certificate document is not valid base64 data") from exc
    if not (32 <= len(document) <= MAX_QUALIFICATION_DOCUMENT_BYTES):
        raise HTTPException(status_code=413, detail="Certificate document must be between 32 bytes and 5 MB")
    extension, signature = QUALIFICATION_DOCUMENT_TYPES[media_type]
    if not document.startswith(signature):
        raise HTTPException(status_code=422, detail="Certificate file content does not match its selected type")
    if media_type == "application/pdf" and b"%%EOF" not in document[-4096:]:
        raise HTTPException(status_code=422, detail="Certificate PDF appears incomplete")
    if media_type == "image/jpeg" and not document.endswith(b"\xff\xd9"):
        raise HTTPException(status_code=422, detail="Certificate JPEG appears incomplete")
    if media_type == "image/png" and b"IEND" not in document[-32:]:
        raise HTTPException(status_code=422, detail="Certificate PNG appears incomplete")
    if media_type == "image/webp" and (len(document) < 12 or document[8:12] != b"WEBP"):
        raise HTTPException(status_code=422, detail="Certificate WebP appears invalid")
    return document, extension, hashlib.sha256(document).hexdigest()


def qualification_document_path(filename: str | None) -> Path | None:
    if not filename or Path(filename).name != filename:
        return None
    return QUALIFICATION_DOCUMENT_DIR / filename


def qualification_records(db: sqlite3.Connection, user: dict[str, Any]) -> list[dict[str, Any]]:
    where, params = ("q.staff_id=?", (user["id"],)) if user["role"] == "staff" else ("1=1", ())
    records = rows(db.execute(
        f"""SELECT q.*,u.first_name,u.last_name FROM qualifications q
            JOIN users u ON u.id=q.staff_id WHERE {where}
            ORDER BY q.expiry_date,q.qualification_type""",
        params,
    ))
    today = business_today()
    for record in records:
        expiry = date.fromisoformat(record["expiry_date"])
        remaining = (expiry - today).days
        status_value = "expired" if remaining < 0 else "expiring" if remaining <= int(record["reminder_days"] or 60) else "current"
        if record["status"] != status_value:
            db.execute("UPDATE qualifications SET status=? WHERE id=?", (status_value, record["id"]))
        record["status"] = status_value
        record["days_remaining"] = remaining
        document_path = qualification_document_path(record.get("document_filename"))
        document_available = bool(
            document_path
            and document_path.is_file()
            and record.get("document_sha256")
            and hashlib.sha256(document_path.read_bytes()).hexdigest() == record["document_sha256"]
        )
        record["document_available"] = document_available
        record["document_url"] = f"/api/staff/qualifications/{record['id']}/document" if document_available else None
        if remaining <= int(record["reminder_days"] or 60):
            dispatched = db.execute(
                """INSERT OR IGNORE INTO qualification_reminder_dispatches
                   (qualification_id,expiry_date,created_at) VALUES(?,?,?)""",
                (record["id"], record["expiry_date"], now_iso()),
            )
            if dispatched.rowcount:
                when = f"expired {abs(remaining)} days ago" if remaining < 0 else f"expires in {remaining} days"
                message = f"{record['qualification_type']} {when} on {record['expiry_date']}. Upload the renewed certificate or licence as soon as it is issued."
                db.execute(
                    """INSERT INTO notifications(user_id,title,message,kind,delivery_channels,created_at)
                       VALUES(?,?,?,?,?,?)""",
                    (record["staff_id"], "Certificate renewal required", message, "compliance", '["in_app"]', now_iso()),
                )
                db.execute(
                    """INSERT INTO notifications(audience_role,title,message,kind,delivery_channels,created_at)
                       VALUES(?,?,?,?,?,?)""",
                    ("admin", f"{record['first_name']} · certificate renewal", message, "compliance", '["in_app"]', now_iso()),
                )
    return records


def validate_association_png(encoded: str) -> tuple[bytes, int, int, str]:
    """Decode and structurally validate a modest, browser-safe PNG badge file."""
    try:
        artwork = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(status_code=422, detail="Artwork must be a valid base64-encoded PNG file") from exc
    if len(artwork) > 1_000_000:
        raise HTTPException(status_code=413, detail="Badge artwork must be no larger than 1 MB")
    if len(artwork) < 45 or artwork[:8] != b"\x89PNG\r\n\x1a\n":
        raise HTTPException(status_code=422, detail="Only genuine PNG badge artwork is accepted")

    position = 8
    width = height = 0
    seen_idat = seen_iend = False
    chunk_index = 0
    while position + 12 <= len(artwork):
        length = int.from_bytes(artwork[position:position + 4], "big")
        chunk_type = artwork[position + 4:position + 8]
        chunk_end = position + 12 + length
        if length > 1_000_000 or chunk_end > len(artwork):
            raise HTTPException(status_code=422, detail="PNG artwork is incomplete or malformed")
        chunk_data = artwork[position + 8:position + 8 + length]
        supplied_crc = int.from_bytes(artwork[position + 8 + length:chunk_end], "big")
        if (binascii.crc32(chunk_type + chunk_data) & 0xFFFFFFFF) != supplied_crc:
            raise HTTPException(status_code=422, detail="PNG artwork failed its integrity check")
        if chunk_index == 0:
            if chunk_type != b"IHDR" or length != 13:
                raise HTTPException(status_code=422, detail="PNG artwork has an invalid header")
            width = int.from_bytes(chunk_data[:4], "big")
            height = int.from_bytes(chunk_data[4:8], "big")
            if not (64 <= width <= 2400 and 64 <= height <= 2400) or width * height > 4_000_000:
                raise HTTPException(status_code=422, detail="Badge artwork dimensions must be between 64 and 2400 pixels")
            if chunk_data[10] != 0 or chunk_data[11] != 0 or chunk_data[12] not in (0, 1):
                raise HTTPException(status_code=422, detail="PNG artwork uses unsupported encoding settings")
        elif chunk_type == b"IHDR":
            raise HTTPException(status_code=422, detail="PNG artwork contains more than one header")
        if chunk_type == b"IDAT":
            seen_idat = True
        if chunk_type == b"IEND":
            if length != 0 or chunk_end != len(artwork):
                raise HTTPException(status_code=422, detail="PNG artwork has an invalid ending")
            seen_iend = True
            break
        position = chunk_end
        chunk_index += 1
    if not seen_idat or not seen_iend:
        raise HTTPException(status_code=422, detail="PNG artwork is missing required image data")
    return artwork, width, height, hashlib.sha256(artwork).hexdigest()


def association_artwork_path(filename: str | None) -> Path | None:
    if not filename or Path(filename).name != filename:
        return None
    return ASSOCIATION_BADGE_DIR / filename


def association_badge_records(db: sqlite3.Connection) -> list[dict[str, Any]]:
    records = rows(
        db.execute(
            """SELECT c.*,u.first_name verifier_first,u.last_name verifier_last
               FROM association_credentials c
               LEFT JOIN users u ON u.id=c.verified_by
               ORDER BY CASE c.key
                   WHEN 'swim_schools_australia' THEN 1
                   WHEN 'austswim' THEN 2 ELSE 3 END"""
        )
    )
    today = business_today().isoformat()
    for record in records:
        blockers: list[str] = []
        if not (record.get("membership_reference") or "").strip():
            blockers.append("Membership or certification reference required")
        if not record.get("valid_until"):
            blockers.append("Renewal or valid-until date required")
        elif record["valid_until"] < today:
            blockers.append("Evidence has expired")
        if not record.get("usage_rights_confirmed"):
            blockers.append("Logo usage rights must be confirmed")
        artwork_path = association_artwork_path(record.get("artwork_filename"))
        artwork_available = False
        if artwork_path and artwork_path.is_file() and record.get("artwork_sha256"):
            try:
                artwork_available = hashlib.sha256(artwork_path.read_bytes()).hexdigest() == record["artwork_sha256"]
            except OSError:
                artwork_available = False
        if not artwork_available:
            blockers.append("Current issued PNG artwork required")
        if not record.get("verified_by") or not record.get("verified_at"):
            blockers.append("Management verification required")
        record["usage_rights_confirmed"] = bool(record.get("usage_rights_confirmed"))
        record["artwork_available"] = artwork_available
        record["ready"] = not blockers
        record["blocking_reasons"] = blockers
        record["artwork_url"] = (
            f"/api/public/association-badges/{record['key']}/artwork.png?v={record['artwork_sha256'][:16]}"
            if artwork_available else None
        )
    return records


def public_feature_controls(db: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """Report requested and effective public features with their production launch gates."""
    raw = {row["key"]: row["value"] for row in db.execute("SELECT key,value FROM site_settings")}
    catalogue = rows(
        db.execute(
            """SELECT id,price_cents,cost_cents,status,sample_status,sizes,supplier_route,
                      shopify_gid,printify_product_id,supplier_reference
               FROM products"""
        )
    )
    public_ready_products = sum(
        1 for product in catalogue
        if product.get("status") == "available" and not product_launch_blockers(product)
    )
    merch_requested = raw.get("feature_merch_home") == "1"
    badge_requested = raw.get("feature_association_badges") == "1"
    badges = association_badge_records(db)
    ready_badges = sum(1 for badge in badges if badge["ready"])
    badges_ready = len(badges) == len(ASSOCIATION_BADGE_KEYS) and ready_badges == len(badges)
    merch_ready = public_ready_products > 0

    return {
        "merch_home": {
            "requested": merch_requested,
            "effective_enabled": merch_requested and merch_ready,
            "can_enable": merch_ready,
            "ready_items": public_ready_products,
            "reason": (
                f"{public_ready_products} sampled, costed and mapped product{'s' if public_ready_products != 1 else ''} ready for publication."
                if merch_ready
                else "No product has passed the physical-sample, cost, supplier and Shopify mapping gates."
            ),
        },
        "association_badges": {
            "requested": badge_requested,
            "effective_enabled": badge_requested and badges_ready,
            "can_enable": badges_ready,
            "ready_items": ready_badges,
            "reason": (
                "All three issued badges have current evidence, verified usage rights and integrity-checked artwork."
                if badges_ready
                else f"{ready_badges} of 3 marks ready. Current issued badge files, renewal evidence and recorded usage rights are still required."
            ),
        },
    }


def csv_download(filename: str, headings: list[str], records: list[list[Any]]) -> Response:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headings)
    for record in records:
        safe = []
        for value in record:
            text = "" if value is None else str(value)
            safe.append("'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text)
        writer.writerow(safe)
    return Response(output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def renumber_waitlist(db: sqlite3.Connection, class_id: int) -> None:
    for position, row in enumerate(db.execute("SELECT id FROM waitlist WHERE class_id=? AND status='waiting' ORDER BY position,created_at", (class_id,)), start=1):
        db.execute("UPDATE waitlist SET position=? WHERE id=?", (position, row["id"]))


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "HV Swim Bendigo", "version": "5.13.0", "environment": settings.app_env, "time": now_iso()}


@app.get("/api/admin/system-health")
def admin_system_health(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    """Protected operational readiness without exposing paths, secrets or customer data."""
    with db_session() as db:
        quick_check = [row[0] for row in db.execute("PRAGMA quick_check")]
        foreign_key_violations = list(db.execute("PRAGMA foreign_key_check"))
        journal_mode = str(db.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        billing_mismatches = db.execute(
            """SELECT COUNT(*) FROM billing_invoices bi
               WHERE bi.total_cents != COALESCE(
                 (SELECT SUM(bil.line_amount_cents) FROM billing_invoice_lines bil WHERE bil.invoice_id=bi.id),0
               )"""
        ).fetchone()[0]
        legacy_token_count = sum(
            not integration_token_encryption_current(row[0])
            for row in db.execute(
                "SELECT encrypted_tokens FROM integration_connections WHERE encrypted_tokens IS NOT NULL"
            )
        )
        connections = {
            row["provider"]: row["status"]
            for row in db.execute("SELECT provider,status FROM integration_connections")
        }
    database_ok = quick_check == ["ok"] and not foreign_key_violations and billing_mismatches == 0
    return {
        "ok": database_ok and legacy_token_count == 0,
        "checked_at": now_iso(),
        "release": app.version,
        "database": {
            "integrity": "ok" if quick_check == ["ok"] else "review_required",
            "foreign_key_violations": len(foreign_key_violations),
            "billing_total_mismatches": int(billing_mismatches),
            "journal_mode": journal_mode,
        },
        "security": {
            "integration_token_encryption": "current" if legacy_token_count == 0 else "migration_required",
            "legacy_integration_token_records": legacy_token_count,
            "production_separate_data_key": bool(settings.production and settings.data_encryption_key),
        },
        "integrations": {
            "xero": {
                "connection": connections.get("xero", "not_connected"),
                "invoice_configuration_ready": xero_invoice_configuration_ready(),
                "outbound_enabled": settings.xero_sync_enabled,
            },
            "shopify": {
                "connection": connections.get("shopify", "not_connected"),
                "storefront_configured": shopify_ready(),
            },
            "weather": {"commercial_configuration_ready": bool(settings.weather_api_key)},
            "pool_sensor": {"configured": bool(settings.pool_sensor_url)},
        },
    }


@app.get("/api/public/site-settings")
def public_site_settings() -> dict[str, Any]:
    with db_session() as db:
        public_settings = site_settings_payload(db)
        controls = public_feature_controls(db)
        public_settings.pop("feature_merch_home", None)
        public_settings.pop("feature_association_badges", None)
        features = {key: bool(value["effective_enabled"]) for key, value in controls.items()}
        return {
            "settings": public_settings,
            "mode": "production" if settings.production else "preview",
            "features": features,
        }


@app.get("/api/public/association-badges")
def public_association_badges() -> dict[str, Any]:
    with db_session() as db:
        controls = public_feature_controls(db)
        if not controls["association_badges"]["effective_enabled"]:
            return {"badges": [], "published": False}
        badges = []
        for record in association_badge_records(db):
            if not record["ready"]:
                continue
            badges.append(
                {
                    "key": record["key"],
                    "display_name": record["display_name"],
                    "short_label": record["short_label"],
                    "directory_url": record["directory_url"],
                    "valid_until": record["valid_until"],
                    "artwork_url": record["artwork_url"],
                }
            )
        return {"badges": badges, "published": len(badges) == len(ASSOCIATION_BADGE_KEYS)}


@app.get("/api/public/association-badges/{credential_key}/artwork.png")
def public_association_badge_artwork(credential_key: str) -> FileResponse:
    with db_session() as db:
        if not public_feature_controls(db)["association_badges"]["effective_enabled"]:
            raise HTTPException(status_code=404)
        record = next((item for item in association_badge_records(db) if item["key"] == credential_key), None)
        if not record or not record["ready"]:
            raise HTTPException(status_code=404)
        artwork_path = association_artwork_path(record["artwork_filename"])
        if not artwork_path or not artwork_path.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(artwork_path, media_type="image/png")


def oauth_error_redirect(code: str) -> RedirectResponse:
    return RedirectResponse(url=f"/login.html?oauth_error={quote(code, safe='')}", status_code=303)


def safe_oauth_name(value: Any, fallback: str) -> str:
    cleaned = " ".join(str(value or "").strip().split())
    return (cleaned or fallback)[:80]


async def complete_oauth_login(
    provider: str,
    *,
    state: str,
    code: str,
    request: Request,
    supplied_profile: dict[str, Any] | None = None,
) -> RedirectResponse:
    if provider not in {"google", "apple"} or not state or not code:
        return oauth_error_redirect("invalid_response")
    state_digest = hashlib.sha256(state.encode("utf-8")).hexdigest()
    with db_session() as db:
        db.execute("DELETE FROM oauth_login_attempts WHERE expires_at<=?", (now_iso(),))
        attempt = db.execute(
            "SELECT * FROM oauth_login_attempts WHERE state_hash=? AND provider=? AND expires_at>?",
            (state_digest, provider, now_iso()),
        ).fetchone()
        if not attempt:
            return oauth_error_redirect("expired_or_invalid")
        # Consume the state before contacting the provider. A transient failure requires a
        # fresh attempt rather than making the same authorisation code replayable.
        db.execute("DELETE FROM oauth_login_attempts WHERE state_hash=?", (state_digest,))
        code_verifier, nonce = attempt["code_verifier"], attempt["nonce"]
    try:
        token_payload = await oauth_exchange_code(provider, code=code, code_verifier=code_verifier)
        claims = await asyncio.to_thread(
            oauth_verify_identity_token,
            provider,
            token_payload["id_token"],
            nonce=nonce,
        )
    except OAuthProviderError:
        return oauth_error_redirect("provider_failed")

    subject = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip().lower()
    if not subject or not email or len(email) > 254:
        return oauth_error_redirect("verified_email_required")
    provider_profile = supplied_profile or {}
    profile_name = provider_profile.get("name") if isinstance(provider_profile.get("name"), dict) else {}
    local_name = email.split("@", 1)[0].replace(".", " ").replace("_", " ")
    first_name = safe_oauth_name(
        claims.get("given_name") or profile_name.get("firstName"),
        local_name.title() or "HV Swim Family",
    )
    last_name = safe_oauth_name(claims.get("family_name") or profile_name.get("lastName"), "")
    signed_in_at = now_iso()
    response = RedirectResponse(url="/platform.html?account=connected", status_code=303)
    with db_session() as db:
        identity = db.execute(
            "SELECT * FROM oauth_identities WHERE provider=? AND subject=?",
            (provider, subject),
        ).fetchone()
        created = False
        if identity:
            user = db.execute("SELECT * FROM users WHERE id=? AND active=1", (identity["user_id"],)).fetchone()
            if not user:
                return oauth_error_redirect("account_unavailable")
        else:
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if user and not user["active"]:
                return oauth_error_redirect("account_unavailable")
            if user and user["role"] != "customer":
                return oauth_error_redirect("team_account_requires_approval")
            if not user:
                cursor = db.execute(
                    """INSERT INTO users(
                           email,password_hash,role,first_name,last_name,must_change_password,created_at
                       ) VALUES(?,?,'customer',?,?,0,?)""",
                    (email, password_hash(new_token(48)), first_name, last_name, signed_in_at),
                )
                db.execute(
                    "UPDATE users SET customer_number=printf('HVS-%06d',id) WHERE id=?",
                    (cursor.lastrowid,),
                )
                user = db.execute("SELECT * FROM users WHERE id=?", (cursor.lastrowid,)).fetchone()
                created = True
            elif user["must_change_password"]:
                db.execute("UPDATE users SET must_change_password=0 WHERE id=?", (user["id"],))
                user = db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
            try:
                db.execute(
                    """INSERT INTO oauth_identities(
                           provider,subject,user_id,email,created_at,last_login_at
                       ) VALUES(?,?,?,?,?,?)""",
                    (provider, subject, user["id"], email, signed_in_at, signed_in_at),
                )
            except sqlite3.IntegrityError:
                return oauth_error_redirect("account_already_linked")
        db.execute(
            "UPDATE oauth_identities SET email=?,last_login_at=? WHERE provider=? AND subject=?",
            (email, signed_in_at, provider, subject),
        )
        action = "oauth_signup" if created else "oauth_login"
        issue_session(
            db,
            user,
            response,
            ip_address=client_ip(request),
            action=action,
            audit_detail={"provider": provider, "new_family_account": created},
        )
    return response


@app.get("/api/auth/oauth/providers")
def oauth_providers() -> dict[str, Any]:
    providers = oauth_provider_public_status()
    return {
        "providers": providers,
        "signup_role": "customer",
        "team_accounts": "invitation_only",
        "configured_count": sum(1 for item in providers if item["configured"]),
    }


@app.get("/api/auth/oauth/{provider}/start")
def start_oauth(provider: str, request: Request) -> RedirectResponse:
    if provider not in {"google", "apple"}:
        raise HTTPException(status_code=404, detail="Account provider not found")
    if not oauth_provider_ready(provider):
        raise HTTPException(status_code=503, detail=f"{provider.title()} account access is awaiting HV Swim configuration")
    state, nonce, code_verifier = new_token(32), new_token(32), new_token(48)
    created_at = datetime.now(timezone.utc)
    expires_at = (created_at + timedelta(minutes=OAUTH_ATTEMPT_MINUTES)).isoformat()
    ip_address = client_ip(request)
    with db_session() as db:
        db.execute("DELETE FROM oauth_login_attempts WHERE expires_at<=?", (created_at.isoformat(),))
        attempts = db.execute(
            "SELECT COUNT(*) FROM oauth_login_attempts WHERE ip_address=? AND created_at>?",
            (ip_address, (created_at - timedelta(minutes=OAUTH_ATTEMPT_MINUTES)).isoformat()),
        ).fetchone()[0]
        if attempts >= 30:
            raise HTTPException(status_code=429, detail="Too many account sign-in attempts. Try again shortly.")
        db.execute(
            """INSERT INTO oauth_login_attempts(
                   state_hash,provider,ip_address,code_verifier,nonce,created_at,expires_at
               ) VALUES(?,?,?,?,?,?,?)""",
            (
                hashlib.sha256(state.encode("utf-8")).hexdigest(),
                provider,
                ip_address,
                code_verifier,
                nonce,
                created_at.isoformat(),
                expires_at,
            ),
        )
    try:
        destination = oauth_authorization_url(
            provider,
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
        )
    except OAuthProviderError:
        raise HTTPException(status_code=503, detail="Account provider is not ready")
    return RedirectResponse(url=destination, status_code=302)


@app.get("/api/auth/oauth/google/callback")
async def google_oauth_callback(
    request: Request,
    state: str = "",
    code: str = "",
    error: str = "",
) -> RedirectResponse:
    if error:
        return oauth_error_redirect("cancelled" if error == "access_denied" else "provider_failed")
    return await complete_oauth_login("google", state=state, code=code, request=request)


@app.post("/api/auth/oauth/apple/callback")
async def apple_oauth_callback(request: Request) -> RedirectResponse:
    content_type = request.headers.get("content-type", "").lower()
    if not content_type.startswith("application/x-www-form-urlencoded"):
        raise HTTPException(status_code=415, detail="Apple callback must use form-encoded data")
    body = await request.body()
    if len(body) > 32_768:
        raise HTTPException(status_code=413, detail="Apple callback is too large")
    try:
        parsed = {key: values[0] for key, values in parse_qs(body.decode("utf-8"), keep_blank_values=True).items()}
    except UnicodeDecodeError:
        return oauth_error_redirect("invalid_response")
    if parsed.get("error"):
        return oauth_error_redirect("cancelled" if parsed["error"] == "user_cancelled_authorize" else "provider_failed")
    supplied_profile: dict[str, Any] = {}
    if parsed.get("user"):
        try:
            candidate = json.loads(parsed["user"])
            if isinstance(candidate, dict):
                supplied_profile = candidate
        except (TypeError, ValueError):
            supplied_profile = {}
    return await complete_oauth_login(
        "apple",
        state=parsed.get("state", ""),
        code=parsed.get("code", ""),
        request=request,
        supplied_profile=supplied_profile,
    )


@app.get("/api/demo-accounts")
def demo_accounts() -> dict[str, Any]:
    if settings.production:
        raise HTTPException(status_code=404)
    return {
        "accounts": [
            {"role": "Family", "email": "parent@hvswim.demo", "password": "FamilyDemo!26"},
            {"role": "Staff", "email": "staff@hvswim.demo", "password": "StaffDemo!26"},
            {"role": "Management", "email": "admin@hvswim.demo", "password": "AdminDemo!26"},
        ]
    }


@app.post("/api/auth/login")
def login(payload: LoginInput, request: Request, response: Response) -> dict[str, Any]:
    email = payload.email.lower().strip()
    if settings.production and email.endswith("@hvswim.demo"):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    ip = client_ip(request)
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    with db_session() as db:
        db.execute("DELETE FROM login_attempts WHERE created_at<=?", (login_attempt_cutoff(),))
        failures = db.execute("SELECT COUNT(*) FROM login_attempts WHERE email=? AND ip_address=? AND success=0 AND created_at>?", (email, ip, cutoff)).fetchone()[0]
        if failures >= 10:
            raise HTTPException(status_code=429, detail="Too many sign-in attempts. Try again in 15 minutes.")
        user = db.execute("SELECT * FROM users WHERE email=? AND active=1", (email,)).fetchone()
        success = bool(user and password_verify(payload.password, user["password_hash"]) and identity.verify_mfa(db, user, payload.code))
        db.execute("INSERT INTO login_attempts(email,ip_address,success,created_at) VALUES(?,?,?,?)", (email, ip, int(success), now_iso()))
        if not success:
            # The 401 is raised inside db_session(), whose exception path rolls back.
            # Commit the failed attempt first or the limiter never sees any failures.
            db.commit()
            raise HTTPException(status_code=401, detail="Sign-in details are incorrect. Check your authenticator code if enabled.")
        if password_needs_rehash(user["password_hash"]):
            refreshed_hash = password_hash(payload.password)
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (refreshed_hash, user["id"]))
        return issue_session(db, user, response, ip_address=ip, action="login")


@app.get("/api/auth/me")
def me(user: dict[str, Any] = Depends(session_user)) -> dict[str, Any]:
    return {"user": public_user(user), "csrf_token": user["csrf_token"]}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, user: dict[str, Any] = Depends(session_user), x_csrf_token: str | None = Header(default=None)) -> dict[str, bool]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute("DELETE FROM sessions WHERE id=?", (user["session_id"],))
        audit(db, user["id"], "logout", "session", user["session_id"][-8:], ip_address=client_ip(request))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@app.post("/api/auth/change-password")
def change_password(payload: ChangePasswordInput, request: Request, user: dict[str, Any] = Depends(session_user), x_csrf_token: str | None = Header(default=None)) -> dict[str, bool]:
    csrf_guard(request, user, x_csrf_token)
    identity.proof_attempt(user["id"])
    if hmac.compare_digest(payload.current_password, payload.new_password):
        raise HTTPException(status_code=422, detail="Choose a new password that is different from the current password")
    with db_session() as db:
        stored = db.execute("SELECT password_hash FROM users WHERE id=? AND active=1", (user["id"],)).fetchone()
        if not stored or not password_verify(payload.current_password, stored["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        db.execute(
            "UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?",
            (password_hash(payload.new_password), user["id"]),
        )
        db.execute("DELETE FROM sessions WHERE user_id=? AND id<>?", (user["id"], user["session_id"]))
        db.execute("UPDATE account_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL", (now_iso(), user["id"]))
        audit(db, user["id"], "change_password", "user", user["id"], ip_address=client_ip(request))
    return {"changed": True}


@app.get("/api/public/locations")
def public_locations() -> dict[str, Any]:
    with db_session() as db:
        term = public_term_context(db)
        today_weekday = business_today().weekday()
        output = []
        for location in db.execute("SELECT * FROM locations ORDER BY id"):
            reading = db.execute(
                """SELECT pr.*,u.first_name,u.last_name FROM pool_readings pr
                   LEFT JOIN users u ON u.id=pr.verified_by WHERE pr.location_id=? ORDER BY pr.created_at DESC LIMIT 1""",
                (location["id"],),
            ).fetchone()
            item = dict(location)
            item["latest_reading"] = dict(reading) if reading else None
            if reading:
                created = datetime.fromisoformat(reading["created_at"])
                item["reading_stale"] = datetime.now(timezone.utc) - created > timedelta(hours=24)
            else:
                item["reading_stale"] = True
            item["today_classes"] = rows(db.execute(
                """SELECT code,title,start_time,duration_minutes FROM classes
                   WHERE active=1 AND location_id=? AND weekday=? ORDER BY start_time""",
                (location["id"], today_weekday),
            )) if term["in_session"] and "closed" not in location["public_status"].lower() else []
            output.append(item)
        return {"locations": output, "term_calendar": term}


@app.get("/api/public/weather")
async def weather() -> dict[str, Any]:
    try:
        return await current_bendigo_weather()
    except Exception:
        raise HTTPException(status_code=503, detail="Live weather is temporarily unavailable")


@app.get("/api/public/alerts")
def public_alerts() -> dict[str, Any]:
    with db_session() as db:
        query = """SELECT a.id,a.severity,a.title,a.message,
                          COALESCE(l.name,'All HV Swim locations') location_name,a.published_at
                   FROM public_alerts a LEFT JOIN locations l ON l.id=a.location_id
                   WHERE a.status='active'
                   ORDER BY CASE a.severity WHEN 'closure' THEN 0 WHEN 'change' THEN 1 WHEN 'reopening' THEN 2 ELSE 3 END,
                            a.published_at DESC,a.id DESC"""
        return {"alerts": rows(db.execute(query)), "delivery": {"website_polling": "live", "push": "not_implemented"}}


@app.get("/api/classes")
def list_classes() -> dict[str, Any]:
    with db_session() as db:
        query = """SELECT c.*,l.name location_name,l.slug location_slug,u.first_name instructor_first,u.last_name instructor_last,
                   (SELECT COUNT(*) FROM bookings b WHERE b.class_id=c.id AND b.status='confirmed') enrolled
                   FROM classes c JOIN locations l ON l.id=c.location_id LEFT JOIN users u ON u.id=c.instructor_id
                   WHERE c.active=1 ORDER BY c.weekday,c.start_time"""
        output = []
        for row in db.execute(query):
            item = dict(row)
            item["available"] = max(0, item["capacity"] - item["enrolled"])
            item["price"] = item["price_cents"] / 100
            output.append(item)
        return {
            "classes": output,
            "term_calendar": public_term_context(db),
            "enrolment": {
                "mode": "enquiry_only",
                "url": "/enquire.html",
                "message": "Every new lesson enrolment starts with an enquiry and is confirmed personally by HV Swim.",
            },
            "payment": {
                "route": "xero_invoice_workflow",
                "status": "configuration_required",
                "message": "Term lesson charges are handled through the approved Xero invoicing workflow; no payment is taken by this class finder.",
            },
        }


@app.get("/api/customer/swimmers")
def customer_swimmers(user: dict[str, Any] = Depends(require_roles("customer", "admin"))) -> dict[str, Any]:
    with db_session() as db:
        if user["role"] == "customer":
            result = rows(db.execute("SELECT * FROM swimmers WHERE customer_id=? AND active=1 ORDER BY first_name", (user["id"],)))
        else:
            result = rows(db.execute("SELECT s.*,u.first_name parent_first,u.last_name parent_last FROM swimmers s JOIN users u ON u.id=s.customer_id WHERE s.active=1 ORDER BY s.first_name"))
        return {"swimmers": [reveal_swimmer_record(record) for record in result]}


@app.patch("/api/customer/swimmers/{swimmer_id}")
def update_family_swimmer_profile(
    swimmer_id: int,
    payload: FamilySwimmerProfileInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("customer")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        swimmer = db.execute(
            "SELECT id FROM swimmers WHERE id=? AND customer_id=? AND active=1",
            (swimmer_id, user["id"]),
        ).fetchone()
        if not swimmer:
            raise HTTPException(status_code=404, detail="Active swimmer profile not found")
        fields = protect_swimmer_fields({
            "emergency_contact": payload.emergency_contact.strip(),
            "medical_notes": payload.medical_notes.strip(),
            "allergies": payload.allergies.strip(),
            "medications": payload.medications.strip(),
            "support_notes": payload.support_notes.strip(),
        })
        db.execute(
            """UPDATE swimmers
               SET emergency_contact=?,medical_notes=?,allergies=?,medications=?,support_notes=?
               WHERE id=?""",
            (*fields.values(), swimmer_id),
        )
        # Medical and allergy text is deliberately excluded from the audit detail. The
        # event records only which profile sections changed.
        audit(
            db,
            user["id"],
            "update_family_swimmer_safety_profile",
            "swimmer",
            swimmer_id,
            {"updated_fields": list(fields.keys())},
            client_ip(request),
        )
        return {"saved": True, "swimmer_id": swimmer_id, "updated_fields": list(fields.keys())}


@app.get("/api/achievements/templates")
def achievement_templates(user: dict[str, Any] = Depends(session_user)) -> dict[str, Any]:
    with db_session() as db:
        return {
            "templates": achievement_template_rows(db),
            "brand": "HV Swim School Bendigo",
            "certificate_rendering": "html_print",
        }


@app.get("/api/customer/achievements")
def customer_achievements(user: dict[str, Any] = Depends(require_roles("customer"))) -> dict[str, Any]:
    with db_session() as db:
        query = """SELECT a.id,a.certificate_reference,a.certificate_style,a.evidence_note,a.status,
                          a.awarded_at,a.revoked_at,a.revocation_reason,t.code template_code,
                          t.title template_title,t.description template_description,t.badge_symbol,t.brand_label,
                          s.id swimmer_id,s.first_name swimmer_first,s.last_name swimmer_last,s.level,
                          c.id class_id,c.code class_code,c.title class_title,
                          TRIM(awarder.first_name || ' ' || awarder.last_name) awarded_by_name
                   FROM swimmer_achievements a
                   JOIN achievement_templates t ON t.id=a.template_id
                   JOIN swimmers s ON s.id=a.swimmer_id
                   LEFT JOIN classes c ON c.id=a.class_id
                   JOIN users awarder ON awarder.id=a.awarded_by
                   WHERE s.customer_id=?
                   ORDER BY a.awarded_at DESC,a.id DESC"""
        return {
            "achievements": rows(db.execute(query, (user["id"],))),
            "skill_progress": skill_progress_rows(db, user),
            "privacy": {
                "family_visible_evidence": True,
                "staff_notes_excluded": True,
            },
            "certificate_rendering": "html_print",
        }


SUPPORT_LIMIT_PER_HOUR = 4


@app.post("/api/public/support-tickets")
def create_public_support_ticket(payload: PublicSupportTicketInput, request: Request) -> dict[str, Any]:
    ip = client_ip(request)
    if payload.website.strip():
        return {
            "id": 0, "reference": "HV-TKT-RECEIVED", "received": True,
            "message": "Thanks — your message is with the HV Swim team.",
            "delivery": delivery_boundary(in_app_delivered=False),
        }
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        recent = db.execute(
            """SELECT COUNT(*) FROM audit_log
               WHERE action='create_public_support_ticket' AND ip_address=? AND created_at>?""",
            (ip, cutoff),
        ).fetchone()[0]
        if recent >= SUPPORT_LIMIT_PER_HOUR:
            raise HTTPException(
                status_code=429,
                detail="Several support messages have already been received from this connection. Please wait before trying again.",
            )
        account = optional_customer_session(db, request)
        email = str(payload.email).strip().lower()
        customer_id = account["id"] if account and account["email"].lower() == email else None
        created_at = now_iso()
        reference = support_ticket_reference(db)
        cursor = db.execute(
            """INSERT INTO support_tickets
               (reference,customer_id,category,name,email,phone,subject,status,priority,source,
                consent_acknowledged,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,'new','normal','public_widget',?,?,?)""",
            (
                reference, customer_id, payload.category, payload.name.strip(), email,
                payload.phone.strip() or None, payload.subject.strip(), int(payload.consent_acknowledged),
                created_at, created_at,
            ),
        )
        ticket_id = cursor.lastrowid
        db.execute(
            """INSERT INTO support_messages(ticket_id,author_user_id,author_role,message,visibility,created_at)
               VALUES(?,?,?,?,?,?)""",
            (ticket_id, customer_id, "customer" if customer_id else "guest", payload.message.strip(), "customer", created_at),
        )
        db.execute(
            """INSERT INTO notifications(audience_role,title,message,kind,delivery_channels,created_at)
               VALUES('admin',?,?, 'support','[\"in_app\"]',?)""",
            (f"New support ticket · {reference}", f"A new {payload.category.replace('_',' ')} support request is waiting in the queue.", created_at),
        )
        audit(
            db, customer_id, "create_public_support_ticket", "support_ticket", ticket_id,
            {"reference": reference, "category": payload.category, "source": "public_widget"}, ip,
        )
        return {
            "id": ticket_id, "reference": reference, "received": True,
            "message": "Thanks — your message is with the HV Swim team. Keep this reference for follow-up.",
            "delivery": delivery_boundary(in_app_delivered=True),
        }


@app.get("/api/support-tickets")
def list_customer_support_tickets(user: dict[str, Any] = Depends(require_roles("customer"))) -> dict[str, Any]:
    with db_session() as db:
        return {
            "tickets": customer_support_tickets(db, user),
            "delivery_boundary": {"email": "not_implemented", "push": "not_implemented"},
        }


@app.post("/api/support-tickets")
def create_customer_support_ticket(
    payload: CustomerSupportTicketInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("customer")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        created_at = now_iso()
        reference = support_ticket_reference(db)
        name = f"{user['first_name']} {user['last_name']}".strip()
        cursor = db.execute(
            """INSERT INTO support_tickets
               (reference,customer_id,category,name,email,phone,subject,status,priority,source,
                consent_acknowledged,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,'new','normal','customer_portal',1,?,?)""",
            (
                reference, user["id"], payload.category, name, user["email"].lower(),
                payload.phone.strip() or user.get("phone") or None, payload.subject.strip(), created_at, created_at,
            ),
        )
        ticket_id = cursor.lastrowid
        db.execute(
            """INSERT INTO support_messages(ticket_id,author_user_id,author_role,message,visibility,created_at)
               VALUES(?,?,'customer',?,'customer',?)""",
            (ticket_id, user["id"], payload.message.strip(), created_at),
        )
        db.execute(
            """INSERT INTO notifications(audience_role,title,message,kind,delivery_channels,created_at)
               VALUES('admin',?,?, 'support','[\"in_app\"]',?)""",
            (f"New account support ticket · {reference}", "A signed-in family sent a support request.", created_at),
        )
        audit(
            db, user["id"], "create_customer_support_ticket", "support_ticket", ticket_id,
            {"reference": reference, "category": payload.category, "source": "customer_portal"}, client_ip(request),
        )
        return {
            "id": ticket_id, "reference": reference, "created": True,
            "delivery": delivery_boundary(in_app_delivered=True),
        }


@app.post("/api/support-tickets/{ticket_id}/replies")
def reply_customer_support_ticket(
    ticket_id: int,
    payload: CustomerSupportReplyInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("customer")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        ticket = db.execute(
            """SELECT id,reference FROM support_tickets
               WHERE id=? AND (customer_id=? OR (customer_id IS NULL AND LOWER(email)=LOWER(?)))""",
            (ticket_id, user["id"], user["email"]),
        ).fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found")
        created_at = now_iso()
        message_id = db.execute(
            """INSERT INTO support_messages(ticket_id,author_user_id,author_role,message,visibility,created_at)
               VALUES(?,?,'customer',?,'customer',?)""",
            (ticket_id, user["id"], payload.message.strip(), created_at),
        ).lastrowid
        db.execute(
            """UPDATE support_tickets
               SET customer_id=COALESCE(customer_id,?),status='open',resolved_at=NULL,updated_at=? WHERE id=?""",
            (user["id"], created_at, ticket_id),
        )
        db.execute(
            """INSERT INTO notifications(audience_role,title,message,kind,delivery_channels,created_at)
               VALUES('admin',?,?, 'support','[\"in_app\"]',?)""",
            (f"Family replied · {ticket['reference']}", "A family reply is waiting in the support queue.", created_at),
        )
        audit(
            db, user["id"], "reply_customer_support_ticket", "support_ticket", ticket_id,
            {"reference": ticket["reference"], "message_id": message_id}, client_ip(request),
        )
        return {
            "replied": True, "message_id": message_id, "status": "open",
            "delivery": delivery_boundary(in_app_delivered=True),
        }


@app.get("/api/staff/achievements")
def staff_achievements(user: dict[str, Any] = Depends(require_roles("staff", "admin"))) -> dict[str, Any]:
    with db_session() as db:
        return {
            "achievements": staff_achievement_rows(db, user),
            "eligible_swimmers": eligible_achievement_swimmers(db, user),
            "skill_progress": skill_progress_rows(db, user),
            "templates": achievement_template_rows(db),
            "privacy": {
                "evidence_note": "Family-visible certificate evidence",
                "private_staff_note": "Staff and management only; excluded from every customer response",
            },
            "certificate_rendering": "html_print",
        }


@app.post("/api/staff/skill-progress")
def record_skill_progress(payload: StudentSkillInput, request: Request, user: dict[str, Any] = Depends(require_roles("staff", "admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        eligible = eligible_achievement_swimmers(db, user)
        if not any(row["swimmer_id"] == payload.swimmer_id for row in eligible):
            raise HTTPException(status_code=404, detail="Eligible swimmer not found")
        cursor = db.execute(
            """INSERT INTO swimmer_skill_updates
               (swimmer_id,skill_name,skill_status,feedback,next_step,recorded_by,recorded_at)
               VALUES(?,?,?,?,?,?,?)""",
            (payload.swimmer_id, payload.skill_name, payload.skill_status, encrypt_sensitive(payload.feedback),
             encrypt_sensitive(payload.next_step), user["id"], now_iso()),
        )
        audit(db, user["id"], "record_skill_progress", "swimmer_skill_update", cursor.lastrowid,
              {"swimmer_id": payload.swimmer_id, "skill_status": payload.skill_status}, client_ip(request))
        return {"saved": True, "id": cursor.lastrowid, "family_visible": True}


@app.post("/api/staff/achievements")
def issue_achievement(
    payload: AchievementAwardInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("staff", "admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        # Eligibility and award creation are one decision. Hold the write lock so a
        # confirmed booking cannot be cancelled between the instructor check and insert.
        db.execute("BEGIN IMMEDIATE")
        template = db.execute(
            "SELECT * FROM achievement_templates WHERE code=? AND active=1", (payload.template_code,)
        ).fetchone()
        if not template:
            raise HTTPException(status_code=404, detail="Achievement template not found")
        swimmer = db.execute(
            """SELECT s.id,s.customer_id,s.first_name,s.last_name
               FROM swimmers s WHERE s.id=? AND s.active=1""",
            (payload.swimmer_id,),
        ).fetchone()
        if not swimmer:
            raise HTTPException(status_code=404, detail="Eligible swimmer not found")

        selected_class = None
        if user["role"] == "staff":
            if payload.class_id is None:
                raise HTTPException(status_code=400, detail="Choose one of your confirmed classes for this achievement")
            selected_class = db.execute(
                """SELECT c.id,c.code,c.title
                   FROM classes c JOIN bookings b ON b.class_id=c.id
                   WHERE c.id=? AND c.instructor_id=? AND b.swimmer_id=? AND b.status='confirmed'""",
                (payload.class_id, user["id"], payload.swimmer_id),
            ).fetchone()
            if not selected_class:
                # A single not-found response avoids confirming whether an unrelated
                # swimmer or class exists outside this instructor's responsibility.
                raise HTTPException(status_code=404, detail="Eligible swimmer and class were not found")
        elif payload.class_id is not None:
            selected_class = db.execute(
                """SELECT c.id,c.code,c.title
                   FROM classes c JOIN bookings b ON b.class_id=c.id
                   WHERE c.id=? AND b.swimmer_id=? AND b.status='confirmed'""",
                (payload.class_id, payload.swimmer_id),
            ).fetchone()
            if not selected_class:
                raise HTTPException(status_code=409, detail="The swimmer is not confirmed in the selected class; leave the class blank for a management award")

        awarded_at = now_iso()
        reference = certificate_reference(db)
        cursor = db.execute(
            """INSERT INTO swimmer_achievements
               (certificate_reference,template_id,swimmer_id,class_id,certificate_style,evidence_note,
                private_staff_note,status,awarded_by,awarded_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                reference, template["id"], swimmer["id"], selected_class["id"] if selected_class else None,
                template["certificate_style"], payload.evidence_note, payload.private_staff_note or None,
                "active", user["id"], awarded_at,
            ),
        )
        achievement_id = cursor.lastrowid
        db.execute(
            """INSERT INTO notifications(user_id,title,message,kind,delivery_channels,created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                swimmer["customer_id"], f"New achievement for {swimmer['first_name']}",
                f"{swimmer['first_name']} earned {template['title']}. Open Achievements to view certificate {reference}.",
                "achievement", '["in_app"]', awarded_at,
            ),
        )
        audit(
            db, user["id"], "issue_swimmer_achievement", "swimmer_achievement", achievement_id,
            {
                "certificate_reference": reference, "template_code": template["code"],
                "swimmer_id": swimmer["id"], "class_id": selected_class["id"] if selected_class else None,
                "evidence_note_family_visible": True, "private_staff_note_recorded": bool(payload.private_staff_note),
            },
            client_ip(request),
        )
        issued = next(item for item in staff_achievement_rows(db, user) if item["id"] == achievement_id)
        return {
            "awarded": True,
            "achievement": issued,
            "notification": {"in_app_delivered": True, "external_channels": {}},
            "certificate_rendering": "html_print",
        }


@app.post("/api/staff/achievements/{achievement_id}/revoke")
def revoke_achievement(
    achievement_id: int,
    payload: AchievementRevokeInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("staff", "admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        achievement = db.execute(
            """SELECT a.*,s.customer_id,s.first_name swimmer_first,t.code template_code,t.title template_title
               FROM swimmer_achievements a
               JOIN swimmers s ON s.id=a.swimmer_id
               JOIN achievement_templates t ON t.id=a.template_id
               WHERE a.id=?""",
            (achievement_id,),
        ).fetchone()
        if not achievement:
            raise HTTPException(status_code=404, detail="Achievement not found")
        if user["role"] == "staff" and achievement["awarded_by"] != user["id"]:
            raise HTTPException(status_code=403, detail="Staff can revoke only achievements they issued")
        if achievement["status"] == "revoked":
            raise HTTPException(status_code=409, detail="This achievement has already been revoked")

        revoked_at = now_iso()
        db.execute(
            """UPDATE swimmer_achievements
               SET status='revoked',revoked_by=?,revoked_at=?,revocation_reason=?
               WHERE id=? AND status='active'""",
            (user["id"], revoked_at, payload.reason, achievement_id),
        )
        db.execute(
            """INSERT INTO notifications(user_id,title,message,kind,delivery_channels,created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                achievement["customer_id"], f"Achievement update for {achievement['swimmer_first']}",
                f"Certificate {achievement['certificate_reference']} ({achievement['template_title']}) has been revoked. Reason: {payload.reason}",
                "achievement", '["in_app"]', revoked_at,
            ),
        )
        audit(
            db, user["id"], "revoke_swimmer_achievement", "swimmer_achievement", achievement_id,
            {
                "certificate_reference": achievement["certificate_reference"],
                "template_code": achievement["template_code"], "swimmer_id": achievement["swimmer_id"],
                "class_id": achievement["class_id"], "reason": payload.reason,
            },
            client_ip(request),
        )
        return {
            "revoked": True, "achievement_id": achievement_id,
            "certificate_reference": achievement["certificate_reference"],
            "revoked_at": revoked_at, "reason": payload.reason,
            "notification": {"in_app_delivered": True, "external_channels": {}},
        }


@app.get("/api/staff/support-tickets")
def list_staff_support_tickets(user: dict[str, Any] = Depends(require_roles("staff", "admin"))) -> dict[str, Any]:
    with db_session() as db:
        queue = rows(
            db.execute(
                """SELECT t.id,t.reference,t.customer_id,t.category,t.name,t.email,t.phone,t.subject,
                          t.status,t.priority,t.assigned_to,t.source,t.created_at,t.updated_at,t.resolved_at,
                          TRIM(COALESCE(assigned.first_name,'') || ' ' || COALESCE(assigned.last_name,'')) assigned_name,
                          (SELECT COUNT(*) FROM support_messages m WHERE m.ticket_id=t.id) message_count,
                          (SELECT COUNT(*) FROM support_messages m WHERE m.ticket_id=t.id AND m.visibility='internal') internal_note_count
                   FROM support_tickets t LEFT JOIN users assigned ON assigned.id=t.assigned_to
                   ORDER BY CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,
                            CASE t.status WHEN 'new' THEN 0 WHEN 'open' THEN 1 WHEN 'waiting_customer' THEN 2 WHEN 'resolved' THEN 3 ELSE 4 END,
                            t.updated_at DESC,t.id DESC"""
            )
        )
        counts = {status: 0 for status in ("new", "open", "waiting_customer", "resolved", "closed")}
        for ticket in queue:
            counts[ticket["status"]] += 1
        return {
            "tickets": queue,
            "summary": {"total": len(queue), "guest": sum(1 for item in queue if item["source"] == "public_widget" and item["customer_id"] is None), "by_status": counts},
            "delivery_boundary": {"email": "not_implemented", "push": "not_implemented"},
        }


@app.get("/api/staff/support-tickets/{ticket_id}")
def get_staff_support_ticket(ticket_id: int, user: dict[str, Any] = Depends(require_roles("staff", "admin"))) -> dict[str, Any]:
    with db_session() as db:
        ticket = staff_support_ticket(db, ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found")
        return {
            "ticket": ticket,
            "privacy": {"internal_notes": "staff_and_management_only", "customer_messages": "visible_to_ticket_owner"},
            "delivery_boundary": {"email": "not_implemented", "push": "not_implemented"},
        }


@app.post("/api/staff/support-tickets/{ticket_id}/replies")
def reply_staff_support_ticket(
    ticket_id: int,
    payload: StaffSupportReplyInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("staff", "admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        ticket = db.execute("SELECT * FROM support_tickets WHERE id=?", (ticket_id,)).fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found")
        created_at = now_iso()
        visibility = "internal" if payload.internal_note else "customer"
        message_id = db.execute(
            """INSERT INTO support_messages(ticket_id,author_user_id,author_role,message,visibility,created_at)
               VALUES(?,?,?,?,?,?)""",
            (ticket_id, user["id"], user["role"], payload.message.strip(), visibility, created_at),
        ).lastrowid
        next_status = ticket["status"] if payload.internal_note else "waiting_customer"
        next_resolved_at = ticket["resolved_at"] if payload.internal_note else None
        db.execute(
            """UPDATE support_tickets SET assigned_to=COALESCE(assigned_to,?),status=?,resolved_at=?,updated_at=? WHERE id=?""",
            (user["id"], next_status, next_resolved_at, created_at, ticket_id),
        )
        customer_id = ticket["customer_id"]
        if customer_id is None:
            account = db.execute(
                "SELECT id FROM users WHERE role='customer' AND active=1 AND LOWER(email)=LOWER(?)",
                (ticket["email"],),
            ).fetchone()
            customer_id = account["id"] if account else None
            if customer_id is not None:
                db.execute("UPDATE support_tickets SET customer_id=? WHERE id=?", (customer_id, ticket_id))
        in_app_delivered = False
        if not payload.internal_note and customer_id is not None:
            db.execute(
                """INSERT INTO notifications(user_id,title,message,kind,delivery_channels,created_at)
                   VALUES(?,?,?,'support','[\"in_app\"]',?)""",
                (customer_id, f"HV Swim replied · {ticket['reference']}", "A new reply is available in your account messages.", created_at),
            )
            in_app_delivered = True
        audit(
            db, user["id"], "add_support_internal_note" if payload.internal_note else "reply_staff_support_ticket",
            "support_ticket", ticket_id,
            {"reference": ticket["reference"], "message_id": message_id, "visibility": visibility, "status": next_status},
            client_ip(request),
        )
        return {
            "replied": True, "message_id": message_id, "visibility": visibility,
            "status": next_status, "delivery": delivery_boundary(in_app_delivered=in_app_delivered),
        }


@app.patch("/api/staff/support-tickets/{ticket_id}")
def update_staff_support_ticket(
    ticket_id: int,
    payload: SupportTicketUpdateInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("staff", "admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        ticket = db.execute("SELECT id,reference,status,priority,assigned_to FROM support_tickets WHERE id=?", (ticket_id,)).fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found")
        changes: dict[str, Any] = {}
        assignments: list[str] = []
        values: list[Any] = []
        if "status" in payload.model_fields_set:
            changes["status"] = payload.status
            assignments.append("status=?")
            values.append(payload.status)
            assignments.append("resolved_at=?")
            values.append(now_iso() if payload.status in {"resolved", "closed"} else None)
        if "priority" in payload.model_fields_set:
            changes["priority"] = payload.priority
            assignments.append("priority=?")
            values.append(payload.priority)
        if "assigned_to" in payload.model_fields_set:
            if payload.assigned_to is not None:
                assignee = db.execute(
                    "SELECT id FROM users WHERE id=? AND role IN ('staff','admin') AND active=1",
                    (payload.assigned_to,),
                ).fetchone()
                if not assignee:
                    raise HTTPException(status_code=404, detail="Active staff assignee not found")
            changes["assigned_to"] = payload.assigned_to
            assignments.append("assigned_to=?")
            values.append(payload.assigned_to)
        changed_at = now_iso()
        assignments.append("updated_at=?")
        values.extend((changed_at, ticket_id))
        db.execute(f"UPDATE support_tickets SET {','.join(assignments)} WHERE id=?", values)
        audit(
            db, user["id"], "update_support_ticket", "support_ticket", ticket_id,
            {"reference": ticket["reference"], "changes": changes}, client_ip(request),
        )
        return {"saved": True, "ticket": staff_support_ticket(db, ticket_id)}


@app.get("/api/customer/bookings")
def customer_bookings(user: dict[str, Any] = Depends(require_roles("customer", "admin"))) -> dict[str, Any]:
    with db_session() as db:
        where, params = ("s.customer_id=?", (user["id"],)) if user["role"] == "customer" else ("1=1", ())
        query = f"""SELECT b.id,b.status,b.created_at,s.id swimmer_id,s.swimmer_number,s.first_name swimmer_first,s.last_name swimmer_last,
                    c.id class_id,c.title,c.level,c.weekday,c.start_time,c.duration_minutes,l.name location_name,
                    u.first_name instructor_first,u.last_name instructor_last
                    FROM bookings b JOIN swimmers s ON s.id=b.swimmer_id JOIN classes c ON c.id=b.class_id
                    JOIN locations l ON l.id=c.location_id LEFT JOIN users u ON u.id=c.instructor_id
                    WHERE {where} ORDER BY c.weekday,c.start_time"""
        bookings = rows(db.execute(query, params))
        waitlist_query = f"""SELECT w.id,w.position,w.status,w.created_at,s.id swimmer_id,s.swimmer_number,s.first_name swimmer_first,s.last_name swimmer_last,
                              c.id class_id,c.title,c.level,c.weekday,c.start_time,c.duration_minutes,l.name location_name
                              FROM waitlist w JOIN swimmers s ON s.id=w.swimmer_id JOIN classes c ON c.id=w.class_id
                              JOIN locations l ON l.id=c.location_id WHERE {where} AND w.status='waiting'
                              ORDER BY c.weekday,c.start_time,w.position"""
        return {
            "bookings": bookings,
            "waitlist": rows(db.execute(waitlist_query, params)),
            "new_enrolments": {
                "mode": "enquiry_only",
                "url": "/enquire.html",
                "message": "Send a lesson enquiry for every new enrolment or waitlist request.",
            },
        }


@app.get("/api/customer/billing")
def customer_billing(user: dict[str, Any] = Depends(require_roles("customer"))) -> dict[str, Any]:
    with db_session() as db:
        invoice_ids = [
            row["id"]
            for row in db.execute(
                """SELECT id FROM billing_invoices
                   WHERE customer_id=? AND status!='draft' ORDER BY created_at DESC""",
                (user["id"],),
            )
        ]
        invoices = []
        for invoice_id in invoice_ids:
            invoice = billing_invoice_payload(db, invoice_id)
            invoices.append(
                {
                    key: invoice[key]
                    for key in (
                        "id",
                        "invoice_number",
                        "provider",
                        "currency",
                        "customer_number",
                        "status",
                        "issue_date",
                        "due_date",
                        "total_cents",
                        "amount_paid_cents",
                        "amount_due_cents",
                        "xero_invoice_number",
                        "xero_status",
                        "online_invoice_url",
                        "term_name",
                        "created_at",
                        "updated_at",
                        "lines",
                    )
                }
            )
        outstanding = sum(
            int(invoice["amount_due_cents"])
            for invoice in invoices
            if invoice["status"] not in {"paid", "voided"}
        )
        return {
            "invoices": invoices,
            "summary": {
                "invoice_count": len(invoices),
                "outstanding_cents": outstanding,
                "paid_cents": sum(int(invoice["amount_paid_cents"]) for invoice in invoices),
            },
            "lesson_provider": "Xero",
            "merchandise_provider": "Shopify",
            "card_data_stored": False,
        }


@app.get("/api/customer/absences")
def customer_absences(user: dict[str, Any] = Depends(require_roles("customer"))) -> dict[str, Any]:
    with db_session() as db:
        term = active_term(db)
        term_data = public_term_context(db)
        bookings = rows(db.execute(
            """SELECT b.id booking_id,s.id swimmer_id,s.first_name swimmer_first,s.last_name swimmer_last,
                      c.id class_id,c.code,c.title,c.weekday,c.start_time,c.duration_minutes,l.name location_name
               FROM bookings b JOIN swimmers s ON s.id=b.swimmer_id JOIN classes c ON c.id=b.class_id
               JOIN locations l ON l.id=c.location_id
               WHERE s.customer_id=? AND b.status='confirmed' AND c.active=1
               ORDER BY s.first_name,c.weekday,c.start_time""",
            (user["id"],),
        ))
        today = business_today()
        if term:
            term_end = date.fromisoformat(term["end_date"])
            for booking in bookings:
                occurrence = next_class_occurrence(booking["weekday"], today, term_end)
                booking["next_occurrence"] = occurrence.isoformat() if occurrence else None
        else:
            for booking in bookings:
                booking["next_occurrence"] = None
        history = rows(db.execute(
            """SELECT a.id,a.occurrence_date,a.reason_category,a.credit_status,a.reported_at,
                      b.id booking_id,s.id swimmer_id,s.first_name swimmer_first,c.title,c.code,c.start_time,l.name location_name,
                      t.name term_name,t.absence_credit_limit
               FROM absence_reports a JOIN bookings b ON b.id=a.booking_id JOIN swimmers s ON s.id=b.swimmer_id
               JOIN classes c ON c.id=b.class_id JOIN locations l ON l.id=c.location_id
               JOIN school_terms t ON t.id=a.term_id
               WHERE s.customer_id=? ORDER BY a.occurrence_date DESC,a.id DESC""",
            (user["id"],),
        ))
        usage: list[dict[str, Any]] = []
        if term:
            usage = rows(db.execute(
                """SELECT s.id swimmer_id,s.first_name swimmer_first,s.last_name swimmer_last,
                          SUM(CASE WHEN a.credit_status='credited' THEN 1 ELSE 0 END) credits_used
                   FROM swimmers s LEFT JOIN bookings b ON b.swimmer_id=s.id
                   LEFT JOIN absence_reports a ON a.booking_id=b.id AND a.term_id=?
                   WHERE s.customer_id=? AND s.active=1 GROUP BY s.id ORDER BY s.first_name""",
                (term["id"], user["id"]),
            ))
            for item in usage:
                item["credit_limit"] = term["absence_credit_limit"]
                item["credits_remaining"] = max(0, term["absence_credit_limit"] - int(item["credits_used"] or 0))
        return {
            "term": term_data,
            "bookings": bookings,
            "usage": usage,
            "history": history,
            "policy": {
                "lesson_price_cents": 2250,
                "payment_due": "on_enrolment",
                "make_up_classes": False,
                "mid_term_refunds": False,
                "financial_boundary": "An eligible absence credit is recorded here; no Xero, bank or payment adjustment is made automatically.",
            },
        }


@app.post("/api/customer/absences")
def report_customer_absence(payload: AbsenceReportInput, request: Request, user: dict[str, Any] = Depends(require_roles("customer")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    if payload.occurrence_date < business_today():
        raise HTTPException(status_code=422, detail="Absences must be reported for today or a future lesson")
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        booking = db.execute(
            """SELECT b.id,b.status,b.swimmer_id,s.customer_id,s.first_name swimmer_first,
                      c.id class_id,c.title,c.weekday,c.start_time
               FROM bookings b JOIN swimmers s ON s.id=b.swimmer_id JOIN classes c ON c.id=b.class_id
               WHERE b.id=?""",
            (payload.booking_id,),
        ).fetchone()
        if not booking or booking["customer_id"] != user["id"] or booking["status"] != "confirmed":
            raise HTTPException(status_code=404, detail="Confirmed lesson booking not found")
        term = validate_class_occurrence(db, booking, payload.occurrence_date)
        if term["status"] != "active":
            raise HTTPException(status_code=409, detail="Absences can only be reported within the active school term")
        existing = db.execute(
            "SELECT id,credit_status FROM absence_reports WHERE booking_id=? AND occurrence_date=?",
            (payload.booking_id, payload.occurrence_date.isoformat()),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="This absence has already been reported")
        credits_used = db.execute(
            """SELECT COUNT(*) FROM absence_reports a JOIN bookings b ON b.id=a.booking_id
               WHERE b.swimmer_id=? AND a.term_id=? AND a.credit_status='credited'""",
            (booking["swimmer_id"], term["id"]),
        ).fetchone()[0]
        credit_status = "credited" if credits_used < term["absence_credit_limit"] else "recorded_no_credit"
        cursor = db.execute(
            """INSERT INTO absence_reports(
                   booking_id,term_id,occurrence_date,reason_category,credit_status,reported_by,reported_at
               ) VALUES(?,?,?,?,?,?,?)""",
            (payload.booking_id, term["id"], payload.occurrence_date.isoformat(), payload.reason_category, credit_status, user["id"], now_iso()),
        )
        audit(
            db, user["id"], "report_lesson_absence", "absence_report", cursor.lastrowid,
            {"booking_id": payload.booking_id, "occurrence_date": payload.occurrence_date.isoformat(), "credit_status": credit_status},
            client_ip(request),
        )
        return {
            "id": cursor.lastrowid,
            "credit_status": credit_status,
            "credits_used": credits_used + (1 if credit_status == "credited" else 0),
            "credit_limit": term["absence_credit_limit"],
            "message": (
                "Absence recorded and one term credit marked as eligible."
                if credit_status == "credited"
                else "Absence recorded. The term credit limit has already been reached."
            ),
            "financial_adjustment": "not_automatic",
        }


@app.post("/api/customer/bookings")
def create_booking(payload: BookingInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    """Management-only confirmation path used after the team has reviewed an enquiry."""
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        # Capacity is read and then written. Without an immediate write lock two requests
        # arriving together can both see the last place free and both take it, putting the
        # class over its instructor-to-swimmer ratio.
        db.execute("BEGIN IMMEDIATE")
        term = active_term(db)
        if not term:
            raise HTTPException(status_code=409, detail="Management must publish an active school term before accepting lesson bookings")
        swimmer = db.execute("SELECT * FROM swimmers WHERE id=?", (payload.swimmer_id,)).fetchone()
        swim_class = db.execute("SELECT * FROM classes WHERE id=? AND active=1", (payload.class_id,)).fetchone()
        if not swimmer:
            raise HTTPException(status_code=404, detail="Swimmer not found")
        if not swim_class:
            raise HTTPException(status_code=404, detail="Class not found")
        existing = db.execute("SELECT id,status FROM bookings WHERE class_id=? AND swimmer_id=? AND status='confirmed'", (payload.class_id, payload.swimmer_id)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="This swimmer is already booked in the class")
        waiting = db.execute("SELECT id,position FROM waitlist WHERE class_id=? AND swimmer_id=? AND status='waiting'", (payload.class_id, payload.swimmer_id)).fetchone()
        if waiting:
            raise HTTPException(status_code=409, detail=f"This swimmer is already at position {waiting['position']} on the waitlist")
        enrolled = db.execute("SELECT COUNT(*) FROM bookings WHERE class_id=? AND status='confirmed'", (payload.class_id,)).fetchone()[0]
        if enrolled >= swim_class["capacity"]:
            position = db.execute("SELECT COUNT(*) FROM waitlist WHERE class_id=? AND status='waiting'", (payload.class_id,)).fetchone()[0] + 1
            cursor = db.execute("INSERT INTO waitlist(class_id,swimmer_id,position,status,created_at) VALUES(?,?,?,?,?)", (payload.class_id, payload.swimmer_id, position, "waiting", now_iso()))
            audit(db, user["id"], "join_waitlist", "class", payload.class_id, {"swimmer_id": payload.swimmer_id, "position": position}, client_ip(request))
            return {"status": "waitlisted", "waitlist_id": cursor.lastrowid, "position": position}
        cursor = db.execute("INSERT INTO bookings(class_id,swimmer_id,status,created_at) VALUES(?,?,?,?)", (payload.class_id, payload.swimmer_id, "confirmed", now_iso()))
        charge = create_xero_lesson_charge(
            db, booking_id=cursor.lastrowid, customer_id=swimmer["customer_id"], term=term, swim_class=swim_class
        )
        db.execute("INSERT INTO notifications(user_id,title,message,kind,delivery_channels,created_at) VALUES(?,?,?,?,?,?)", (swimmer["customer_id"], "Lesson booking confirmed", f"{swimmer['first_name']} is confirmed for {swim_class['title']}.", "booking", '["in_app","email"]', now_iso()))
        audit(db, user["id"], "create_booking", "booking", cursor.lastrowid, {"class_id": payload.class_id, "swimmer_id": payload.swimmer_id, "lesson_charge_reference": charge["reference"], "payment_provider": "xero"}, client_ip(request))
        return {
            "status": "confirmed", "booking_id": cursor.lastrowid,
            "payment": {"provider": "Xero", "route": "xero_invoice_workflow", "reference": charge["reference"], "amount_cents": charge["amount_cents"], "status": charge["status"], "family_customer_number": charge["family_customer_number"], "swimmer_number": charge["swimmer_number"], "xero_contact_mapped": bool(charge["xero_contact_id"])},
        }


@app.delete("/api/customer/bookings/{booking_id}")
def cancel_booking(booking_id: int, request: Request, user: dict[str, Any] = Depends(require_roles("customer", "admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, bool]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        booking = db.execute("SELECT b.*,s.customer_id FROM bookings b JOIN swimmers s ON s.id=b.swimmer_id WHERE b.id=?", (booking_id,)).fetchone()
        if not booking or (user["role"] == "customer" and booking["customer_id"] != user["id"]):
            raise HTTPException(status_code=404, detail="Booking not found")
        db.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (booking_id,))
        db.execute("UPDATE lesson_charges SET status='cancelled_no_refund' WHERE booking_id=? AND status='pending_xero_invoice'", (booking_id,))
        audit(db, user["id"], "cancel_booking", "booking", booking_id, ip_address=client_ip(request))
        return {"ok": True}


@app.get("/api/staff/roster")
def staff_roster(user: dict[str, Any] = Depends(require_roles("staff", "admin"))) -> dict[str, Any]:
    with db_session() as db:
        where, params = ("r.staff_id=?", (user["id"],)) if user["role"] == "staff" else ("1=1", ())
        query = f"""SELECT r.*,l.name location_name,l.slug location_slug,u.first_name,u.last_name
                    FROM rosters r JOIN locations l ON l.id=r.location_id JOIN users u ON u.id=r.staff_id
                    WHERE {where} AND r.shift_date>=? ORDER BY r.shift_date,r.start_time"""
        return {"roster": rows(db.execute(query, params + (business_today().isoformat(),)))}


@app.get("/api/staff/lesson-register")
def staff_lesson_register(occurrence_date: date | None = None, user: dict[str, Any] = Depends(require_roles("staff", "admin"))) -> dict[str, Any]:
    selected = occurrence_date or business_today()
    with db_session() as db:
        term = term_for_date(db, selected)
        if not term:
            return {
                "occurrence_date": selected.isoformat(),
                "term": None,
                "classes": [],
                "message": "This date is outside every published school term.",
            }
        owner_clause = " AND c.instructor_id=?" if user["role"] == "staff" else ""
        params: tuple[Any, ...] = (selected.weekday(), user["id"]) if user["role"] == "staff" else (selected.weekday(),)
        classes = rows(db.execute(
            f"""SELECT c.id,c.code,c.title,c.level,c.start_time,c.duration_minutes,c.capacity,
                       l.id location_id,l.name location_name,l.slug location_slug,
                       u.first_name instructor_first,u.last_name instructor_last
                FROM classes c JOIN locations l ON l.id=c.location_id LEFT JOIN users u ON u.id=c.instructor_id
                WHERE c.active=1 AND c.weekday=?{owner_clause} ORDER BY c.start_time,c.id""",
            params,
        ))
        for class_item in classes:
            register = rows(db.execute(
                """SELECT b.id booking_id,s.id swimmer_id,s.first_name swimmer_first,s.last_name swimmer_last,
                          s.level,s.medical_notes,s.allergies,s.medications,s.support_notes,s.photo_consent,
                          la.id attendance_id,la.attendance_status,la.parent_onsite_confirmed,
                          la.photo_clearance_snapshot,la.private_note,la.updated_at,
                          ar.id absence_report_id,ar.credit_status absence_credit_status
                   FROM bookings b JOIN swimmers s ON s.id=b.swimmer_id
                   LEFT JOIN lesson_attendance la ON la.booking_id=b.id AND la.occurrence_date=?
                   LEFT JOIN absence_reports ar ON ar.booking_id=b.id AND ar.occurrence_date=?
                   WHERE b.class_id=? AND b.status='confirmed' AND s.active=1
                   ORDER BY s.first_name,s.last_name""",
                (selected.isoformat(), selected.isoformat(), class_item["id"]),
            ))
            for record in register:
                reveal_swimmer_record(record)
                record["photo_consent"] = bool(record["photo_consent"])
                record["parent_onsite_confirmed"] = None if record["parent_onsite_confirmed"] is None else bool(record["parent_onsite_confirmed"])
                record["reported_absence"] = bool(record["absence_report_id"])
                if record["reported_absence"] and not record["attendance_status"]:
                    record["suggested_status"] = "excused"
            class_item["parent_onsite_required"] = "stroke development" not in class_item["title"].lower()
            class_item["register"] = register
            class_item["completed"] = sum(1 for record in register if record["attendance_status"])
        return {
            "occurrence_date": selected.isoformat(),
            "term": {**dict(term), "is_preview": term["source"] == "preview"},
            "classes": classes,
            "policy": {
                "parent_onsite": "Required while a swimmer is present, except Stroke Development classes.",
                "photo_clearance": "The register snapshots the swimmer's recorded consent; staff must not take photos when clearance is absent.",
                "medical_privacy": "Only record lesson-safety information in the private note.",
            },
        }


@app.post("/api/staff/lesson-register")
def save_lesson_attendance(payload: LessonAttendanceInput, request: Request, user: dict[str, Any] = Depends(require_roles("staff", "admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    if payload.occurrence_date > business_today():
        raise HTTPException(status_code=422, detail="Attendance cannot be recorded before the lesson date")
    with db_session() as db:
        booking = db.execute(
            """SELECT b.id,b.status,c.id class_id,c.title,c.weekday,c.instructor_id,
                      s.id swimmer_id,s.photo_consent
               FROM bookings b JOIN classes c ON c.id=b.class_id JOIN swimmers s ON s.id=b.swimmer_id
               WHERE b.id=?""",
            (payload.booking_id,),
        ).fetchone()
        if not booking or booking["status"] != "confirmed":
            raise HTTPException(status_code=404, detail="Confirmed lesson booking not found")
        if user["role"] == "staff" and booking["instructor_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Staff can update only their assigned lesson register")
        term = validate_class_occurrence(db, booking, payload.occurrence_date)
        parent_required = "stroke development" not in booking["title"].lower()
        if parent_required and payload.attendance_status in {"present", "late"} and payload.parent_onsite_confirmed is not True:
            raise HTTPException(status_code=422, detail="Confirm that a parent or guardian is on site for this swimmer")
        recorded_at = now_iso()
        existing = db.execute(
            "SELECT id FROM lesson_attendance WHERE booking_id=? AND occurrence_date=?",
            (payload.booking_id, payload.occurrence_date.isoformat()),
        ).fetchone()
        if existing:
            db.execute(
                """UPDATE lesson_attendance SET attendance_status=?,parent_onsite_confirmed=?,
                          photo_clearance_snapshot=?,private_note=?,recorded_by=?,term_id=?,updated_at=? WHERE id=?""",
                (
                    payload.attendance_status,
                    None if payload.parent_onsite_confirmed is None else int(payload.parent_onsite_confirmed),
                    int(bool(booking["photo_consent"])),
                    payload.private_note or None,
                    user["id"],
                    term["id"],
                    recorded_at,
                    existing["id"],
                ),
            )
            attendance_id = existing["id"]
            action = "update_lesson_attendance"
        else:
            attendance_id = db.execute(
                """INSERT INTO lesson_attendance(
                       booking_id,term_id,occurrence_date,attendance_status,parent_onsite_confirmed,
                       photo_clearance_snapshot,private_note,recorded_by,recorded_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    payload.booking_id,
                    term["id"],
                    payload.occurrence_date.isoformat(),
                    payload.attendance_status,
                    None if payload.parent_onsite_confirmed is None else int(payload.parent_onsite_confirmed),
                    int(bool(booking["photo_consent"])),
                    payload.private_note or None,
                    user["id"],
                    recorded_at,
                    recorded_at,
                ),
            ).lastrowid
            action = "record_lesson_attendance"
        audit(
            db, user["id"], action, "lesson_attendance", attendance_id,
            {
                "booking_id": payload.booking_id,
                "class_id": booking["class_id"],
                "occurrence_date": payload.occurrence_date.isoformat(),
                "attendance_status": payload.attendance_status,
                "parent_onsite_required": parent_required,
                "parent_onsite_confirmed": payload.parent_onsite_confirmed,
                "photo_clearance_snapshot": bool(booking["photo_consent"]),
                "term_id": term["id"],
            },
            client_ip(request),
        )
        return {
            "id": attendance_id,
            "saved": True,
            "photo_clearance": bool(booking["photo_consent"]),
            "parent_onsite_required": parent_required,
            "updated_at": recorded_at,
        }


@app.post("/api/staff/clock")
def staff_clock(payload: ClockInput, request: Request, user: dict[str, Any] = Depends(require_roles("staff", "admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        return workforce.clock_action(db, user, workforce.ClockAction(**payload.model_dump()))


@app.get("/api/staff/time-entries")
def staff_time_entries(user: dict[str, Any] = Depends(require_roles("staff", "admin"))) -> dict[str, Any]:
    with db_session() as db:
        where, params = ("t.staff_id=?", (user["id"],)) if user["role"] == "staff" else ("1=1", ())
        query = f"""SELECT t.*,l.name location_name,u.first_name,u.last_name FROM time_entries t
                    JOIN locations l ON l.id=t.location_id JOIN users u ON u.id=t.staff_id WHERE {where}
                    ORDER BY t.clock_in DESC LIMIT 100"""
        return {"time_entries": rows(db.execute(query, params))}


@app.post("/api/staff/time-entries")
def create_manual_hours(
    payload: HoursEntryInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("staff", "admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        location = location_by_slug(db, payload.location_slug)
        existing = rows(db.execute(
            """SELECT id,work_date,entry_scope,status FROM time_entries
               WHERE staff_id=? AND week_start=?""",
            (user["id"], payload.week_start.isoformat()),
        ))
        if payload.entry_mode == "weekly" and existing:
            raise HTTPException(status_code=409, detail="This payroll week already has hours. Edit the daily records or choose another week.")
        if payload.entry_mode == "daily" and any(item["entry_scope"] == "weekly" for item in existing):
            raise HTTPException(status_code=409, detail="This week already has a weekly-total entry")

        values = (
            [(payload.week_start, float(payload.total_hours or 0))]
            if payload.entry_mode == "weekly"
            else [(entry.work_date, float(entry.hours)) for entry in payload.daily_entries]
        )
        saved_ids: list[int] = []
        for work_day, hours in values:
            start = datetime.combine(work_day, datetime.min.time(), tzinfo=MELBOURNE_TZ)
            finish = start + timedelta(hours=hours)
            current = db.execute(
                """SELECT * FROM time_entries
                   WHERE staff_id=? AND week_start=? AND work_date=? AND entry_scope='daily'""",
                (user["id"], payload.week_start.isoformat(), work_day.isoformat()),
            ).fetchone()
            if current and current["status"] != "draft":
                raise HTTPException(status_code=409, detail=f"Hours for {work_day.isoformat()} have already been submitted")
            if current and current["origin"] != "manual":
                raise HTTPException(status_code=409, detail="Use a reviewed correction for an existing clock or legacy entry")
            workforce.assert_no_entry_overlap(db, user["id"], {
                "origin": "manual", "entry_scope": payload.entry_mode,
                "work_date": work_day.isoformat(), "week_start": payload.week_start.isoformat(),
            }, current["id"] if current else None)
            if current:
                db.execute(
                    """UPDATE time_entries SET location_id=?,clock_in=?,clock_out=?,hours=?,notes=?
                       WHERE id=?""",
                    (location["id"], start.isoformat(), finish.isoformat(), hours, payload.notes or None, current["id"]),
                )
                saved_ids.append(current["id"])
            else:
                entry_id = db.execute(
                    """INSERT INTO time_entries(
                           staff_id,location_id,clock_in,clock_out,hours,status,work_date,week_start,entry_scope,notes
                       ) VALUES(?,?,?,?,?,'draft',?,?,?,?)""",
                    (
                        user["id"], location["id"], start.isoformat(), finish.isoformat(), hours,
                        work_day.isoformat(), payload.week_start.isoformat(), payload.entry_mode, payload.notes or None,
                    ),
                ).lastrowid
                saved_ids.append(entry_id)
            db.execute("UPDATE time_entries SET origin='manual',worked_seconds=?,review_state='draft',entry_version=entry_version+? WHERE id=?",
                       (int(workforce.Decimal(str(hours))*3600), 1 if current else 0, saved_ids[-1]))
            workforce.record_event(db, user, saved_ids[-1], "manual_hours", payload.notes or "Staff-entered hours", current)
        audit(
            db, user["id"], "record_manual_hours", "time_entry",
            detail={"entry_ids": saved_ids, "week_start": payload.week_start.isoformat(), "entry_mode": payload.entry_mode, "total_hours": sum(hours for _, hours in values)},
            ip_address=client_ip(request),
        )
        return {"saved": True, "entry_ids": saved_ids, "week_start": payload.week_start.isoformat(), "entry_mode": payload.entry_mode}


@app.post("/api/staff/time-entries/submit")
def submit_timesheet(payload: SubmitTimesheetInput, request: Request, user: dict[str, Any] = Depends(require_roles("staff", "admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    if not payload.entry_ids:
        raise HTTPException(status_code=400, detail="Select at least one completed time entry")
    with db_session() as db:
        placeholders = ",".join("?" for _ in payload.entry_ids)
        params: list[Any] = list(payload.entry_ids)
        where_owner = ""
        if user["role"] == "staff":
            where_owner = " AND staff_id=?"
            params.append(user["id"])
        cursor = db.execute(f"UPDATE time_entries SET status='submitted',review_state='submitted' WHERE id IN ({placeholders}) AND clock_out IS NOT NULL AND status='draft'{where_owner}", params)
        audit(db, user["id"], "submit_timesheet", "time_entry", detail={"entry_ids": payload.entry_ids, "updated": cursor.rowcount}, ip_address=client_ip(request))
        return {"updated": cursor.rowcount}


@app.get("/api/staff/incidents")
def staff_incidents(user: dict[str, Any] = Depends(require_roles("staff", "admin"))) -> dict[str, Any]:
    with db_session() as db:
        where, params = ("ir.reported_by=?", (user["id"],)) if user["role"] == "staff" else ("1=1", ())
        reports = incident_payloads(db.execute(
            f"""SELECT ir.*,s.first_name swimmer_first,s.last_name swimmer_last,s.swimmer_number,
                       family.customer_number,family.first_name family_first,family.last_name family_last,
                       reporter.staff_number,reporter.first_name reporter_first,reporter.last_name reporter_last,
                       l.name location_name
                FROM incident_reports ir JOIN swimmers s ON s.id=ir.swimmer_id
                JOIN users family ON family.id=ir.family_user_id
                JOIN users reporter ON reporter.id=ir.reported_by
                JOIN locations l ON l.id=ir.location_id
                WHERE {where} ORDER BY ir.incident_at DESC,ir.id DESC LIMIT 250""",
            params,
        ))
        swimmers = rows(db.execute(
            """SELECT s.id,s.first_name,s.last_name,s.swimmer_number,u.customer_number,
                      u.first_name family_first,u.last_name family_last
               FROM swimmers s JOIN users u ON u.id=s.customer_id
               WHERE s.active=1 AND u.active=1 ORDER BY s.first_name,s.last_name"""
        ))
        locations = rows(db.execute("SELECT slug,name FROM locations ORDER BY CASE slug WHEN 'wood-street' THEN 0 ELSE 1 END,name"))
        return {"reports": reports, "swimmers": swimmers, "locations": locations, "reporter": {"staff_number": user.get("staff_number")}}


@app.post("/api/staff/incidents")
def create_incident_report(
    payload: IncidentReportInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("staff", "admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    incident_at = payload.incident_at.replace(tzinfo=MELBOURNE_TZ) if payload.incident_at.tzinfo is None else payload.incident_at
    incident_utc = incident_at.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if incident_utc > now + timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="Incident time cannot be in the future")
    if incident_utc < now - timedelta(days=31):
        raise HTTPException(status_code=422, detail="Incidents older than 31 days require management review before entry")
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        swimmer = db.execute(
            """SELECT s.id,s.customer_id,s.first_name,s.last_name,s.swimmer_number,u.customer_number
               FROM swimmers s JOIN users u ON u.id=s.customer_id
               WHERE s.id=? AND s.active=1 AND u.active=1""",
            (payload.swimmer_id,),
        ).fetchone()
        if not swimmer:
            raise HTTPException(status_code=404, detail="Active swimmer and family account not found")
        location = location_by_slug(db, payload.location_slug)
        reference = incident_reference(db)
        encrypted = {field_name: encrypt_sensitive(getattr(payload, field_name)) for field_name in INCIDENT_SENSITIVE_FIELDS}
        incident_id = db.execute(
            """INSERT INTO incident_reports(
                   reference,swimmer_id,family_user_id,reported_by,location_id,incident_at,incident_type,
                   what_happened,injury_observed,first_aid_applied,further_action,witnesses,
                   parent_notified,status,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'open',?)""",
            (
                reference, swimmer["id"], swimmer["customer_id"], user["id"], location["id"],
                incident_utc.isoformat(), payload.incident_type, encrypted["what_happened"],
                encrypted["injury_observed"], encrypted["first_aid_applied"], encrypted["further_action"],
                encrypted["witnesses"], int(payload.parent_notified), now_iso(),
            ),
        ).lastrowid
        db.execute(
            """UPDATE incident_reports SET severity=?,first_aider=?,emergency_services=?,supporting_notes=?
               WHERE id=?""",
            (payload.severity, encrypted["first_aider"], int(payload.emergency_services), encrypted["supporting_notes"], incident_id),
        )
        db.execute(
            """INSERT INTO notifications(user_id,title,message,kind,delivery_channels,created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                swimmer["customer_id"], "Incident report recorded",
                f"A private incident report for {swimmer['first_name']} has been recorded under {reference}. Sign in to review it and contact HV Swim if you have questions.",
                "incident", '["in_app"]', now_iso(),
            ),
        )
        audit(
            db, user["id"], "create_incident_report", "incident_report", incident_id,
            {
                "reference": reference, "swimmer_number": swimmer["swimmer_number"],
                "family_customer_number": swimmer["customer_number"], "location": payload.location_slug,
                "incident_type": payload.incident_type, "parent_notified": payload.parent_notified,
            },
            client_ip(request),
        )
        return {
            "id": incident_id, "reference": reference, "status": "open",
            "swimmer_number": swimmer["swimmer_number"], "family_customer_number": swimmer["customer_number"],
            "staff_number": user.get("staff_number"), "family_notification": "delivered_in_app",
        }


@app.patch("/api/admin/incidents/{incident_id}")
def update_incident_status(
    incident_id: int,
    payload: IncidentStatusInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        incident = db.execute("SELECT id,reference,status,manager_review FROM incident_reports WHERE id=?", (incident_id,)).fetchone()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident report not found")
        if payload.status == "closed" and not (payload.manager_review or incident["manager_review"]):
            raise HTTPException(status_code=422, detail="Record a management review before closing an incident")
        db.execute("UPDATE incident_reports SET status=? WHERE id=?", (payload.status, incident_id))
        if payload.manager_review:
            db.execute("UPDATE incident_reports SET manager_review=?,reviewed_by=?,reviewed_at=? WHERE id=?", (encrypt_sensitive(payload.manager_review), user["id"], now_iso(), incident_id))
        audit(db, user["id"], "update_incident_status", "incident_report", incident_id, {"reference": incident["reference"], "from": incident["status"], "to": payload.status}, client_ip(request))
        return {"saved": True, "id": incident_id, "status": payload.status}


@app.get("/api/customer/incidents")
def customer_incidents(user: dict[str, Any] = Depends(require_roles("customer"))) -> dict[str, Any]:
    with db_session() as db:
        reports = incident_payloads(db.execute(
            """SELECT ir.id,ir.reference,ir.incident_at,ir.incident_type,ir.what_happened,
                      ir.injury_observed,ir.first_aid_applied,ir.further_action,ir.witnesses,
                      ir.parent_notified,ir.status,ir.created_at,ir.severity,ir.first_aider,ir.emergency_services,
                      s.first_name swimmer_first,s.last_name swimmer_last,s.swimmer_number,
                      family.customer_number,reporter.staff_number,
                      reporter.first_name reporter_first,reporter.last_name reporter_last,l.name location_name
               FROM incident_reports ir JOIN swimmers s ON s.id=ir.swimmer_id
               JOIN users family ON family.id=ir.family_user_id
               JOIN users reporter ON reporter.id=ir.reported_by
               JOIN locations l ON l.id=ir.location_id
               WHERE ir.family_user_id=? ORDER BY ir.incident_at DESC,ir.id DESC""",
            (user["id"],),
        ))
        return {"reports": reports}


@app.post("/api/staff/pool-readings")
def create_pool_reading(payload: PoolReadingInput, request: Request, user: dict[str, Any] = Depends(require_roles("staff", "admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    if payload.status == "open" and payload.temperature is None:
        raise HTTPException(status_code=400, detail="An open pool requires a temperature reading")
    with db_session() as db:
        location = location_by_slug(db, payload.location_slug)
        created_at = now_iso()
        cursor = db.execute("INSERT INTO pool_readings(location_id,temperature,status,note,verified_by,source,created_at) VALUES(?,?,?,?,?,?,?)", (location["id"], payload.temperature, payload.status, payload.note, user["id"], "manual", created_at))
        db.execute("UPDATE locations SET public_status=? WHERE id=?", ({"open": "Lessons running", "changed": "Changed conditions", "closed": "Closed / lessons cancelled"}[payload.status], location["id"]))
        audience_message = f"{location['name']}: {payload.note or {'open':'Lessons running','changed':'Changed conditions','closed':'Closed / lessons cancelled'}[payload.status]}"
        db.execute("INSERT INTO notifications(audience_role,title,message,kind,delivery_channels,created_at) VALUES(?,?,?,?,?,?)", ("customer", "Pool condition updated", audience_message, "pool", '["in_app"]', created_at))
        alert = sync_pool_public_alert(
            db,
            location=location,
            pool_status=payload.status,
            note=payload.note.strip(),
            actor_id=user["id"],
            pool_reading_id=cursor.lastrowid,
            ip_address=client_ip(request),
            changed_at=created_at,
        )
        audit(db, user["id"], "publish_pool_reading", "pool_reading", cursor.lastrowid, {"location": payload.location_slug, "temperature": payload.temperature, "status": payload.status}, client_ip(request))
        return {
            "id": cursor.lastrowid, "published": True, "created_at": created_at,
            "public_alert": alert,
            "delivery": {"website_polling": "live", **delivery_boundary(in_app_delivered=True)},
        }


@app.post("/api/staff/pool-checklists")
def create_checklist(payload: ChecklistInput, request: Request, user: dict[str, Any] = Depends(require_roles("staff", "admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        location = location_by_slug(db, payload.location_slug)
        cursor = db.execute("INSERT INTO pool_checklists(location_id,staff_id,deck_safe,first_aid_ready,equipment_ready,water_checked,notes,created_at) VALUES(?,?,?,?,?,?,?,?)", (location["id"], user["id"], int(payload.deck_safe), int(payload.first_aid_ready), int(payload.equipment_ready), int(payload.water_checked), payload.notes, now_iso()))
        audit(db, user["id"], "complete_pool_checklist", "pool_checklist", cursor.lastrowid, {"location": payload.location_slug}, client_ip(request))
        return {"id": cursor.lastrowid, "complete": all([payload.deck_safe, payload.first_aid_ready, payload.equipment_ready, payload.water_checked])}


@app.get("/api/staff/qualifications")
def qualifications(user: dict[str, Any] = Depends(require_roles("staff", "admin"))) -> dict[str, Any]:
    with db_session() as db:
        return {"qualifications": qualification_records(db, user), "reminders": {"in_app": "live", "email": "setup_required", "sms": "setup_required"}}


@app.post("/api/staff/qualifications")
def create_qualification_document(
    payload: QualificationDocumentInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("staff", "admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    staff_id = payload.staff_id if user["role"] == "admin" and payload.staff_id else user["id"]
    if user["role"] == "staff" and payload.staff_id not in (None, user["id"]):
        raise HTTPException(status_code=403, detail="Staff can upload only their own certificate documents")
    document, extension, digest = validate_qualification_document(payload.document_base64, payload.document_media_type)
    filename = f"{new_token(24)}{extension}"
    QUALIFICATION_DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
    final_path = QUALIFICATION_DOCUMENT_DIR / filename
    temporary_path = QUALIFICATION_DOCUMENT_DIR / f".{filename}.tmp"
    temporary_path.write_bytes(document)
    temporary_path.replace(final_path)
    try:
        with db_session() as db:
            staff = db.execute(
                "SELECT id FROM users WHERE id=? AND role IN ('staff','admin') AND active=1",
                (staff_id,),
            ).fetchone()
            if not staff:
                raise HTTPException(status_code=404, detail="Active staff account not found")
            today = business_today()
            remaining = (payload.expiry_date - today).days
            qualification_status = "expired" if remaining < 0 else "expiring" if remaining <= payload.reminder_days else "current"
            qualification_id = db.execute(
                """INSERT INTO qualifications(
                       staff_id,qualification_type,expiry_date,status,verified_at,document_filename,
                       original_filename,document_media_type,document_sha256,uploaded_at,reminder_days
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    staff_id, payload.qualification_type, payload.expiry_date.isoformat(), qualification_status,
                    now_iso(), filename, payload.original_filename, payload.document_media_type, digest, now_iso(),
                    payload.reminder_days,
                ),
            ).lastrowid
            audit(
                db, user["id"], "upload_staff_qualification", "qualification", qualification_id,
                {"staff_id": staff_id, "qualification_type": payload.qualification_type, "expiry_date": payload.expiry_date.isoformat(), "media_type": payload.document_media_type, "sha256": digest},
                client_ip(request),
            )
            return {"id": qualification_id, "saved": True, "status": qualification_status, "document_url": f"/api/staff/qualifications/{qualification_id}/document"}
    except Exception:
        final_path.unlink(missing_ok=True)
        raise


@app.get("/api/staff/qualifications/{qualification_id}/document")
def qualification_document(
    qualification_id: int,
    user: dict[str, Any] = Depends(require_roles("staff", "admin")),
) -> FileResponse:
    with db_session() as db:
        record = db.execute("SELECT * FROM qualifications WHERE id=?", (qualification_id,)).fetchone()
        if not record or (user["role"] == "staff" and record["staff_id"] != user["id"]):
            raise HTTPException(status_code=404, detail="Certificate document not found")
        document_path = qualification_document_path(record["document_filename"])
        if not document_path or not document_path.is_file():
            raise HTTPException(status_code=404, detail="Certificate document not found")
        if hashlib.sha256(document_path.read_bytes()).hexdigest() != record["document_sha256"]:
            raise HTTPException(status_code=409, detail="Certificate document failed its integrity check")
        return FileResponse(
            document_path,
            media_type=record["document_media_type"],
            filename=record["original_filename"],
            content_disposition_type="inline",
            headers={"Cache-Control": "private, no-store"},
        )


@app.get("/api/notifications")
def notifications(user: dict[str, Any] = Depends(session_user)) -> dict[str, Any]:
    with db_session() as db:
        reminders_created = materialise_due_lesson_reminders(db, user["id"]) if user["role"] == "customer" else 0
        query = """SELECT n.id,n.user_id,n.audience_role,n.title,n.message,n.kind,n.delivery_channels,n.created_at,
                          COALESCE(r.read_at,CASE WHEN n.user_id=? THEN n.read_at END) read_at
                   FROM notifications n
                   LEFT JOIN notification_receipts r ON r.notification_id=n.id AND r.user_id=?
                   WHERE n.user_id=? OR n.audience_role=?
                   ORDER BY n.created_at DESC LIMIT 100"""
        return {
            "notifications": rows(db.execute(query, (user["id"], user["id"], user["id"], user["role"]))),
            "lesson_reminders_created": reminders_created,
        }


@app.get("/api/customer/reminder-preferences")
def get_customer_reminder_preferences(user: dict[str, Any] = Depends(require_roles("customer"))) -> dict[str, Any]:
    with db_session() as db:
        return {
            "preferences": reminder_preferences(db, user["id"]),
            "delivery": {
                "in_app": "live",
                "email": "credentials_and_adapter_required",
                "sms": "credentials_and_adapter_required",
                "push": "paused_with_mobile_app",
            },
        }


@app.patch("/api/customer/reminder-preferences")
def save_customer_reminder_preferences(
    payload: ReminderPreferencesInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("customer")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute(
            """INSERT INTO reminder_preferences(user_id,enabled,hours_before,channels,updated_at)
               VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
               enabled=excluded.enabled,hours_before=excluded.hours_before,
               channels=excluded.channels,updated_at=excluded.updated_at""",
            (user["id"], int(payload.enabled), payload.hours_before, json.dumps(payload.channels), now_iso()),
        )
        audit(
            db, user["id"], "update_lesson_reminders", "user", user["id"],
            {"enabled": payload.enabled, "hours_before": payload.hours_before, "channels": payload.channels},
            client_ip(request),
        )
        return {"saved": True, "preferences": reminder_preferences(db, user["id"])}


@app.post("/api/notifications/{notification_id}/read")
def read_notification(notification_id: int, request: Request, user: dict[str, Any] = Depends(session_user), x_csrf_token: str | None = Header(default=None)) -> dict[str, bool]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        visible = db.execute(
            "SELECT id FROM notifications WHERE id=? AND (user_id=? OR audience_role=?)",
            (notification_id, user["id"], user["role"]),
        ).fetchone()
        if not visible:
            raise HTTPException(status_code=404, detail="Notification not found")
        db.execute(
            """INSERT INTO notification_receipts(notification_id,user_id,read_at) VALUES(?,?,?)
               ON CONFLICT(notification_id,user_id) DO UPDATE SET read_at=excluded.read_at""",
            (notification_id, user["id"], now_iso()),
        )
        return {"ok": True}


@app.get("/api/admin/metrics")
def admin_metrics(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        metrics = {
            "active_swimmers": db.execute("SELECT COUNT(*) FROM swimmers WHERE active=1").fetchone()[0],
            "active_classes": db.execute("SELECT COUNT(*) FROM classes WHERE active=1").fetchone()[0],
            "confirmed_bookings": db.execute("SELECT COUNT(*) FROM bookings WHERE status='confirmed'").fetchone()[0],
            "waitlist": db.execute("SELECT COUNT(*) FROM waitlist WHERE status='waiting'").fetchone()[0],
            "pending_hours": db.execute("SELECT COALESCE(SUM(hours),0) FROM time_entries WHERE status='submitted'").fetchone()[0],
            "new_enquiries": db.execute("SELECT COUNT(*) FROM enquiries WHERE status='new'").fetchone()[0],
            "expiring_qualifications": db.execute("SELECT COUNT(*) FROM qualifications WHERE status='expiring' OR expiry_date<=?", ((business_today()+timedelta(days=60)).isoformat(),)).fetchone()[0],
            "class_utilisation": round(100 * db.execute("SELECT COUNT(*) FROM bookings WHERE status='confirmed'").fetchone()[0] / max(1, db.execute("SELECT COALESCE(SUM(capacity),1) FROM classes WHERE active=1").fetchone()[0]), 1),
        }
        return {"metrics": metrics}


@app.get("/api/admin/dashboard")
def admin_dashboard(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        term_context = public_term_context(db)
        active_swimmers = db.execute("SELECT COUNT(*) FROM swimmers WHERE active=1").fetchone()[0]
        confirmed_bookings = db.execute("SELECT COUNT(*) FROM bookings WHERE status='confirmed'").fetchone()[0]
        waitlist = db.execute("SELECT COUNT(*) FROM waitlist WHERE status='waiting'").fetchone()[0]
        enquiry_total = db.execute("SELECT COUNT(*) FROM enquiries").fetchone()[0]
        enquiry_mix = {status: 0 for status in ("new", "contacted", "trial_booked", "closed")}
        for row in db.execute("SELECT status,COUNT(*) count FROM enquiries GROUP BY status"):
            enquiry_mix[row["status"]] = row["count"]
        class_rows = []
        total_capacity = 0
        total_enrolled = 0
        class_query = """SELECT c.id,c.code,c.title,c.level,c.capacity,c.weekday,c.start_time,l.name location_name,
                         (SELECT COUNT(*) FROM bookings b WHERE b.class_id=c.id AND b.status='confirmed') enrolled
                         FROM classes c JOIN locations l ON l.id=c.location_id WHERE c.active=1"""
        for row in db.execute(class_query):
            item = dict(row)
            item["utilisation"] = round(100 * item["enrolled"] / max(1, item["capacity"]), 1)
            item["available"] = max(0, item["capacity"] - item["enrolled"])
            total_capacity += item["capacity"]
            total_enrolled += item["enrolled"]
            class_rows.append(item)
        class_rows.sort(key=lambda item: (-item["utilisation"], item["title"]))
        hour_mix = {status: 0.0 for status in ("draft", "submitted", "approved", "exported")}
        for row in db.execute("SELECT status,COALESCE(SUM(hours),0) hours FROM time_entries GROUP BY status"):
            hour_mix[row["status"]] = round(float(row["hours"] or 0), 2)
        locations = []
        now = datetime.now(timezone.utc)
        today_weekday = business_today().weekday()
        for location in db.execute("SELECT * FROM locations ORDER BY id"):
            reading = db.execute("SELECT temperature,status,note,source,created_at FROM pool_readings WHERE location_id=? ORDER BY created_at DESC LIMIT 1", (location["id"],)).fetchone()
            checklist = db.execute("SELECT created_at,deck_safe,first_aid_ready,equipment_ready,water_checked FROM pool_checklists WHERE location_id=? ORDER BY created_at DESC LIMIT 1", (location["id"],)).fetchone()
            reading_fresh = bool(reading and now - datetime.fromisoformat(reading["created_at"]) <= timedelta(hours=24))
            checklist_fresh = bool(checklist and now - datetime.fromisoformat(checklist["created_at"]) <= timedelta(hours=24))
            today_classes = db.execute("SELECT COUNT(*) FROM classes WHERE active=1 AND location_id=? AND weekday=?", (location["id"], today_weekday)).fetchone()[0] if term_context["in_session"] else 0
            locations.append({**dict(location), "latest_reading": dict(reading) if reading else None, "latest_checklist": dict(checklist) if checklist else None, "reading_fresh": reading_fresh, "checklist_fresh": checklist_fresh, "today_classes": today_classes})
        metrics = {
            "active_swimmers": active_swimmers,
            "confirmed_bookings": confirmed_bookings,
            "waitlist": waitlist,
            "enquiries_total": enquiry_total,
            "new_enquiries": enquiry_mix["new"],
            "class_utilisation": round(100 * total_enrolled / max(1, total_capacity), 1),
            "class_capacity": total_capacity,
            "pending_hours": hour_mix["submitted"],
            "pool_readings_current": sum(1 for item in locations if item["reading_fresh"]),
            "pool_locations": len(locations),
        }
        return {
            "generated_at": now_iso(),
            "source": {"name": "HV Swim operational database", "mode": "Local SQLite preview", "freshness": "Live at page load"},
            "metrics": metrics,
            "enquiry_mix": enquiry_mix,
            "classes": class_rows,
            "hour_mix": hour_mix,
            "locations": locations,
            "definitions": {
                "class_utilisation": "Confirmed bookings divided by total capacity across active classes.",
                "pending_hours": "Submitted staff hours awaiting management approval.",
                "pool_readings_current": "Locations whose latest water reading is no more than 24 hours old.",
                "enquiry_mix": "Current workflow status for every public lesson enquiry in the database.",
            },
            "term_calendar": term_context,
        }


@app.get("/api/admin/locations")
def admin_locations(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        locations = []
        today_weekday = business_today().weekday()
        term_context = public_term_context(db)
        for location in db.execute("SELECT * FROM locations ORDER BY name"):
            reading = db.execute(
                "SELECT temperature,status,note,source,created_at FROM pool_readings WHERE location_id=? ORDER BY created_at DESC LIMIT 1",
                (location["id"],),
            ).fetchone()
            checklist = db.execute(
                "SELECT created_at,deck_safe,first_aid_ready,equipment_ready,water_checked FROM pool_checklists WHERE location_id=? ORDER BY created_at DESC LIMIT 1",
                (location["id"],),
            ).fetchone()
            today_classes = rows(db.execute(
                "SELECT code,title,start_time,duration_minutes FROM classes WHERE active=1 AND location_id=? AND weekday=? ORDER BY start_time",
                (location["id"], today_weekday),
            )) if term_context["in_session"] else []
            locations.append({
                **dict(location),
                "latest_reading": dict(reading) if reading else None,
                "latest_checklist": dict(checklist) if checklist else None,
                "today_classes": today_classes,
            })
        return {"locations": locations, "term_calendar": term_context, "source": "HV Swim operational database", "generated_at": now_iso()}


@app.patch("/api/admin/locations/{location_id}")
def update_admin_location(location_id: int, payload: LocationUpdateInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        location = db.execute("SELECT id,slug,name FROM locations WHERE id=?", (location_id,)).fetchone()
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")
        db.execute(
            "UPDATE locations SET public_status=?,venue_type=?,parking=?,accessibility=? WHERE id=?",
            (payload.public_status, payload.venue_type, payload.parking, payload.accessibility, location_id),
        )
        audit(db, user["id"], "update_public_location", "location", location_id, {"slug": location["slug"], "fields": ["public_status", "venue_type", "parking", "accessibility"]}, client_ip(request))
        return {"saved": True, "id": location_id, "name": location["name"]}


@app.get("/api/admin/alerts")
def admin_alerts(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        query = """SELECT a.*,COALESCE(l.name,'All HV Swim locations') location_name,
                          TRIM(publisher.first_name || ' ' || publisher.last_name) published_by_name,
                          TRIM(updater.first_name || ' ' || updater.last_name) updated_by_name,
                          TRIM(COALESCE(resolver.first_name,'') || ' ' || COALESCE(resolver.last_name,'')) resolved_by_name
                   FROM public_alerts a LEFT JOIN locations l ON l.id=a.location_id
                   JOIN users publisher ON publisher.id=a.published_by
                   JOIN users updater ON updater.id=a.updated_by
                   LEFT JOIN users resolver ON resolver.id=a.resolved_by
                   ORDER BY CASE a.status WHEN 'active' THEN 0 ELSE 1 END,a.updated_at DESC,a.id DESC"""
        alerts = rows(db.execute(query))
        return {
            "alerts": alerts,
            "summary": {"active": sum(1 for item in alerts if item["status"] == "active"), "resolved": sum(1 for item in alerts if item["status"] == "resolved")},
            "delivery_boundary": {"website_polling": "live", "email": "not_implemented", "push": "not_implemented"},
        }


@app.post("/api/admin/alerts")
def create_admin_alert(
    payload: PublicAlertInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        if payload.location_id is not None and not db.execute("SELECT id FROM locations WHERE id=?", (payload.location_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Location not found")
        published_at = now_iso()
        alert_id = db.execute(
            """INSERT INTO public_alerts
               (severity,title,message,location_id,status,source,published_by,published_at,updated_by,updated_at)
               VALUES(?,?,?,?,'active','manual',?,?,?,?)""",
            (payload.severity, payload.title.strip(), payload.message.strip(), payload.location_id, user["id"], published_at, user["id"], published_at),
        ).lastrowid
        db.execute(
            """INSERT INTO notifications(audience_role,title,message,kind,delivery_channels,created_at)
               VALUES('customer',?,?, 'alert','[\"in_app\"]',?)""",
            (payload.title.strip(), payload.message.strip(), published_at),
        )
        audit(
            db, user["id"], "create_public_alert", "public_alert", alert_id,
            {"severity": payload.severity, "location_id": payload.location_id, "source": "manual"}, client_ip(request),
        )
        return {
            "created": True, "alert": public_alert_record(db, alert_id),
            "delivery": {"website_polling": "live", **delivery_boundary(in_app_delivered=True)},
        }


@app.post("/api/admin/alerts/{alert_id}/resolve")
def resolve_admin_alert(
    alert_id: int,
    payload: PublicAlertResolveInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        alert = db.execute("SELECT id,severity,title,location_id,status FROM public_alerts WHERE id=?", (alert_id,)).fetchone()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        if alert["status"] == "resolved":
            raise HTTPException(status_code=409, detail="This alert has already been resolved")
        resolved_at = now_iso()
        db.execute(
            """UPDATE public_alerts SET status='resolved',resolved_by=?,resolved_at=?,resolution_note=?,updated_by=?,updated_at=?
               WHERE id=?""",
            (user["id"], resolved_at, payload.reason.strip(), user["id"], resolved_at, alert_id),
        )
        db.execute(
            """INSERT INTO notifications(audience_role,title,message,kind,delivery_channels,created_at)
               VALUES('customer',?,?, 'alert','[\"in_app\"]',?)""",
            (f"Resolved · {alert['title']}", payload.reason.strip(), resolved_at),
        )
        audit(
            db, user["id"], "resolve_public_alert", "public_alert", alert_id,
            {"severity": alert["severity"], "location_id": alert["location_id"], "reason": payload.reason.strip()}, client_ip(request),
        )
        return {
            "resolved": True, "alert_id": alert_id, "resolved_at": resolved_at,
            "delivery": {"website_polling": "live", **delivery_boundary(in_app_delivered=True)},
        }


@app.get("/api/admin/exports/enquiries.csv")
def export_enquiries(request: Request, user: dict[str, Any] = Depends(require_roles("admin"))) -> Response:
    with db_session() as db:
        records = rows(db.execute("SELECT created_at,enquiry_type,name,email,phone,swimmer_name,swimmer_age,program_interest,preferred_class,preferred_days,contact_method,status,experience FROM enquiries ORDER BY created_at DESC"))
        audit(db, user["id"], "export_enquiries", "export", "hv-swim-enquiries.csv", {"record_count": len(records)}, client_ip(request))
    return csv_download(
        "hv-swim-enquiries.csv",
        ["Created", "Type", "Contact", "Email", "Phone", "Swimmer", "Swimmer age", "Program", "Preferred class", "Preferred days", "Contact method", "Status", "Experience"],
        [[item["created_at"], item["enquiry_type"], item["name"], item["email"], item["phone"], item["swimmer_name"], item["swimmer_age"], item["program_interest"], item["preferred_class"], item["preferred_days"], item["contact_method"], item["status"], item["experience"]] for item in records],
    )


@app.get("/api/admin/exports/products.csv")
def export_products(request: Request, user: dict[str, Any] = Depends(require_roles("admin"))) -> Response:
    with db_session() as db:
        records = rows(db.execute("""SELECT sku,title,category,audience,price_cents,cost_cents,status,sample_status,sizes,
                                            supplier_route,fulfilment_mode,shopify_gid,printify_product_id,supplier_reference
                                     FROM products ORDER BY category,title"""))
        audit(db, user["id"], "export_products", "export", "hv-swim-merchandise.csv", {"record_count": len(records)}, client_ip(request))
    return csv_download(
        "hv-swim-merchandise.csv",
        ["SKU", "Product", "Category", "Audience", "Retail price AUD", "Cost AUD", "Status", "Sample", "Sizes", "Supplier route", "Fulfilment", "Shopify GID", "Printify product ID", "Supplier reference"],
        [[item["sku"], item["title"], item["category"], item["audience"], f'{item["price_cents"] / 100:.2f}', "" if item["cost_cents"] is None else f'{item["cost_cents"] / 100:.2f}', item["status"], item["sample_status"], item["sizes"], item["supplier_route"], item["fulfilment_mode"], item["shopify_gid"], item["printify_product_id"], item["supplier_reference"]] for item in records],
    )


@app.get("/api/admin/exports/timesheets.csv")
def export_timesheets(request: Request, user: dict[str, Any] = Depends(require_roles("admin"))) -> Response:
    with db_session() as db:
        query = """SELECT u.first_name,u.last_name,t.clock_in,t.clock_out,l.name location_name,t.hours,t.status,t.approved_at
                   FROM time_entries t JOIN users u ON u.id=t.staff_id JOIN locations l ON l.id=t.location_id
                   ORDER BY t.clock_in DESC"""
        records = rows(db.execute(query))
        audit(db, user["id"], "export_timesheets", "export", "hv-swim-timesheets.csv", {"record_count": len(records)}, client_ip(request))
    return csv_download(
        "hv-swim-timesheets.csv",
        ["Staff", "Shift start", "Shift finish", "Location", "Hours", "Status", "Approved at"],
        [[f'{item["first_name"]} {item["last_name"]}'.strip(), item["clock_in"], item["clock_out"], item["location_name"], item["hours"], item["status"], item["approved_at"]] for item in records],
    )


@app.get("/api/admin/site-settings")
def admin_site_settings(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        return {
            "settings": site_settings_payload(db),
            "feature_controls": public_feature_controls(db),
            "confirmed_business": {
                "legal_name": "HVS BENDIGO PTY LTD",
                "abn": "46 687 937 962",
                "email": "bendigo@hvswimschool.com",
                "complaints_contacts": "Paul and Laura Smith",
                "lesson_fee": "$22.50 per lesson · term billing",
                "clock_tracking": "Not used",
            },
        }


@app.get("/api/admin/association-badges")
def admin_association_badges(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        credentials = association_badge_records(db)
        for item in credentials:
            item["admin_artwork_url"] = (
                f"/api/admin/association-badges/{item['key']}/artwork.png?v={item['artwork_sha256'][:16]}"
                if item["artwork_available"] else None
            )
        return {"credentials": credentials, "feature_control": public_feature_controls(db)["association_badges"]}


@app.get("/api/admin/association-badges/{credential_key}/artwork.png")
def admin_association_badge_artwork(credential_key: str, user: dict[str, Any] = Depends(require_roles("admin"))) -> FileResponse:
    with db_session() as db:
        record = next((item for item in association_badge_records(db) if item["key"] == credential_key), None)
        if not record or not record["artwork_available"]:
            raise HTTPException(status_code=404)
        artwork_path = association_artwork_path(record["artwork_filename"])
        if not artwork_path or not artwork_path.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(artwork_path, media_type="image/png")


@app.patch("/api/admin/association-badges/{credential_key}")
def update_admin_association_badge(
    credential_key: str,
    payload: AssociationCredentialInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    if credential_key not in ASSOCIATION_BADGE_KEYS:
        raise HTTPException(status_code=404, detail="Association credential not found")

    artwork_filename = artwork_sha256 = None
    dimensions: tuple[int, int] | None = None
    if payload.artwork_png_base64 is not None:
        artwork, width, height, artwork_sha256 = validate_association_png(payload.artwork_png_base64)
        ASSOCIATION_BADGE_DIR.mkdir(parents=True, exist_ok=True)
        artwork_filename = f"{credential_key}-{artwork_sha256[:16]}.png"
        temporary_path = ASSOCIATION_BADGE_DIR / f".{artwork_filename}.{new_token(6)}.tmp"
        temporary_path.write_bytes(artwork)
        temporary_path.replace(ASSOCIATION_BADGE_DIR / artwork_filename)
        dimensions = (width, height)

    with db_session() as db:
        existing = db.execute("SELECT key FROM association_credentials WHERE key=?", (credential_key,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Association credential not found")
        if artwork_filename:
            db.execute(
                """UPDATE association_credentials
                   SET membership_reference=?,valid_until=?,usage_rights_confirmed=?,internal_notes=?,
                       artwork_filename=?,artwork_sha256=?,verified_by=?,verified_at=?,updated_at=?
                   WHERE key=?""",
                (
                    payload.membership_reference or None,
                    payload.valid_until.isoformat() if payload.valid_until else None,
                    int(payload.usage_rights_confirmed),
                    payload.internal_notes or None,
                    artwork_filename,
                    artwork_sha256,
                    user["id"],
                    now_iso(),
                    now_iso(),
                    credential_key,
                ),
            )
        else:
            db.execute(
                """UPDATE association_credentials
                   SET membership_reference=?,valid_until=?,usage_rights_confirmed=?,internal_notes=?,
                       verified_by=?,verified_at=?,updated_at=? WHERE key=?""",
                (
                    payload.membership_reference or None,
                    payload.valid_until.isoformat() if payload.valid_until else None,
                    int(payload.usage_rights_confirmed),
                    payload.internal_notes or None,
                    user["id"],
                    now_iso(),
                    now_iso(),
                    credential_key,
                ),
            )
        updated = next(item for item in association_badge_records(db) if item["key"] == credential_key)
        audit(
            db,
            user["id"],
            "verify_association_credential",
            "association_credential",
            credential_key,
            {
                "ready": updated["ready"],
                "valid_until": updated["valid_until"],
                "usage_rights_confirmed": updated["usage_rights_confirmed"],
                "artwork_sha256": artwork_sha256,
                "artwork_dimensions": dimensions,
            },
            client_ip(request),
        )
        updated["admin_artwork_url"] = (
            f"/api/admin/association-badges/{credential_key}/artwork.png?v={updated['artwork_sha256'][:16]}"
            if updated["artwork_available"] else None
        )
        return {"saved": True, "credential": updated, "feature_control": public_feature_controls(db)["association_badges"]}


@app.patch("/api/admin/site-settings")
def update_site_settings(payload: SiteSettingsInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    values = payload.model_dump()
    values["announcement_enabled"] = "1" if values["announcement_enabled"] else "0"
    with db_session() as db:
        feature_controls = public_feature_controls(db)
        if payload.feature_merch_home and not feature_controls["merch_home"]["can_enable"]:
            raise HTTPException(status_code=409, detail=feature_controls["merch_home"]["reason"])
        if payload.feature_association_badges and not feature_controls["association_badges"]["can_enable"]:
            raise HTTPException(status_code=409, detail=feature_controls["association_badges"]["reason"])
        values["feature_merch_home"] = "1" if payload.feature_merch_home else "0"
        values["feature_association_badges"] = "1" if payload.feature_association_badges else "0"
        for key, value in values.items():
            db.execute("INSERT INTO site_settings(key,value,updated_by,updated_at) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_by=excluded.updated_by,updated_at=excluded.updated_at", (key, str(value), user["id"], now_iso()))
        audit(db, user["id"], "update_public_website", "site_settings", "homepage", {"fields": list(values)}, client_ip(request))
        return {"saved": True, "settings": site_settings_payload(db), "feature_controls": public_feature_controls(db)}


@app.get("/api/admin/enquiries")
def admin_enquiries(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        query = """SELECT e.*, u.first_name AS owner_first, u.last_name AS owner_last
                   FROM enquiries e LEFT JOIN users u ON u.id=e.assigned_to
                   ORDER BY CASE e.status WHEN 'new' THEN 0 WHEN 'contacted' THEN 1 WHEN 'trial_booked' THEN 2 ELSE 3 END,e.created_at DESC LIMIT 250"""
        return {"enquiries": rows(db.execute(query)), "owners": rows(db.execute(
            "SELECT id,first_name,last_name FROM users WHERE active=1 AND role='admin' ORDER BY first_name,last_name"
        )), "limit": 250}


@app.patch("/api/admin/enquiries/{enquiry_id}")
def update_enquiry(enquiry_id: int, payload: EnquiryStatusInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        enquiry = db.execute("SELECT * FROM enquiries WHERE id=?", (enquiry_id,)).fetchone()
        if not enquiry:
            raise HTTPException(status_code=404, detail="Enquiry not found")
        if payload.assigned_to is not None and not db.execute(
            "SELECT id FROM users WHERE id=? AND role='admin' AND active=1", (payload.assigned_to,)
        ).fetchone():
            raise HTTPException(status_code=422, detail="Choose an active management owner")
        if payload.status == "trial_booked" and enquiry["enquiry_type"] not in {"lesson", "lesson_question", "private_lesson"}:
            raise HTTPException(status_code=422, detail="Only lesson enquiries can have a trial booked")
        next_action = "none" if payload.status == "closed" else payload.next_action
        follow_up = None if payload.status == "closed" or payload.follow_up_on is None else payload.follow_up_on.isoformat()
        changed = db.execute(
            "UPDATE enquiries SET status=?,assigned_to=?,next_action=?,follow_up_on=?,revision=revision+1 WHERE id=? AND revision=?",
            (payload.status, payload.assigned_to, next_action, follow_up, enquiry_id, payload.revision),
        )
        if changed.rowcount != 1:
            raise HTTPException(status_code=409, detail="Another manager updated this enquiry. Reload the inbox before saving again.")
        audit(db, user["id"], "update_enquiry_status", "enquiry", enquiry_id, {
            "from": enquiry["status"], "to": payload.status, "assigned_to": payload.assigned_to,
            "next_action": next_action, "follow_up_on": follow_up, "revision": payload.revision + 1,
        }, client_ip(request))
        return {"saved": True, "id": enquiry_id, "status": payload.status, "revision": payload.revision + 1}


@app.get("/api/admin/staff")
def admin_staff(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        query = """SELECT u.id,u.email,u.first_name,u.last_name,u.phone,u.role,u.active,u.staff_number,
                          u.shopify_customer_gid,u.xero_employee_id,u.xero_payroll_calendar_id,
                   (SELECT COUNT(*) FROM qualifications q WHERE q.staff_id=u.id AND (q.status='expiring' OR q.expiry_date<=?)) expiring_qualifications
                   FROM users u WHERE u.role IN ('staff','admin') ORDER BY u.first_name,u.last_name"""
        cutoff = (business_today() + timedelta(days=60)).isoformat()
        return {"staff": rows(db.execute(query, (cutoff,)))}


@app.get("/api/admin/accounts")
def admin_accounts(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        query = """SELECT u.id,u.email,u.role,u.first_name,u.last_name,u.phone,u.active,u.created_at,
                          u.customer_number,u.staff_number,u.xero_contact_id,u.shopify_customer_gid,
                          u.xero_employee_id,u.xero_payroll_calendar_id,
                          (SELECT COUNT(*) FROM swimmers s WHERE s.customer_id=u.id AND s.active=1) swimmer_count,
                          (SELECT COUNT(*) FROM bookings b JOIN swimmers s ON s.id=b.swimmer_id
                           WHERE s.customer_id=u.id AND b.status='confirmed') active_booking_count,
                          (SELECT COUNT(*) FROM billing_invoices bi WHERE bi.customer_id=u.id) invoice_count,
                          (SELECT COALESCE(SUM(bi.amount_due_cents),0) FROM billing_invoices bi
                           WHERE bi.customer_id=u.id AND bi.status NOT IN ('draft','paid','voided')) outstanding_cents,
                          (SELECT COALESCE(SUM(lc.amount_cents),0) FROM lesson_charges lc
                           LEFT JOIN billing_invoice_lines bil ON bil.lesson_charge_id=lc.id
                           WHERE lc.customer_id=u.id AND lc.status='pending_xero_invoice' AND bil.id IS NULL) unbilled_cents,
                          (SELECT MAX(ses.created_at) FROM sessions ses WHERE ses.user_id=u.id) last_session_at
                   FROM users u ORDER BY u.active DESC,u.role,u.first_name,u.last_name"""
        return {"accounts": rows(db.execute(query))}


@app.patch("/api/admin/customers/{customer_id}/integration-mapping")
def update_customer_integration_mapping(
    customer_id: int,
    payload: CustomerIntegrationMappingInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        customer = db.execute(
            "SELECT id,customer_number FROM users WHERE id=? AND role='customer' AND active=1",
            (customer_id,),
        ).fetchone()
        if not customer:
            raise HTTPException(status_code=404, detail="Active family account not found")
        try:
            db.execute(
                "UPDATE users SET xero_contact_id=?,shopify_customer_gid=? WHERE id=?",
                (payload.xero_contact_id or None, payload.shopify_customer_gid or None, customer_id),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="That Xero or Shopify customer record is already linked to another family") from exc
        audit(
            db,
            user["id"],
            "update_customer_integration_mapping",
            "user",
            customer_id,
            {
                "customer_number": customer["customer_number"],
                "xero_contact_mapped": bool(payload.xero_contact_id),
                "shopify_customer_mapped": bool(payload.shopify_customer_gid),
            },
            client_ip(request),
        )
        return {
            "saved": True,
            "customer_number": customer["customer_number"],
            "xero_contact_mapped": bool(payload.xero_contact_id),
            "shopify_customer_mapped": bool(payload.shopify_customer_gid),
            "transmission": "none",
        }


@app.post("/api/admin/accounts")
def create_admin_account(payload: AdminUserInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    email = str(payload.email).lower().strip()
    if settings.production and email.endswith("@hvswim.demo"):
        raise HTTPException(status_code=400, detail="Demo-domain accounts cannot be created in production")
    with db_session() as db:
        try:
            cursor = db.execute(
                """INSERT INTO users(email,password_hash,role,first_name,last_name,phone,must_change_password,created_at)
                   VALUES(?,?,?,?,?,?,1,?)""",
                (email, password_hash(payload.temporary_password), payload.role, payload.first_name.strip(), payload.last_name.strip(), payload.phone.strip(), now_iso()),
            )
            if payload.role == "customer":
                db.execute(
                    "UPDATE users SET customer_number=printf('HVS-%06d',id) WHERE id=?",
                    (cursor.lastrowid,),
                )
            else:
                db.execute(
                    "UPDATE users SET staff_number=printf('HVS-W-%06d',id) WHERE id=?",
                    (cursor.lastrowid,),
                )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        audit(db, user["id"], "create_account", "user", cursor.lastrowid, {"email": email, "role": payload.role}, client_ip(request))
        return {"id": cursor.lastrowid, "created": True, "email": email, "role": payload.role}


@app.patch("/api/admin/accounts/{account_id}/status")
def update_account_status(account_id: int, payload: AccountStatusInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    if account_id == user["id"] and not payload.active:
        raise HTTPException(status_code=400, detail="You cannot deactivate the account you are currently using")
    with db_session() as db:
        account = db.execute("SELECT id,email,role,active FROM users WHERE id=?", (account_id,)).fetchone()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        if account["role"] == "admin" and account["active"] and not payload.active:
            active_admins = db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]
            if active_admins <= 1:
                raise HTTPException(status_code=409, detail="The final active management account cannot be deactivated")
        db.execute("UPDATE users SET active=? WHERE id=?", (int(payload.active), account_id))
        if not payload.active:
            db.execute("DELETE FROM sessions WHERE user_id=?", (account_id,))
            db.execute("UPDATE account_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL", (now_iso(), account_id))
        audit(
            db,
            user["id"],
            "update_account_status",
            "user",
            account_id,
            {"active": payload.active, "role": account["role"]},
            client_ip(request),
        )
        return {"saved": True, "id": account_id, "active": payload.active}


@app.post("/api/admin/accounts/{account_id}/temporary-password")
def issue_temporary_password(account_id: int, payload: AdminPasswordResetInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    if account_id == user["id"]:
        raise HTTPException(status_code=400, detail="Use Change password for the account you are currently using")
    with db_session() as db:
        account = db.execute("SELECT id,role,active FROM users WHERE id=?", (account_id,)).fetchone()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        if not account["active"]:
            raise HTTPException(status_code=409, detail="Reactivate this account before issuing a temporary password")
        db.execute(
            "UPDATE users SET password_hash=?,must_change_password=1 WHERE id=?",
            (password_hash(payload.temporary_password), account_id),
        )
        db.execute("DELETE FROM sessions WHERE user_id=?", (account_id,))
        db.execute("UPDATE account_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL", (now_iso(), account_id))
        audit(db, user["id"], "issue_temporary_password", "user", account_id, {"role": account["role"]}, client_ip(request))
        return {"saved": True, "id": account_id, "must_change_password": True}


@app.post("/api/admin/swimmers")
def create_admin_swimmer(payload: AdminSwimmerInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        customer = db.execute("SELECT id FROM users WHERE id=? AND role='customer' AND active=1", (payload.customer_id,)).fetchone()
        if not customer:
            raise HTTPException(status_code=404, detail="Active family account not found")
        cursor = db.execute(
            """INSERT INTO swimmers(
                   customer_id,first_name,last_name,date_of_birth,level,emergency_contact,
                   medical_notes,allergies,medications,support_notes,photo_consent,created_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                payload.customer_id, payload.first_name.strip(), payload.last_name.strip(),
                payload.date_of_birth.isoformat() if payload.date_of_birth else None,
                payload.level, encrypt_sensitive(payload.emergency_contact.strip()), encrypt_sensitive(payload.medical_notes.strip()),
                encrypt_sensitive(payload.allergies.strip()), encrypt_sensitive(payload.medications.strip()), encrypt_sensitive(payload.support_notes.strip()),
                int(payload.photo_consent), now_iso(),
            ),
        )
        db.execute(
            "UPDATE swimmers SET swimmer_number=printf('HVS-S-%06d',id) WHERE id=?",
            (cursor.lastrowid,),
        )
        audit(db, user["id"], "create_swimmer", "swimmer", cursor.lastrowid, {"customer_id": payload.customer_id}, client_ip(request))
        return {"id": cursor.lastrowid, "created": True}


@app.patch("/api/admin/staff/{staff_id}/xero-mapping")
def update_xero_staff_mapping(staff_id: int, payload: XeroStaffMappingInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        staff = db.execute("SELECT id FROM users WHERE id=? AND role IN ('staff','admin') AND active=1", (staff_id,)).fetchone()
        if not staff:
            raise HTTPException(status_code=404, detail="Active staff account not found")
        try:
            db.execute(
                "UPDATE users SET xero_employee_id=?,xero_payroll_calendar_id=?,shopify_customer_gid=? WHERE id=?",
                (payload.employee_id or None, payload.payroll_calendar_id or None, payload.shopify_customer_gid or None, staff_id),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="That Shopify customer record is already linked to another person") from exc
        audit(
            db, user["id"], "update_xero_staff_mapping", "user", staff_id,
            {"employee_mapped": bool(payload.employee_id), "calendar_mapped": bool(payload.payroll_calendar_id), "shopify_staff_customer_mapped": bool(payload.shopify_customer_gid)},
            client_ip(request),
        )
        return {
            "saved": True, "staff_id": staff_id, "employee_mapped": bool(payload.employee_id),
            "calendar_mapped": bool(payload.payroll_calendar_id), "shopify_staff_customer_mapped": bool(payload.shopify_customer_gid),
            "transmission": "none",
        }


@app.get("/api/admin/enrolments")
def admin_enrolments(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        term_context = public_term_context(db)
        class_query = """SELECT c.id,c.code,c.title,c.level,c.weekday,c.start_time,c.duration_minutes,c.capacity,c.price_cents,
                         l.name location_name,l.slug location_slug,u.first_name instructor_first,u.last_name instructor_last,
                         (SELECT COUNT(*) FROM bookings b WHERE b.class_id=c.id AND b.status='confirmed') enrolled,
                         (SELECT COUNT(*) FROM waitlist w WHERE w.class_id=c.id AND w.status='waiting') waiting
                         FROM classes c JOIN locations l ON l.id=c.location_id LEFT JOIN users u ON u.id=c.instructor_id
                         WHERE c.active=1 ORDER BY c.weekday,c.start_time"""
        classes = []
        for row in db.execute(class_query):
            item = dict(row)
            item["available"] = max(0, item["capacity"] - item["enrolled"])
            item["utilisation"] = round(100 * item["enrolled"] / max(1, item["capacity"]), 1)
            item["is_today"] = term_context["in_session"] and item["weekday"] == business_today().weekday()
            classes.append(item)
        waitlist_query = """SELECT w.id,w.position,w.status,w.created_at,c.id class_id,c.code,c.title,c.weekday,c.start_time,c.capacity,
                            s.id swimmer_id,s.first_name swimmer_first,s.last_name swimmer_last,u.id customer_id,
                            u.first_name customer_first,u.last_name customer_last,u.email customer_email,u.phone customer_phone,
                            l.name location_name,
                            (SELECT COUNT(*) FROM bookings b WHERE b.class_id=c.id AND b.status='confirmed') enrolled
                            FROM waitlist w JOIN classes c ON c.id=w.class_id JOIN swimmers s ON s.id=w.swimmer_id
                            JOIN users u ON u.id=s.customer_id JOIN locations l ON l.id=c.location_id
                            WHERE w.status='waiting' ORDER BY c.weekday,c.start_time,w.position"""
        waiting = rows(db.execute(waitlist_query))
        return {
            "generated_at": now_iso(),
            "source": {"name": "HV Swim operational database", "mode": "Local SQLite preview"},
            "summary": {
                "active_classes": len(classes),
                "confirmed_places": sum(item["enrolled"] for item in classes),
                "open_places": sum(item["available"] for item in classes),
                "waitlisted_swimmers": len(waiting),
                "classes_today": sum(1 for item in classes if item["is_today"]),
            },
            "classes": classes,
            "waitlist": waiting,
            "term_calendar": term_context,
        }


@app.get("/api/admin/term-operations")
def admin_term_operations(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        terms = rows(db.execute(
            """SELECT t.*,TRIM(COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'')) created_by_name,
                      (SELECT COUNT(*) FROM absence_reports a WHERE a.term_id=t.id) absence_reports,
                      (SELECT COUNT(*) FROM absence_reports a WHERE a.term_id=t.id AND a.credit_status='credited') credits_recorded
               FROM school_terms t LEFT JOIN users u ON u.id=t.created_by
               ORDER BY t.start_date DESC,t.id DESC"""
        ))
        absences = rows(db.execute(
            """SELECT a.id,a.occurrence_date,a.reason_category,a.credit_status,a.reported_at,
                      s.first_name swimmer_first,s.last_name swimmer_last,c.title,c.code,c.start_time,
                      l.name location_name,t.name term_name,u.first_name customer_first,u.last_name customer_last
               FROM absence_reports a JOIN bookings b ON b.id=a.booking_id JOIN swimmers s ON s.id=b.swimmer_id
               JOIN users u ON u.id=s.customer_id JOIN classes c ON c.id=b.class_id JOIN locations l ON l.id=c.location_id
               JOIN school_terms t ON t.id=a.term_id ORDER BY a.occurrence_date DESC,a.id DESC LIMIT 250"""
        ))
        attendance = rows(db.execute(
            """SELECT la.occurrence_date,la.attendance_status,COUNT(*) count
               FROM lesson_attendance la GROUP BY la.occurrence_date,la.attendance_status
               ORDER BY la.occurrence_date DESC"""
        ))
        current = public_term_context(db)
        return {
            "terms": terms,
            "active_term": current,
            "absences": absences,
            "attendance_summary": attendance,
            "policy": {
                "lesson_price_cents": 2250,
                "absence_credit_default": 2,
                "make_up_classes": False,
                "mid_term_refunds": False,
                "parent_onsite_exception": "Stroke Development",
                "payment_route": "xero_invoice_workflow",
            },
        }


@app.post("/api/admin/terms")
def create_school_term(payload: SchoolTermInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        if payload.activate:
            db.execute("UPDATE school_terms SET status='closed',updated_at=? WHERE status='active'", (now_iso(),))
        status_value = "active" if payload.activate else "draft"
        cursor = db.execute(
            """INSERT INTO school_terms(
                   name,start_date,end_date,absence_credit_limit,status,source,created_by,created_at,updated_at
               ) VALUES(?,?,?,?,?,'management',?,?,?)""",
            (
                payload.name,
                payload.start_date.isoformat(),
                payload.end_date.isoformat(),
                payload.absence_credit_limit,
                status_value,
                user["id"],
                now_iso(),
                now_iso(),
            ),
        )
        audit(
            db, user["id"], "create_school_term", "school_term", cursor.lastrowid,
            {**payload.model_dump(mode="json"), "status": status_value}, client_ip(request),
        )
        return {"id": cursor.lastrowid, "created": True, "status": status_value}


@app.post("/api/admin/terms/{term_id}/activate")
def activate_school_term(term_id: int, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        term = db.execute("SELECT * FROM school_terms WHERE id=?", (term_id,)).fetchone()
        if not term:
            raise HTTPException(status_code=404, detail="School term not found")
        if term["status"] == "active":
            return {"id": term_id, "status": "active", "changed": False}
        changed_at = now_iso()
        db.execute("UPDATE school_terms SET status='closed',updated_at=? WHERE status='active'", (changed_at,))
        db.execute("UPDATE school_terms SET status='active',source='management',updated_at=? WHERE id=?", (changed_at, term_id))
        audit(
            db, user["id"], "activate_school_term", "school_term", term_id,
            {"name": term["name"], "start_date": term["start_date"], "end_date": term["end_date"]},
            client_ip(request),
        )
        return {"id": term_id, "status": "active", "changed": True}


@app.post("/api/admin/waitlist/{waitlist_id}/action")
def admin_waitlist_action(waitlist_id: int, payload: WaitlistActionInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        # Same read-then-write gap as create_booking: lock before checking capacity.
        db.execute("BEGIN IMMEDIATE")
        entry = db.execute(
            """SELECT w.*,c.title,c.capacity,c.weekday,c.price_cents,s.first_name swimmer_first,s.customer_id
               FROM waitlist w JOIN classes c ON c.id=w.class_id JOIN swimmers s ON s.id=w.swimmer_id
               WHERE w.id=? AND w.status='waiting'""",
            (waitlist_id,),
        ).fetchone()
        if not entry:
            raise HTTPException(status_code=404, detail="Active waitlist entry not found")
        if payload.action == "remove":
            db.execute("UPDATE waitlist SET status='removed' WHERE id=?", (waitlist_id,))
            renumber_waitlist(db, entry["class_id"])
            audit(db, user["id"], "remove_waitlist_entry", "waitlist", waitlist_id, {"class_id": entry["class_id"], "swimmer_id": entry["swimmer_id"]}, client_ip(request))
            return {"status": "removed", "waitlist_id": waitlist_id}
        enrolled = db.execute("SELECT COUNT(*) FROM bookings WHERE class_id=? AND status='confirmed'", (entry["class_id"],)).fetchone()[0]
        if enrolled >= entry["capacity"]:
            raise HTTPException(status_code=409, detail="This class is still full. Increase capacity or wait for a confirmed place to open.")
        existing = db.execute("SELECT id FROM bookings WHERE class_id=? AND swimmer_id=? AND status='confirmed'", (entry["class_id"], entry["swimmer_id"])).fetchone()
        if existing:
            db.execute("UPDATE waitlist SET status='converted' WHERE id=?", (waitlist_id,))
            booking_id = existing["id"]
        else:
            booking_id = db.execute("INSERT INTO bookings(class_id,swimmer_id,status,created_at) VALUES(?,?,?,?)", (entry["class_id"], entry["swimmer_id"], "confirmed", now_iso())).lastrowid
            db.execute("UPDATE waitlist SET status='converted' WHERE id=?", (waitlist_id,))
        term = active_term(db)
        if not term:
            raise HTTPException(status_code=409, detail="Management must publish an active school term before confirming a lesson place")
        charge = create_xero_lesson_charge(
            db, booking_id=booking_id, customer_id=entry["customer_id"], term=term, swim_class=entry
        )
        renumber_waitlist(db, entry["class_id"])
        db.execute("INSERT INTO notifications(user_id,title,message,kind,delivery_channels,created_at) VALUES(?,?,?,?,?,?)", (entry["customer_id"], "A lesson place is confirmed", f"{entry['swimmer_first']} now has a confirmed place in {entry['title']}.", "booking", '["in_app","email"]', now_iso()))
        audit(db, user["id"], "promote_waitlist_entry", "waitlist", waitlist_id, {"booking_id": booking_id, "class_id": entry["class_id"], "swimmer_id": entry["swimmer_id"], "lesson_charge_reference": charge["reference"], "payment_provider": "xero"}, client_ip(request))
        return {"status": "confirmed", "waitlist_id": waitlist_id, "booking_id": booking_id, "payment": {"provider": "Xero", "reference": charge["reference"], "amount_cents": charge["amount_cents"], "status": charge["status"], "family_customer_number": charge["family_customer_number"], "swimmer_number": charge["swimmer_number"], "xero_contact_mapped": bool(charge["xero_contact_id"])}}


@app.get("/api/admin/timesheets")
def admin_timesheets(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        query = """SELECT t.*,u.first_name,u.last_name,l.name location_name FROM time_entries t
                   JOIN users u ON u.id=t.staff_id JOIN locations l ON l.id=t.location_id
                   ORDER BY CASE t.status WHEN 'submitted' THEN 0 WHEN 'draft' THEN 1 ELSE 2 END,t.clock_in DESC"""
        return {"time_entries": rows(db.execute(query))}


@app.post("/api/admin/timesheets/approve")
def approve_timesheet(payload: ApproveTimesheetInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        return workforce.approve_entry(db, user, payload.entry_id)


@app.post("/api/admin/classes")
def create_class(payload: ClassInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        location = location_by_slug(db, payload.location_slug)
        try:
            cursor = db.execute("INSERT INTO classes(code,title,level,location_id,instructor_id,weekday,start_time,duration_minutes,capacity,price_cents) VALUES(?,?,?,?,?,?,?,?,?,?)", (payload.code.upper(), payload.title, payload.level, location["id"], payload.instructor_id, payload.weekday, payload.start_time, payload.duration_minutes, payload.capacity, payload.price_cents))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Class code already exists")
        audit(db, user["id"], "create_class", "class", cursor.lastrowid, payload.model_dump(mode="json"), client_ip(request))
        return {"id": cursor.lastrowid, "created": True}


@app.post("/api/admin/roster")
def create_roster(payload: RosterInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        location = location_by_slug(db, payload.location_slug)
        staff = db.execute("SELECT id FROM users WHERE id=? AND role IN ('staff','admin') AND active=1", (payload.staff_id,)).fetchone()
        if not staff:
            raise HTTPException(status_code=404, detail="Staff member not found")
        check_roster_conflict(db, payload)
        cursor = db.execute("INSERT INTO rosters(staff_id,location_id,shift_date,start_time,end_time,role_label,status) VALUES(?,?,?,?,?,?,?)", (payload.staff_id, location["id"], payload.shift_date.isoformat(), payload.start_time, payload.end_time, payload.role_label, "published"))
        audit(db, user["id"], "publish_roster_shift", "roster", cursor.lastrowid, payload.model_dump(mode="json"), client_ip(request))
        return {"id": cursor.lastrowid, "published": True}


def check_roster_conflict(db, payload: RosterInput, excluding_id: int = 0) -> None:
    conflict = db.execute(
        """SELECT id FROM rosters WHERE staff_id=? AND shift_date=? AND id!=?
           AND status='published' AND start_time<? AND end_time>? LIMIT 1""",
        (payload.staff_id, payload.shift_date.isoformat(), excluding_id, payload.end_time, payload.start_time),
    ).fetchone()
    if conflict:
        raise HTTPException(status_code=409, detail="This team member already has an overlapping shift. Review the roster before publishing.")


@app.patch("/api/admin/roster/{roster_id}")
def update_roster(roster_id: int, payload: RosterInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute("SELECT * FROM rosters WHERE id=?", (roster_id,)).fetchone()
        if not previous:
            raise HTTPException(status_code=404, detail="Roster shift not found")
        if previous["shift_date"] < business_today().isoformat() or payload.shift_date < business_today():
            raise HTTPException(status_code=409, detail="Past roster shifts are preserved. Use the reviewed timesheet workflow to correct worked hours.")
        location = location_by_slug(db, payload.location_slug)
        if not db.execute("SELECT id FROM users WHERE id=? AND active=1 AND role IN ('staff','admin')", (payload.staff_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Staff member not found")
        check_roster_conflict(db, payload, roster_id)
        db.execute("UPDATE rosters SET staff_id=?,location_id=?,shift_date=?,start_time=?,end_time=?,role_label=? WHERE id=?", (payload.staff_id, location["id"], payload.shift_date.isoformat(), payload.start_time, payload.end_time, payload.role_label, roster_id))
        audit(db, user["id"], "update_roster_shift", "roster", roster_id, {"before": dict(previous), "after": payload.model_dump(mode="json")}, client_ip(request))
        return {"id": roster_id, "saved": True}


@app.post("/api/admin/notifications")
def create_notification(payload: NotificationInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    if not payload.user_id and not payload.audience_role:
        raise HTTPException(status_code=400, detail="Choose a user or audience role")
    if "in_app" not in payload.channels:
        raise HTTPException(status_code=409, detail="In-app delivery must remain selected until an external provider adapter is implemented")
    external_channels = {
        channel: "not_implemented" for channel in payload.channels if channel in {"email", "sms", "push"}
    }
    with db_session() as db:
        cursor = db.execute("INSERT INTO notifications(user_id,audience_role,title,message,kind,delivery_channels,created_at) VALUES(?,?,?,?,?,?,?)", (payload.user_id, payload.audience_role, payload.title, payload.message, payload.kind, json.dumps(payload.channels), now_iso()))
        audit(db, user["id"], "create_notification", "notification", cursor.lastrowid, {"channels": payload.channels, "external_channels": external_channels}, client_ip(request))
        return {"id": cursor.lastrowid, "created": True, "in_app_delivered": True, "external_channels": external_channels}


@app.get("/api/admin/integrations")
def integrations(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        connection_status = {
            row["provider"]: row["status"] for row in db.execute(
                "SELECT provider,status FROM integration_connections WHERE provider IN ('xero','shopify')"
            )
        }
        return {
            "integrations": integration_summary(db),
            "safe_mode": {
                "xero_sync_requested": settings.xero_sync_enabled,
                "payroll_transmission_locked": True,
                "invoice_transmission": "draft_only_with_management_approval_and_complete_configuration",
            },
            "payment_routing": [
                {
                    "category": "Lesson enrolments & term fees",
                    "provider": "Xero",
                    "route": "xero_invoice_workflow",
                    "connection_status": connection_status.get("xero", "not_connected"),
                    "transaction_status": "draft_sync_ready" if settings.xero_sync_enabled and xero_invoice_configuration_ready() else "configuration_required",
                    "boundary": "Management creates and approves the local invoice first. The platform sends only a DRAFT invoice after contact, account-code and tax settings are complete; Xero remains the accounting source of truth.",
                },
                {
                    "category": "Absence credits",
                    "provider": "Xero",
                    "route": "xero_credit_note_workflow",
                    "connection_status": connection_status.get("xero", "not_connected"),
                    "transaction_status": "record_only",
                    "boundary": "The platform records eligibility; it does not create a Xero credit note or change an invoice automatically.",
                },
                {
                    "category": "Merchandise & staff uniforms",
                    "provider": "Shopify",
                    "route": "shopify_checkout",
                    "connection_status": connection_status.get("shopify", "not_connected"),
                    "transaction_status": "gated",
                    "boundary": "Checkout is available only for sampled, approved and mapped products. Shopify owns merchandise payment, refunds and order history; lesson fees never enter this route.",
                },
            ],
        }


@app.get("/api/admin/billing")
def admin_billing(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        invoice_ids = [
            row["id"] for row in db.execute("SELECT id FROM billing_invoices ORDER BY created_at DESC")
        ]
        invoices = [billing_invoice_payload(db, invoice_id) for invoice_id in invoice_ids]
        unbilled = rows(
            db.execute(
                """SELECT lc.id,lc.reference,lc.customer_id,lc.term_id,lc.per_lesson_cents,
                          lc.lesson_count,lc.amount_cents,lc.family_customer_number,lc.swimmer_number,
                          lc.invoice_description,lc.created_at,u.first_name customer_first,
                          u.last_name customer_last,u.email customer_email,u.xero_contact_id,
                          t.name term_name,s.first_name swimmer_first,s.last_name swimmer_last
                   FROM lesson_charges lc JOIN users u ON u.id=lc.customer_id
                   JOIN school_terms t ON t.id=lc.term_id JOIN bookings b ON b.id=lc.booking_id
                   JOIN swimmers s ON s.id=b.swimmer_id
                   LEFT JOIN billing_invoice_lines bil ON bil.lesson_charge_id=lc.id
                   WHERE lc.status='pending_xero_invoice' AND bil.id IS NULL
                   ORDER BY u.first_name,u.last_name,t.start_date,lc.created_at"""
            )
        )
        connection = db.execute(
            "SELECT status,metadata,updated_at FROM integration_connections WHERE provider='xero'"
        ).fetchone()
        outstanding = sum(
            int(invoice["amount_due_cents"])
            for invoice in invoices
            if invoice["status"] not in {"draft", "paid", "voided"}
        )
        return {
            "invoices": invoices,
            "unbilled_charges": unbilled,
            "summary": {
                "draft_count": sum(invoice["status"] == "draft" for invoice in invoices),
                "approval_count": sum(invoice["status"] == "approved" for invoice in invoices),
                "sync_review_count": sum(invoice["status"] == "sync_review" for invoice in invoices),
                "outstanding_cents": outstanding,
                "paid_cents": sum(int(invoice["amount_paid_cents"]) for invoice in invoices),
                "unbilled_cents": sum(int(charge["amount_cents"]) for charge in unbilled),
            },
            "xero": {
                "oauth_configured": xero_ready(),
                "connection_status": connection["status"] if connection else "not_connected",
                "connection_metadata": json.loads(connection["metadata"] or "{}") if connection else {},
                "invoice_configuration_ready": xero_invoice_configuration_ready(),
                "outbound_enabled": settings.xero_sync_enabled,
                "account_code_configured": bool(settings.xero_lesson_account_code),
                "tax_type_configured": bool(settings.xero_lesson_tax_type),
                "line_amount_type": settings.xero_line_amount_type or None,
                "sync_mode": "draft_invoices_only",
            },
            "shopify": {
                "storefront_configured": shopify_ready(),
                "route": "merchandise_checkout_only",
                "order_reconciliation": "requires_approved_shopify_customer_access_and_accounting_connector",
            },
        }


@app.post("/api/admin/billing/invoices")
def create_billing_invoice(
    payload: InvoiceDraftInput,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    placeholders = ",".join("?" for _ in payload.charge_ids)
    with db_session() as db:
        # Serialize the availability check with line insertion so two management clicks
        # cannot invoice the same lesson charge concurrently.
        db.execute("BEGIN IMMEDIATE")
        customer = db.execute(
            """SELECT id,customer_number,xero_contact_id,first_name,last_name,email
               FROM users WHERE id=? AND role='customer' AND active=1""",
            (payload.customer_id,),
        ).fetchone()
        if not customer:
            raise HTTPException(status_code=404, detail="Active family account not found")
        charges = rows(
            db.execute(
                f"""SELECT lc.* FROM lesson_charges lc
                    LEFT JOIN billing_invoice_lines bil ON bil.lesson_charge_id=lc.id
                    WHERE lc.id IN ({placeholders}) AND lc.customer_id=?
                      AND lc.status='pending_xero_invoice' AND bil.id IS NULL
                    ORDER BY lc.id""",
                (*payload.charge_ids, payload.customer_id),
            )
        )
        if len(charges) != len(payload.charge_ids):
            raise HTTPException(
                status_code=409,
                detail="One or more lesson charges are unavailable, already invoiced or belong to another family",
            )
        term_ids = {int(charge["term_id"]) for charge in charges}
        if len(term_ids) != 1:
            raise HTTPException(status_code=409, detail="Create a separate invoice for each school term")
        total = sum(int(charge["amount_cents"]) for charge in charges)
        created_at = now_iso()
        cursor = db.execute(
            """INSERT INTO billing_invoices
               (invoice_number,customer_id,term_id,provider,currency,customer_number,xero_contact_id,
                status,issue_date,due_date,subtotal_cents,total_cents,amount_paid_cents,amount_due_cents,
                management_note,idempotency_key,created_by,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                billing_invoice_number(db),
                payload.customer_id,
                next(iter(term_ids)),
                "xero",
                "AUD",
                customer["customer_number"],
                customer["xero_contact_id"],
                "draft",
                business_today().isoformat(),
                payload.due_date.isoformat(),
                total,
                total,
                0,
                total,
                encrypt_sensitive(payload.management_note),
                f"hv-invoice-{new_token(48)}"[:128],
                user["id"],
                created_at,
                created_at,
            ),
        )
        invoice_id = int(cursor.lastrowid)
        for charge in charges:
            db.execute(
                """INSERT INTO billing_invoice_lines
                   (invoice_id,lesson_charge_id,description,quantity,unit_amount_cents,
                    line_amount_cents,student_number,created_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (
                    invoice_id,
                    charge["id"],
                    charge["invoice_description"],
                    charge["lesson_count"],
                    charge["per_lesson_cents"],
                    charge["amount_cents"],
                    charge["swimmer_number"],
                    created_at,
                ),
            )
        record_billing_event(
            db,
            invoice_id,
            "created",
            from_status=None,
            to_status="draft",
            created_by=user["id"],
            detail={"charge_count": len(charges), "total_cents": total},
        )
        audit(
            db,
            user["id"],
            "create_billing_invoice",
            "billing_invoice",
            invoice_id,
            {"customer_number": customer["customer_number"], "charge_count": len(charges), "total_cents": total},
            client_ip(request),
        )
        return {"created": True, "invoice": billing_invoice_payload(db, invoice_id)}


@app.post("/api/admin/billing/invoices/{invoice_id}/approve")
def approve_billing_invoice(
    invoice_id: int,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        invoice = db.execute(
            """SELECT bi.*,u.xero_contact_id current_xero_contact_id
               FROM billing_invoices bi JOIN users u ON u.id=bi.customer_id WHERE bi.id=?""",
            (invoice_id,),
        ).fetchone()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if invoice["status"] != "draft":
            raise HTTPException(status_code=409, detail="Only a draft invoice can be approved")
        if not invoice["current_xero_contact_id"]:
            raise HTTPException(status_code=409, detail="Map this family to its verified Xero contact before approval")
        line_total = db.execute(
            "SELECT COALESCE(SUM(line_amount_cents),0) FROM billing_invoice_lines WHERE invoice_id=?",
            (invoice_id,),
        ).fetchone()[0]
        if not line_total or int(line_total) != int(invoice["total_cents"]):
            raise HTTPException(status_code=409, detail="Invoice line totals do not match the invoice total")
        changed_at = now_iso()
        updated = db.execute(
            """UPDATE billing_invoices SET status='approved',xero_contact_id=?,approved_by=?,
                      approved_at=?,last_sync_error=NULL,updated_at=? WHERE id=? AND status='draft'""",
            (invoice["current_xero_contact_id"], user["id"], changed_at, changed_at, invoice_id),
        )
        if updated.rowcount != 1:
            raise HTTPException(status_code=409, detail="This invoice changed before it could be approved; reload and review it again")
        record_billing_event(
            db,
            invoice_id,
            "approved",
            from_status="draft",
            to_status="approved",
            created_by=user["id"],
            detail={"xero_contact_mapped": True},
        )
        audit(db, user["id"], "approve_billing_invoice", "billing_invoice", invoice_id, {}, client_ip(request))
        return {"approved": True, "invoice": billing_invoice_payload(db, invoice_id)}


@app.post("/api/admin/billing/invoices/{invoice_id}/sync-xero")
async def sync_billing_invoice_to_xero(
    invoice_id: int,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    if not settings.xero_sync_enabled:
        raise HTTPException(status_code=409, detail="Enable reviewed Xero invoice transmission in the server configuration first")
    if not xero_ready() or not xero_invoice_configuration_ready():
        raise HTTPException(status_code=409, detail="Complete the Xero OAuth, account-code, tax and line-amount configuration first")
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        invoice = billing_invoice_payload(db, invoice_id)
        if invoice["status"] != "approved":
            raise HTTPException(status_code=409, detail="Only an approved invoice can be sent to Xero")
        connection = db.execute(
            "SELECT * FROM integration_connections WHERE provider='xero' AND status='connected'"
        ).fetchone()
        if not connection or not connection["encrypted_tokens"]:
            raise HTTPException(status_code=409, detail="Connect the existing Xero organisation first")
        token = decrypt_json(connection["encrypted_tokens"])
        previous = invoice["status"]
        changed_at = now_iso()
        claimed = db.execute(
            "UPDATE billing_invoices SET status='sync_review',last_sync_error=NULL,updated_at=? WHERE id=? AND status='approved'",
            (changed_at, invoice_id),
        )
        if claimed.rowcount != 1:
            raise HTTPException(status_code=409, detail="This invoice is already being handled; reload its current status")
        record_billing_event(
            db,
            invoice_id,
            "xero_sync_started",
            from_status=previous,
            to_status="sync_review",
            created_by=user["id"],
            detail={"mode": "draft_only"},
        )
    try:
        current_token = await refresh_and_store_xero_token(token)
        refreshed_token, xero_invoice = await xero_create_draft_invoice(current_token, invoice=invoice, lines=invoice["lines"])
    except Exception as exc:
        safe_error = f"{type(exc).__name__}: {str(exc)}"[:500]
        with db_session() as db:
            db.execute(
                "UPDATE billing_invoices SET last_sync_error=?,updated_at=? WHERE id=?",
                (safe_error, now_iso(), invoice_id),
            )
            record_billing_event(
                db,
                invoice_id,
                "xero_sync_requires_review",
                from_status="sync_review",
                to_status="sync_review",
                created_by=user["id"],
                detail={"error_type": type(exc).__name__},
            )
            audit(db, user["id"], "xero_invoice_sync_requires_review", "billing_invoice", invoice_id, {"error_type": type(exc).__name__}, client_ip(request))
        raise HTTPException(
            status_code=502,
            detail="Xero did not confirm the draft invoice. Check Xero before attempting any further action.",
        )
    xero_status = str(xero_invoice.get("Status") or "DRAFT").upper()
    local_status = "synced" if xero_status == "DRAFT" else "sent"
    with db_session() as db:
        db.execute(
            "UPDATE integration_connections SET encrypted_tokens=?,updated_at=? WHERE provider='xero'",
            (encrypt_json(refreshed_token), now_iso()),
        )
        db.execute(
            """UPDATE billing_invoices SET status=?,xero_invoice_id=?,xero_invoice_number=?,
                      xero_status=?,last_sync_error=NULL,synced_at=?,updated_at=? WHERE id=?""",
            (
                local_status,
                xero_invoice.get("InvoiceID"),
                xero_invoice.get("InvoiceNumber"),
                xero_status,
                now_iso(),
                now_iso(),
                invoice_id,
            ),
        )
        db.execute(
            """UPDATE lesson_charges SET status='invoiced',xero_invoice_id=?
               WHERE id IN (SELECT lesson_charge_id FROM billing_invoice_lines WHERE invoice_id=?)""",
            (xero_invoice.get("InvoiceID"), invoice_id),
        )
        record_billing_event(
            db,
            invoice_id,
            "xero_draft_created",
            from_status="sync_review",
            to_status=local_status,
            created_by=user["id"],
            detail={"xero_status": xero_status},
        )
        audit(db, user["id"], "sync_billing_invoice_to_xero", "billing_invoice", invoice_id, {"xero_status": xero_status}, client_ip(request))
        return {"synced": True, "invoice": billing_invoice_payload(db, invoice_id)}


@app.post("/api/admin/billing/invoices/{invoice_id}/refresh-xero")
async def refresh_billing_invoice_from_xero(
    invoice_id: int,
    request: Request,
    user: dict[str, Any] = Depends(require_roles("admin")),
    x_csrf_token: str | None = Header(default=None),
) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        invoice = db.execute("SELECT * FROM billing_invoices WHERE id=?", (invoice_id,)).fetchone()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if not invoice["xero_invoice_id"]:
            raise HTTPException(status_code=409, detail="This invoice has no confirmed Xero invoice ID to refresh")
        connection = db.execute(
            "SELECT * FROM integration_connections WHERE provider='xero' AND status='connected'"
        ).fetchone()
        if not connection or not connection["encrypted_tokens"]:
            raise HTTPException(status_code=409, detail="Reconnect the Xero organisation first")
        token = decrypt_json(connection["encrypted_tokens"])
        previous_status = invoice["status"]
    try:
        current_token = await refresh_and_store_xero_token(token)
        refreshed_token, xero_invoice = await xero_get_invoice(current_token, str(invoice["xero_invoice_id"]))
        amount_paid, amount_due = reconcile_xero_amounts(invoice, xero_invoice)
    except Exception as exc:
        with db_session() as db:
            safe_error = f"{type(exc).__name__}: {str(exc)}"[:500]
            db.execute(
                "UPDATE billing_invoices SET status='sync_review',last_sync_error=?,updated_at=? WHERE id=?",
                (safe_error, now_iso(), invoice_id),
            )
            record_billing_event(
                db,
                invoice_id,
                "xero_refresh_requires_review",
                from_status=previous_status,
                to_status="sync_review",
                created_by=user["id"],
                detail={"error_type": type(exc).__name__},
            )
            audit(
                db,
                user["id"],
                "xero_invoice_refresh_requires_review",
                "billing_invoice",
                invoice_id,
                {"error_type": type(exc).__name__},
                client_ip(request),
            )
        raise HTTPException(status_code=502, detail="Xero status could not be safely reconciled. Review the invoice in Xero before retrying.")
    xero_status = str(xero_invoice.get("Status") or "").upper()
    local_status = {
        "DRAFT": "synced",
        "SUBMITTED": "sent",
        "AUTHORISED": "sent",
        "PAID": "paid",
        "VOIDED": "voided",
        "DELETED": "voided",
    }.get(xero_status, "sync_review")
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "UPDATE integration_connections SET encrypted_tokens=?,updated_at=? WHERE provider='xero'",
            (encrypt_json(refreshed_token), now_iso()),
        )
        db.execute(
            """UPDATE billing_invoices SET status=?,xero_status=?,xero_invoice_number=?,
                      amount_paid_cents=?,amount_due_cents=?,online_invoice_url=?,last_sync_error=NULL,
                      updated_at=? WHERE id=?""",
            (
                local_status,
                xero_status,
                xero_invoice.get("InvoiceNumber"),
                amount_paid,
                amount_due,
                safe_xero_online_invoice_url(xero_invoice.get("OnlineInvoiceUrl")),
                now_iso(),
                invoice_id,
            ),
        )
        charge_status = "paid" if local_status == "paid" else "invoiced"
        db.execute(
            f"""UPDATE lesson_charges SET status=?
                WHERE id IN (SELECT lesson_charge_id FROM billing_invoice_lines WHERE invoice_id=?)""",
            (charge_status, invoice_id),
        )
        record_billing_event(
            db,
            invoice_id,
            "xero_status_refreshed",
            from_status=previous_status,
            to_status=local_status,
            created_by=user["id"],
            detail={"xero_status": xero_status, "amount_due_cents": amount_due},
        )
        audit(db, user["id"], "refresh_billing_invoice_from_xero", "billing_invoice", invoice_id, {"xero_status": xero_status}, client_ip(request))
        return {"refreshed": True, "invoice": billing_invoice_payload(db, invoice_id)}


@app.get("/api/admin/lesson-charges")
def admin_lesson_charges(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        charges = rows(db.execute(
            """SELECT lc.id,lc.reference,lc.provider,lc.per_lesson_cents,lc.lesson_count,lc.amount_cents,
                      lc.family_customer_number,lc.swimmer_number,lc.xero_contact_id,lc.invoice_description,
                      lc.status,lc.xero_invoice_id,lc.created_at,b.id booking_id,
                      s.first_name swimmer_first,s.last_name swimmer_last,c.title class_title,
                      u.first_name customer_first,u.last_name customer_last,u.email customer_email,t.name term_name
               FROM lesson_charges lc JOIN bookings b ON b.id=lc.booking_id
               JOIN swimmers s ON s.id=b.swimmer_id JOIN classes c ON c.id=b.class_id
               JOIN users u ON u.id=lc.customer_id JOIN school_terms t ON t.id=lc.term_id
               ORDER BY lc.created_at DESC"""
        ))
        return {
            "charges": charges,
            "provider": "Xero",
            "transmission": "locked_until_authorised_xero_connection_and_reviewed_test_invoice",
            "card_data_stored": False,
        }


@app.get("/api/integrations/xero/connect")
def connect_xero(user: dict[str, Any] = Depends(require_roles("admin"))):
    if not xero_ready():
        raise HTTPException(status_code=409, detail="Add XERO_CLIENT_ID, XERO_CLIENT_SECRET and XERO_REDIRECT_URI to .env first")
    oauth_state = new_token(24)
    expires = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    with db_session() as db:
        db.execute("INSERT INTO oauth_states(state,provider,user_id,expires_at) VALUES(?,?,?,?)", (oauth_state, "xero", user["id"], expires))
    return RedirectResponse(xero_authorization_url(oauth_state), status_code=302)


@app.get("/api/integrations/xero/callback")
async def xero_callback(code: str, state: str):
    with db_session() as db:
        oauth = db.execute("SELECT * FROM oauth_states WHERE state=? AND provider='xero' AND expires_at>?", (state, now_iso())).fetchone()
        if not oauth:
            raise HTTPException(status_code=400, detail="Xero connection request expired or failed security validation")
        db.execute("DELETE FROM oauth_states WHERE state=?", (state,))
    try:
        token = await xero_exchange_code(code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Xero connection failed: {type(exc).__name__}")
    metadata = {"tenant_id": token.get("tenant_id"), "tenant_name": token.get("tenant_name"), "connected_at": now_iso()}
    with db_session() as db:
        db.execute("UPDATE integration_connections SET status='connected',encrypted_tokens=?,metadata=?,updated_at=? WHERE provider='xero'", (encrypt_json(token), json.dumps(metadata), now_iso()))
        audit(db, oauth["user_id"], "connect_xero", "integration", "xero", metadata)
    return RedirectResponse("/platform.html#integrations", status_code=302)


@app.post("/api/integrations/xero/sync-timesheets")
async def sync_xero_timesheets(request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    """Build a safe payroll-readiness preview without transmitting payroll data.

    Xero AU Payroll timesheets require account-specific pay-period boundaries and staff,
    payroll-calendar and earnings-rate mappings. Those must be imported from the connected
    organisation before an outbound implementation can be made idempotent. Until that
    workflow exists, this endpoint deliberately remains a reviewed dry run even if a legacy
    deployment still has XERO_SYNC_ENABLED=true.
    """
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        connection = db.execute("SELECT * FROM integration_connections WHERE provider='xero' AND status='connected'").fetchone()
        if not connection:
            raise HTTPException(status_code=409, detail="Connect the existing Xero organisation first")
        approved = rows(
            db.execute(
                """SELECT t.id,t.staff_id,t.clock_in,t.clock_out,t.hours,t.break_minutes,
                          u.first_name,u.last_name,u.staff_number,u.xero_employee_id,u.xero_payroll_calendar_id
                   FROM time_entries t JOIN users u ON u.id=t.staff_id
                   WHERE t.status='approved' AND t.xero_timesheet_id IS NULL
                   ORDER BY t.clock_in,t.id"""
            )
        )
        entries = [
            {
                "entry_id": entry["id"],
                "staff_id": entry["staff_id"],
                "staff_number": entry["staff_number"],
                "staff_name": f"{entry['first_name']} {entry['last_name']}".strip(),
                "business_date": business_date_from_timestamp(entry["clock_in"]).isoformat(),
                "hours": entry["hours"],
                "break_minutes": entry["break_minutes"],
                "employee_mapped": bool(entry["xero_employee_id"]),
                "payroll_calendar_mapped": bool(entry["xero_payroll_calendar_id"]),
            }
            for entry in approved
        ]
        missing_staff = [
            {
                "staff_id": entry["staff_id"],
                "staff_name": f"{entry['first_name']} {entry['last_name']}".strip(),
                "employee_id": not bool(entry["xero_employee_id"]),
                "payroll_calendar_id": not bool(entry["xero_payroll_calendar_id"]),
            }
            for entry in approved
            if not entry["xero_employee_id"] or not entry["xero_payroll_calendar_id"]
        ]
        blocking_reasons = []
        if not settings.xero_earnings_rate_id:
            blocking_reasons.append("Xero earnings rate is not mapped")
        if missing_staff:
            blocking_reasons.append("One or more staff payroll mappings are incomplete")
        blocking_reasons.append("Live payroll remains locked: provider-verified pay-period, calendar and earnings-rate import and operator reconciliation are required. The local idempotent adapter is implemented and tested without live transmission.")
        readiness = {
            "organisation_connected": True,
            "approved_entries": len(entries),
            "earnings_rate_mapped": bool(settings.xero_earnings_rate_id),
            "staff_mappings_complete": not missing_staff,
            "pay_period_import_implemented": False,
            "idempotent_export_implemented": True,
            "live_payroll_authorised": False,
        }
        audit(
            db,
            user["id"],
            "preview_xero_timesheets",
            "integration",
            "xero",
            {"approved_entries": len(entries), "blocking_reasons": blocking_reasons},
            client_ip(request),
        )
        return {
            "synced": 0,
            "dry_run": True,
            "transmission_locked": True,
            "readiness": readiness,
            "missing_staff_mappings": missing_staff,
            "blocking_reasons": blocking_reasons,
            "entries": entries,
            "message": "Payroll data was not sent. Complete the Xero mappings and pay-period import before enabling a reviewed live export.",
        }


def product_launch_blockers(product: dict[str, Any]) -> list[str]:
    """Return every gate that prevents a catalogue record becoming a sellable product."""
    blockers: list[str] = []
    route = str(product.get("supplier_route") or "manual_review")
    try:
        sizes = json.loads(product.get("sizes") or "[]") if isinstance(product.get("sizes"), str) else product.get("sizes") or []
    except json.JSONDecodeError:
        sizes = []
    if product.get("sample_status") != "approved":
        blockers.append("Physical sample not approved")
    if product.get("status") not in {"approved", "available"}:
        blockers.append("Launch status not approved")
    if not product.get("price_cents") or product.get("cost_cents") is None:
        blockers.append("Retail price or supplier cost missing")
    if not sizes:
        blockers.append("Final options or sizes missing")
    if not product.get("shopify_gid"):
        blockers.append("Shopify product mapping missing")
    if route == "manual_review":
        blockers.append("Supplier route still requires review")
    elif "printify" in route and not product.get("printify_product_id"):
        blockers.append("Printify product mapping missing")
    elif "printify" not in route and not product.get("supplier_reference"):
        blockers.append("Approved supplier or sample reference missing")
    return blockers


def public_product_view(product: dict[str, Any]) -> dict[str, Any]:
    """Keep supplier costs and private integration mappings out of public responses."""
    private_fields = {"cost_cents", "shopify_gid", "printify_product_id", "supplier_reference"}
    return {key: value for key, value in product.items() if key not in private_fields}


@app.get("/api/products")
async def products() -> dict[str, Any]:
    public_product_query = """SELECT id,sku,title,category,description,price_cents,sizes,status,emoji,
                                     sample_status,supplier_route,personalisation,audience,fulfilment_mode,
                                     cost_cents,shopify_gid,printify_product_id,supplier_reference,
                                     image,image_alt
                              FROM products ORDER BY category,title"""
    if shopify_ready():
        try:
            with db_session() as db:
                local_catalogue = [
                    item for item in rows(db.execute(public_product_query))
                    if item.get("audience") != "staff"
                ]
            approved_by_gid = {
                str(product["shopify_gid"]): product
                for product in local_catalogue
                if product.get("status") == "available" and not product_launch_blockers(product)
            }
            live_products = await shopify_products()
            approved_live = []
            for product in live_products:
                profile = approved_by_gid.get(str(product.get("id")))
                if not profile:
                    continue
                # Shopify remains authoritative for public title, imagery, variants and
                # availability. The locally approved production profile adds only the
                # non-private route/personalisation context used by the shop experience.
                approved_live.append({
                    **product,
                    "supplier_route": profile.get("supplier_route"),
                    "fulfilment_mode": profile.get("fulfilment_mode"),
                    "personalisation": profile.get("personalisation"),
                    "audience": profile.get("audience"),
                    "sample_status": profile.get("sample_status"),
                })
            return {
                "source": "shopify",
                "products": approved_live,
                "payment_route": "shopify_checkout",
                "publication_boundary": "Only locally approved, sampled, costed and mapped products are shown from Shopify.",
            }
        except Exception as exc:
            with db_session() as db:
                fallback = [
                    item for item in rows(db.execute(public_product_query))
                    if item.get("audience") != "staff"
                ]
            return {"source": "local_fallback", "products": [public_product_view(item) for item in fallback], "payment_route": "shopify_checkout_unavailable", "warning": f"Shopify unavailable: {type(exc).__name__}"}
    with db_session() as db:
        local_products = [
            item for item in rows(db.execute(public_product_query))
            if item.get("audience") != "staff"
        ]
        return {"source": "planned_catalogue", "products": [public_product_view(item) for item in local_products], "payment_route": "shopify_checkout_configuration_required"}


@app.get("/api/staff/merchandise")
async def staff_merchandise(user: dict[str, Any] = Depends(require_roles("staff", "admin"))) -> dict[str, Any]:
    """Staff-only uniform catalogue; never exposed by the public product endpoint."""
    query = """SELECT id,sku,title,category,description,price_cents,sizes,status,emoji,
                      sample_status,supplier_route,personalisation,audience,fulfilment_mode,
                      cost_cents,shopify_gid,printify_product_id,supplier_reference
               FROM products WHERE audience='staff' ORDER BY category,title"""
    with db_session() as db:
        staff_products = rows(db.execute(query))
    if shopify_ready():
        try:
            approved_by_gid = {
                str(product["shopify_gid"]): product
                for product in staff_products
                if product.get("status") == "available" and not product_launch_blockers(product)
            }
            approved_live = []
            for product in await shopify_products():
                profile = approved_by_gid.get(str(product.get("id")))
                if not profile:
                    continue
                approved_live.append({
                    **product,
                    "supplier_route": profile.get("supplier_route"),
                    "fulfilment_mode": profile.get("fulfilment_mode"),
                    "personalisation": profile.get("personalisation"),
                    "audience": "staff",
                    "sample_status": profile.get("sample_status"),
                })
            return {
                "source": "shopify",
                "products": approved_live,
                "audience": "staff_only",
                "payment_route": "shopify_checkout",
            }
        except Exception as exc:
            return {
                "source": "local_fallback",
                "products": [public_product_view(item) for item in staff_products],
                "audience": "staff_only",
                "payment_route": "shopify_checkout_unavailable",
                "warning": f"Shopify unavailable: {type(exc).__name__}",
            }
    return {
        "source": "planned_catalogue",
        "products": [public_product_view(item) for item in staff_products],
        "audience": "staff_only",
        "payment_route": "shopify_checkout_configuration_required",
    }


@app.get("/api/admin/merch-production")
async def merch_production(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        catalogue = rows(db.execute("SELECT * FROM products ORDER BY category,title"))
    live_printify = []
    printify_error = None
    if printify_ready():
        try:
            live_printify = await printify_products()
        except Exception as exc:
            printify_error = f"Printify connection unavailable: {type(exc).__name__}"
    live_printify_ids = {str(product.get("id")) for product in live_printify if product.get("id") is not None}
    for product in catalogue:
        route = product.get("supplier_route") or "manual_review"
        route_detail = SUPPLIER_ROUTE_DETAILS.get(route, SUPPLIER_ROUTE_DETAILS["manual_review"])
        product["production"] = {
            "supplier": route,
            "supplier_label": route_detail["label"],
            "automation": route_detail["automation"],
            "boundary": route_detail["boundary"],
            "method": PRODUCT_PRODUCTION_METHODS.get(product["sku"], "Confirm the product specification, supplier and physical sample before launch."),
        }
        product["margin_cents"] = None if product.get("cost_cents") is None else product["price_cents"] - product["cost_cents"]
        product["margin_percent"] = None if product.get("cost_cents") is None or not product["price_cents"] else round((product["price_cents"] - product["cost_cents"]) / product["price_cents"] * 100, 1)
        printify_capable = "printify" in route
        printify_mapping = str(product.get("printify_product_id") or "")
        if not printify_capable:
            printify_status = "not_applicable"
        elif not printify_mapping:
            printify_status = "mapping_required"
        elif not printify_ready():
            printify_status = "mapped_connection_required"
        elif printify_mapping in live_printify_ids:
            printify_status = "connected"
        else:
            printify_status = "mapped_not_found"
        product["sync"] = {
            "shopify": "mapped" if product.get("shopify_gid") else "mapping_required",
            "printify": printify_status,
            "manual_order_reference": "recorded" if product.get("supplier_reference") else "required",
        }
        product["blocking_reasons"] = product_launch_blockers(product)
        product["production_ready"] = not product["blocking_reasons"]
        product["public_ready"] = product["production_ready"] and product.get("status") == "available"

    approved_samples = sum(1 for product in catalogue if product.get("sample_status") == "approved")
    costed_products = sum(1 for product in catalogue if product.get("cost_cents") is not None)
    launchable_products = sum(1 for product in catalogue if product.get("production_ready"))
    public_ready_products = sum(1 for product in catalogue if product.get("public_ready"))
    shopify_mapped = sum(1 for product in catalogue if product.get("shopify_gid"))
    printify_eligible = sum(1 for product in catalogue if "printify" in (product.get("supplier_route") or ""))
    printify_mapped = sum(1 for product in catalogue if "printify" in (product.get("supplier_route") or "") and product.get("printify_product_id"))
    route_summary: dict[str, int] = {}
    audience_summary: dict[str, int] = {}
    for product in catalogue:
        route = product.get("supplier_route") or "manual_review"
        audience = product.get("audience") or "family"
        route_summary[route] = route_summary.get(route, 0) + 1
        audience_summary[audience] = audience_summary.get(audience, 0) + 1
    return {
        "catalogue": catalogue,
        "launch_readiness": {
            "total_products": len(catalogue),
            "approved_samples": approved_samples,
            "costed_products": costed_products,
            "launchable_products": launchable_products,
            "public_ready_products": public_ready_products,
            "readiness_percent": round((approved_samples + costed_products + launchable_products) / (max(len(catalogue), 1) * 3) * 100),
        },
        "sync_readiness": {
            "shopify_mapped_products": shopify_mapped,
            "printify_eligible_products": printify_eligible,
            "printify_mapped_products": printify_mapped,
            "unmapped_shopify_products": len(catalogue) - shopify_mapped,
            "unmapped_printify_products": printify_eligible - printify_mapped,
        },
        "catalogue_summary": {"by_audience": audience_summary, "by_supplier_route": route_summary},
        "providers": {
            "shopify": {"configured": shopify_ready(), "integration_mode": "storefront_api", "role": "Public catalogue, secure checkout, customer orders and inventory"},
            "printify": {"configured": printify_ready(), "integration_mode": "api_to_shopify", "role": "Eligible POD mockups, production and fulfilment after sample approval", "products": live_printify, "error": printify_error},
            "vistaprint": {"configured": False, "integration_mode": "manual_purchase_order", "live_api_supported": False, "role": "Manual quotes and bulk ordering for approved uniforms, bottles and promotional gear", "url": "https://www.vistaprint.com.au/custom-promotional-merch"},
            "specialist_swim": {"configured": False, "integration_mode": "manual_purchase_order", "role": "Chlorine-resistant swimwear and fit/safety-sensitive aquatic equipment"},
            "premium_teamwear": {"configured": False, "integration_mode": "authorised_reseller_manual", "role": "Premium blank garments may be sourced through authorised resellers; no Nike, Puma, Gildan or other brand connection or licence is claimed"},
        },
        "workflow": ["Approve production artwork", "Select supplier and record mapping/reference", "Order physical samples", "Approve sizes, safety and margins", "Publish approved products to Shopify", "Test checkout, fulfilment and returns", "Launch collection"],
        "integration_boundaries": [
            "Shopify is the public system for products, variants, inventory and checkout once credentials are configured.",
            "Printify automation applies only to eligible mapped products after a physical sample is approved.",
            "VistaPrint and specialist suppliers remain manual quote, proof and purchase-order workflows; no VistaPrint API response is fabricated.",
            "Named apparel brands are supplier possibilities only through authorised reseller channels; HV Swim must approve the blank and decoration rights before use.",
        ],
    }


@app.patch("/api/admin/products/{product_id}")
def update_product(product_id: int, payload: ProductUpdateInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        product = db.execute("SELECT id,sku,title,price_cents,status FROM products WHERE id=?", (product_id,)).fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        printify_product_id = payload.printify_product_id if "printify" in payload.supplier_route else ""
        db.execute(
            """UPDATE products
               SET price_cents=?,status=?,sample_status=?,cost_cents=?,supplier_route=?,fulfilment_mode=?,personalisation=?,
                   shopify_gid=CASE WHEN ? IS NULL THEN shopify_gid ELSE NULLIF(?, '') END,
                   printify_product_id=CASE WHEN ? IS NULL THEN printify_product_id ELSE NULLIF(?, '') END,
                   supplier_reference=CASE WHEN ? IS NULL THEN supplier_reference ELSE NULLIF(?, '') END
               WHERE id=?""",
            (
                payload.price_cents, payload.status, payload.sample_status, payload.cost_cents,
                payload.supplier_route, fulfilment_mode_for_route(payload.supplier_route), payload.personalisation,
                payload.shopify_gid, payload.shopify_gid,
                printify_product_id, printify_product_id,
                payload.supplier_reference, payload.supplier_reference,
                product_id,
            ),
        )
        detail = {
            "sku": product["sku"], "price_cents": payload.price_cents, "status": payload.status,
            "sample_status": payload.sample_status, "cost_cents": payload.cost_cents,
            "supplier_route": payload.supplier_route, "fulfilment_mode": fulfilment_mode_for_route(payload.supplier_route),
            "shopify_gid": payload.shopify_gid, "printify_product_id": printify_product_id,
            "supplier_reference": payload.supplier_reference,
        }
        audit(db, user["id"], "update_merchandise_product", "product", product_id, detail, client_ip(request))
        return {"saved": True, "id": product_id, **detail}


@app.post("/api/products/cart")
async def create_cart(payload: CartInput, request: Request, user: dict[str, Any] = Depends(session_user), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    try:
        return {"cart": await shopify_create_cart(payload.variant_id, payload.quantity)}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=502, detail="Shopify cart could not be created")


@app.get("/api/integrations/pool-sensor")
async def sensor(user: dict[str, Any] = Depends(require_roles("staff", "admin"))) -> dict[str, Any]:
    if not settings.pool_sensor_url:
        return {"configured": False, "message": "No pool sensor API has been supplied. Daily staff verification remains active."}
    try:
        return {"configured": True, "reading": await pool_sensor_reading()}
    except Exception:
        raise HTTPException(status_code=502, detail="Configured pool sensor did not respond")


ENQUIRY_LIMIT_PER_HOUR = 5
@app.post("/api/public/enquiries")
def create_enquiry(payload: EnquiryInput, request: Request) -> dict[str, Any]:
    ip = client_ip(request)
    # Bots fill every field they find. Answer as though it worked so they stop retrying,
    # but record nothing.
    if payload.website.strip():
        return {"id": 0, "reference": "HV-ENQ-0000", "received": True, "message": "Thanks — the HV Swim team can now follow up with you."}
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        recent = db.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action='create_enquiry' AND ip_address=? AND created_at>?",
            (ip, cutoff),
        ).fetchone()[0]
        if recent >= ENQUIRY_LIMIT_PER_HOUR:
            raise HTTPException(
                status_code=429,
                detail="We have already received several enquiries from this connection. Please call 0413 462 112 if you need to reach us sooner.",
            )
        cursor = db.execute(
            """INSERT INTO enquiries(enquiry_type,name,email,phone,swimmer_name,swimmer_age,program_interest,preferred_class,preferred_days,contact_method,experience,support_needs,status,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (payload.enquiry_type, payload.name, payload.email, payload.phone, payload.swimmer_name, payload.swimmer_age, payload.program_interest, payload.preferred_class, payload.preferred_days, payload.contact_method, payload.experience, payload.support_needs, "new", now_iso()),
        )
        reference = f"HV-{'MERCH' if payload.enquiry_type == 'merchandise' else 'ENQ'}-{cursor.lastrowid:04d}"
        if payload.enquiry_type == "merchandise":
            title = f"New merchandise enquiry · {reference}"
            message = f"{payload.name} asked about the HV Swim collection."
        elif payload.enquiry_type not in {"lesson", "private_lesson", "lesson_question"}:
            title = f"New {payload.enquiry_type.replace('_', ' ')} enquiry · {reference}"
            message = f"{payload.name} sent an enquiry for team follow-up."
        else:
            swimmer = payload.swimmer_name or f"swimmer age {payload.swimmer_age or 'not supplied'}"
            program = payload.program_interest or "program match required"
            title = f"New enrolment enquiry · {reference}"
            message = f"{payload.name} submitted an enquiry for {swimmer}: {program}."
        db.execute("INSERT INTO notifications(audience_role,title,message,kind,delivery_channels,created_at) VALUES(?,?,?,?,?,?)", ("admin", title, message, "enquiry", '["in_app"]', now_iso()))
        audit(db, None, "create_enquiry", "enquiry", cursor.lastrowid, {"email": payload.email, "reference": reference, "enquiry_type": payload.enquiry_type, "program": payload.program_interest}, ip)
        return {"id": cursor.lastrowid, "reference": reference, "received": True, "message": "Thanks — the HV Swim team can now follow up with you."}


@app.get("/api/admin/audit")
def audit_log(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        query = """SELECT a.*,u.first_name,u.last_name FROM audit_log a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.created_at DESC LIMIT 200"""
        return {"audit": rows(db.execute(query))}


identity.register(app, session_user, csrf_guard)
workforce.register(app, session_user, csrf_guard)


@app.api_route("/api/{unmatched_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def unknown_api_route(unmatched_path: str) -> None:
    """Keep unmatched API requests JSON even though the static site has an HTML 404."""
    raise HTTPException(status_code=404, detail="Not Found")


@app.exception_handler(StarletteHTTPException)
async def not_found_page(request: Request, exc: StarletteHTTPException):
    """Browsers asking for a missing page get the branded 404; the API keeps its JSON."""
    wants_html = "text/html" in request.headers.get("accept", "")
    if exc.status_code == 404 and wants_html and not request.url.path.startswith("/api/"):
        page = ROOT / "404.html"
        if page.exists():
            return HTMLResponse(page.read_text(encoding="utf-8"), status_code=404)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


# Only the browser assets directory is mounted wholesale. The previous root mount exposed
# every file in the repository — including backend source, the SQLite database and any
# future .env file — to anyone who knew the path. Root-level files are now served from an
# explicit allowlist so adding a private operational file can never make it public by
# accident.
app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")

PUBLIC_ROOT_FILES = frozenset(
    {
        "404.html",
        "START_HERE.html",
        "about.html",
        "admin.html",
        "customer.html",
        "enquire.html",
        "index.html",
        "locations.html",
        "login.html",
        "manifest.webmanifest",
        "offline.html",
        "photo-consent.html",
        "platform.html",
        "privacy.html",
        "programs.html",
        "robots.txt",
        "service-worker.js",
        "shop.html",
        "sitemap.xml",
        "staff.html",
        "terms.html",
    }
)


@app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
def browser_favicon() -> FileResponse:
    """Serve the existing PNG icon for browsers that probe the conventional URL."""
    return FileResponse(ROOT / "assets" / "app-icon-v3-64.png", media_type="image/png")


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def public_home() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.api_route("/{public_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
def public_file(public_path: str) -> FileResponse:
    if public_path not in PUBLIC_ROOT_FILES or (settings.production and public_path == "START_HERE.html"):
        raise HTTPException(status_code=404, detail="Not Found")
    file_path = ROOT / public_path
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(file_path)
