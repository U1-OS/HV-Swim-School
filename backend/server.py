from __future__ import annotations

import csv
import hmac
import io
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, EmailStr, Field

from .config import ROOT, settings
from .database import audit, db_session, initialise_database, rows
from .integrations import (
    current_bendigo_weather,
    decrypt_json,
    encrypt_json,
    pool_sensor_reading,
    printify_products,
    printify_ready,
    shopify_create_cart,
    shopify_products,
    shopify_ready,
    xero_authorization_url,
    xero_exchange_code,
    xero_post_timesheets,
    xero_ready,
)
from .security import expires_iso, new_token, now_iso, password_hash, password_needs_rehash, password_verify, public_user

SESSION_COOKIE = "hv_session"

app = FastAPI(
    title="HV Swim Bendigo Platform API",
    version="5.1.0",
    docs_url="/api/docs" if not settings.production else None,
    redoc_url=None,
)


@app.on_event("startup")
def startup() -> None:
    if settings.production and settings.session_secret == "local-demo-secret-change-before-production":
        raise RuntimeError("HV_SESSION_SECRET must be changed before production startup")
    initialise_database()


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self' https://api.open-meteo.com; form-action 'self' mailto:; "
        "base-uri 'self'; frame-ancestors 'self'"
    )
    if settings.production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    path = request.url.path
    if path.startswith("/api/"):
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


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class BookingInput(BaseModel):
    class_id: int
    swimmer_id: int


class ClockInput(BaseModel):
    action: Literal["in", "out"]
    location_slug: str = "wood-street"
    latitude: float | None = None
    longitude: float | None = None
    accuracy_metres: float | None = None


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


class ApproveTimesheetInput(BaseModel):
    entry_id: int


class ClassInput(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    title: str = Field(min_length=3, max_length=80)
    level: str = Field(min_length=2, max_length=80)
    location_slug: str
    instructor_id: int | None = None
    weekday: int = Field(ge=0, le=6)
    start_time: str
    duration_minutes: int = Field(ge=15, le=180)
    capacity: int = Field(ge=1, le=20)
    price_cents: int = Field(ge=0, le=100_000)


class RosterInput(BaseModel):
    staff_id: int
    location_slug: str
    shift_date: date
    start_time: str
    end_time: str
    role_label: str = Field(default="Instructor", max_length=80)


class NotificationInput(BaseModel):
    user_id: int | None = None
    audience_role: Literal["customer", "staff", "admin"] | None = None
    title: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=3, max_length=800)
    kind: str = Field(default="info", max_length=30)
    channels: list[Literal["in_app", "email", "sms", "push"]] = Field(default_factory=lambda: ["in_app"])


class EnquiryInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(default="", max_length=40)
    swimmer_name: str = Field(default="", max_length=100)
    swimmer_age: str = Field(default="", max_length=50)
    program_interest: str = Field(default="", max_length=100)
    preferred_class: str = Field(default="", max_length=180)
    preferred_days: str = Field(default="", max_length=180)
    contact_method: str = Field(default="email", max_length=30)
    experience: str = Field(default="", max_length=500)
    support_needs: str = Field(default="", max_length=500)
    # Honeypot. The form renders this hidden and off-screen, so a person never fills it in.
    website: str = Field(default="", max_length=200)


class EnquiryStatusInput(BaseModel):
    status: Literal["new", "contacted", "trial_booked", "closed"]


class SiteSettingsInput(BaseModel):
    announcement_enabled: bool = False
    announcement_text: str = Field(min_length=3, max_length=180)
    enrolment_status: Literal["open", "limited", "waitlist"] = "open"
    hero_eyebrow: str = Field(min_length=3, max_length=90)
    hero_heading: str = Field(min_length=3, max_length=80)
    hero_accent: str = Field(min_length=3, max_length=80)
    hero_intro: str = Field(min_length=20, max_length=360)
    primary_cta: str = Field(min_length=3, max_length=50)


class ProductUpdateInput(BaseModel):
    price_cents: int = Field(ge=0, le=100_000)
    status: Literal["planned", "sampling", "approved", "available", "paused"]
    sample_status: Literal["not_ordered", "ordered", "received", "changes_required", "approved"] = "not_ordered"
    cost_cents: int | None = Field(default=None, ge=0, le=100_000)
    supplier_route: Literal["specialist_uniform", "vistaprint", "printify", "printify_or_vistaprint", "vistaprint_or_specialist", "manual_review"] = "manual_review"
    personalisation: str = Field(default="", max_length=240)


class LocationUpdateInput(BaseModel):
    public_status: str = Field(min_length=3, max_length=80)
    venue_type: str = Field(min_length=3, max_length=140)
    parking: str = Field(min_length=3, max_length=240)
    accessibility: str = Field(min_length=3, max_length=320)


class WaitlistActionInput(BaseModel):
    action: Literal["promote", "remove"]


class CartInput(BaseModel):
    variant_id: str
    quantity: int = Field(default=1, ge=1, le=20)


LOGIN_ATTEMPT_RETENTION_DAYS = 30


def login_attempt_cutoff() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=LOGIN_ATTEMPT_RETENTION_DAYS)).isoformat()


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
            (session_id, now_iso()),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Session expired")
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


def integration_summary(db: sqlite3.Connection) -> list[dict[str, Any]]:
    output = []
    configuration = {
        "xero": {"configured": xero_ready(), "description": "Existing Xero organisation · OAuth and payroll mapping"},
        "shopify": {"configured": shopify_ready(), "description": "Storefront catalogue, cart and checkout"},
        "printify": {"configured": printify_ready(), "description": "POD products, mockups and Shopify fulfilment"},
        "vistaprint": {"configured": False, "description": "Manual uniforms and promotional-product supplier workflow"},
        "email": {"configured": bool(settings.email_provider and settings.email_api_key), "description": "Transactional email provider"},
        "sms": {"configured": bool(settings.sms_provider and settings.sms_api_key), "description": "SMS reminders and urgent closures"},
        "web_push": {"configured": bool(settings.web_push_public_key and settings.web_push_private_key), "description": "App push notifications"},
        "pool_sensor": {"configured": bool(settings.pool_sensor_url), "description": "Optional automatic pool sensor feed"},
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
    return settings_rows


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
    return {"ok": True, "service": "HV Swim Bendigo", "version": "5.1.0", "environment": settings.app_env, "time": now_iso()}


@app.get("/api/public/site-settings")
def public_site_settings() -> dict[str, Any]:
    with db_session() as db:
        return {"settings": site_settings_payload(db)}


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
        failures = db.execute("SELECT COUNT(*) FROM login_attempts WHERE email=? AND ip_address=? AND success=0 AND created_at>?", (email, ip, cutoff)).fetchone()[0]
        if failures >= 10:
            raise HTTPException(status_code=429, detail="Too many sign-in attempts. Try again in 15 minutes.")
        user = db.execute("SELECT * FROM users WHERE email=? AND active=1", (email,)).fetchone()
        success = bool(user and password_verify(payload.password, user["password_hash"]))
        db.execute("INSERT INTO login_attempts(email,ip_address,success,created_at) VALUES(?,?,?,?)", (email, ip, int(success), now_iso()))
        if not success:
            raise HTTPException(status_code=401, detail="Email or password is incorrect")
        if password_needs_rehash(user["password_hash"]):
            refreshed_hash = password_hash(payload.password)
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (refreshed_hash, user["id"]))
        session_id, csrf = new_token(32), new_token(24)
        db.execute("DELETE FROM sessions WHERE expires_at<=?", (now_iso(),))
        # Sign-in records exist only for rate limiting. Keeping email/IP pairs longer
        # than that is a privacy liability, so prune anything past the retention window.
        db.execute("DELETE FROM login_attempts WHERE created_at<=?", (login_attempt_cutoff(),))
        db.execute("INSERT INTO sessions(id,user_id,csrf_token,created_at,expires_at) VALUES(?,?,?,?,?)", (session_id, user["id"], csrf, now_iso(), expires_iso()))
        audit(db, user["id"], "login", "session", session_id[-8:], ip_address=ip)
        response.set_cookie(SESSION_COOKIE, session_id, max_age=14*24*60*60, httponly=True, secure=settings.production, samesite="lax", path="/")
        return {"user": public_user(user), "csrf_token": csrf}


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


@app.get("/api/public/locations")
def public_locations() -> dict[str, Any]:
    with db_session() as db:
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
            output.append(item)
        return {"locations": output}


@app.get("/api/public/weather")
async def weather() -> dict[str, Any]:
    try:
        return {"source": "Open-Meteo", "location": "Bendigo", "current": await current_bendigo_weather()}
    except Exception:
        raise HTTPException(status_code=503, detail="Live weather is temporarily unavailable")


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
        return {"classes": output}


@app.get("/api/customer/swimmers")
def customer_swimmers(user: dict[str, Any] = Depends(require_roles("customer", "admin"))) -> dict[str, Any]:
    with db_session() as db:
        if user["role"] == "customer":
            result = rows(db.execute("SELECT * FROM swimmers WHERE customer_id=? AND active=1 ORDER BY first_name", (user["id"],)))
        else:
            result = rows(db.execute("SELECT s.*,u.first_name parent_first,u.last_name parent_last FROM swimmers s JOIN users u ON u.id=s.customer_id WHERE s.active=1 ORDER BY s.first_name"))
        return {"swimmers": result}


@app.get("/api/customer/bookings")
def customer_bookings(user: dict[str, Any] = Depends(require_roles("customer", "admin"))) -> dict[str, Any]:
    with db_session() as db:
        where, params = ("s.customer_id=?", (user["id"],)) if user["role"] == "customer" else ("1=1", ())
        query = f"""SELECT b.id,b.status,b.created_at,s.id swimmer_id,s.first_name swimmer_first,s.last_name swimmer_last,
                    c.id class_id,c.title,c.level,c.weekday,c.start_time,c.duration_minutes,l.name location_name,
                    u.first_name instructor_first,u.last_name instructor_last
                    FROM bookings b JOIN swimmers s ON s.id=b.swimmer_id JOIN classes c ON c.id=b.class_id
                    JOIN locations l ON l.id=c.location_id LEFT JOIN users u ON u.id=c.instructor_id
                    WHERE {where} ORDER BY c.weekday,c.start_time"""
        bookings = rows(db.execute(query, params))
        waitlist_query = f"""SELECT w.id,w.position,w.status,w.created_at,s.id swimmer_id,s.first_name swimmer_first,s.last_name swimmer_last,
                              c.id class_id,c.title,c.level,c.weekday,c.start_time,c.duration_minutes,l.name location_name
                              FROM waitlist w JOIN swimmers s ON s.id=w.swimmer_id JOIN classes c ON c.id=w.class_id
                              JOIN locations l ON l.id=c.location_id WHERE {where} AND w.status='waiting'
                              ORDER BY c.weekday,c.start_time,w.position"""
        return {"bookings": bookings, "waitlist": rows(db.execute(waitlist_query, params))}


@app.post("/api/customer/bookings")
def create_booking(payload: BookingInput, request: Request, user: dict[str, Any] = Depends(require_roles("customer", "admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        # Capacity is read and then written. Without an immediate write lock two requests
        # arriving together can both see the last place free and both take it, putting the
        # class over its instructor-to-swimmer ratio.
        db.execute("BEGIN IMMEDIATE")
        swimmer = db.execute("SELECT * FROM swimmers WHERE id=?", (payload.swimmer_id,)).fetchone()
        swim_class = db.execute("SELECT * FROM classes WHERE id=? AND active=1", (payload.class_id,)).fetchone()
        if not swimmer or (user["role"] == "customer" and swimmer["customer_id"] != user["id"]):
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
        db.execute("INSERT INTO notifications(user_id,title,message,kind,delivery_channels,created_at) VALUES(?,?,?,?,?,?)", (swimmer["customer_id"], "Lesson booking confirmed", f"{swimmer['first_name']} is confirmed for {swim_class['title']}.", "booking", '["in_app","email"]', now_iso()))
        audit(db, user["id"], "create_booking", "booking", cursor.lastrowid, {"class_id": payload.class_id, "swimmer_id": payload.swimmer_id}, client_ip(request))
        return {"status": "confirmed", "booking_id": cursor.lastrowid}


@app.delete("/api/customer/bookings/{booking_id}")
def cancel_booking(booking_id: int, request: Request, user: dict[str, Any] = Depends(require_roles("customer", "admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, bool]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        booking = db.execute("SELECT b.*,s.customer_id FROM bookings b JOIN swimmers s ON s.id=b.swimmer_id WHERE b.id=?", (booking_id,)).fetchone()
        if not booking or (user["role"] == "customer" and booking["customer_id"] != user["id"]):
            raise HTTPException(status_code=404, detail="Booking not found")
        db.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (booking_id,))
        audit(db, user["id"], "cancel_booking", "booking", booking_id, ip_address=client_ip(request))
        return {"ok": True}


@app.get("/api/staff/roster")
def staff_roster(user: dict[str, Any] = Depends(require_roles("staff", "admin"))) -> dict[str, Any]:
    with db_session() as db:
        where, params = ("r.staff_id=?", (user["id"],)) if user["role"] == "staff" else ("1=1", ())
        query = f"""SELECT r.*,l.name location_name,l.slug location_slug,u.first_name,u.last_name
                    FROM rosters r JOIN locations l ON l.id=r.location_id JOIN users u ON u.id=r.staff_id
                    WHERE {where} AND r.shift_date>=? ORDER BY r.shift_date,r.start_time"""
        return {"roster": rows(db.execute(query, params + (date.today().isoformat(),)))}


@app.post("/api/staff/clock")
def staff_clock(payload: ClockInput, request: Request, user: dict[str, Any] = Depends(require_roles("staff", "admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        if payload.action == "in":
            active = db.execute("SELECT * FROM time_entries WHERE staff_id=? AND clock_out IS NULL", (user["id"],)).fetchone()
            if active:
                raise HTTPException(status_code=409, detail="You are already clocked in")
            location = location_by_slug(db, payload.location_slug)
            cursor = db.execute("INSERT INTO time_entries(staff_id,location_id,clock_in,latitude,longitude,accuracy_metres,status) VALUES(?,?,?,?,?,?,?)", (user["id"], location["id"], now_iso(), payload.latitude, payload.longitude, payload.accuracy_metres, "draft"))
            audit(db, user["id"], "clock_in", "time_entry", cursor.lastrowid, {"location": payload.location_slug}, client_ip(request))
            return {"status": "clocked_in", "entry_id": cursor.lastrowid, "clock_in": now_iso(), "location": location["name"]}
        active = db.execute("SELECT * FROM time_entries WHERE staff_id=? AND clock_out IS NULL ORDER BY clock_in DESC LIMIT 1", (user["id"],)).fetchone()
        if not active:
            raise HTTPException(status_code=409, detail="No active shift was found")
        finish = datetime.now(timezone.utc)
        start = datetime.fromisoformat(active["clock_in"])
        hours = round(max(0, (finish - start).total_seconds() / 3600), 2)
        db.execute("UPDATE time_entries SET clock_out=?,hours=? WHERE id=?", (finish.isoformat(), hours, active["id"]))
        audit(db, user["id"], "clock_out", "time_entry", active["id"], {"hours": hours}, client_ip(request))
        return {"status": "clocked_out", "entry_id": active["id"], "clock_out": finish.isoformat(), "hours": hours}


@app.get("/api/staff/time-entries")
def staff_time_entries(user: dict[str, Any] = Depends(require_roles("staff", "admin"))) -> dict[str, Any]:
    with db_session() as db:
        where, params = ("t.staff_id=?", (user["id"],)) if user["role"] == "staff" else ("1=1", ())
        query = f"""SELECT t.*,l.name location_name,u.first_name,u.last_name FROM time_entries t
                    JOIN locations l ON l.id=t.location_id JOIN users u ON u.id=t.staff_id WHERE {where}
                    ORDER BY t.clock_in DESC LIMIT 100"""
        return {"time_entries": rows(db.execute(query, params))}


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
        cursor = db.execute(f"UPDATE time_entries SET status='submitted' WHERE id IN ({placeholders}) AND clock_out IS NOT NULL AND status='draft'{where_owner}", params)
        audit(db, user["id"], "submit_timesheet", "time_entry", detail={"entry_ids": payload.entry_ids, "updated": cursor.rowcount}, ip_address=client_ip(request))
        return {"updated": cursor.rowcount}


@app.post("/api/staff/pool-readings")
def create_pool_reading(payload: PoolReadingInput, request: Request, user: dict[str, Any] = Depends(require_roles("staff", "admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    if payload.status == "open" and payload.temperature is None:
        raise HTTPException(status_code=400, detail="An open pool requires a temperature reading")
    with db_session() as db:
        location = location_by_slug(db, payload.location_slug)
        cursor = db.execute("INSERT INTO pool_readings(location_id,temperature,status,note,verified_by,source,created_at) VALUES(?,?,?,?,?,?,?)", (location["id"], payload.temperature, payload.status, payload.note, user["id"], "manual", now_iso()))
        db.execute("UPDATE locations SET public_status=? WHERE id=?", ({"open": "Lessons running", "changed": "Changed conditions", "closed": "Closed / lessons cancelled"}[payload.status], location["id"]))
        audience_message = f"{location['name']}: {payload.note or {'open':'Lessons running','changed':'Changed conditions','closed':'Closed / lessons cancelled'}[payload.status]}"
        db.execute("INSERT INTO notifications(audience_role,title,message,kind,delivery_channels,created_at) VALUES(?,?,?,?,?,?)", ("customer", "Pool condition updated", audience_message, "pool", '["in_app","push"]', now_iso()))
        audit(db, user["id"], "publish_pool_reading", "pool_reading", cursor.lastrowid, {"location": payload.location_slug, "temperature": payload.temperature, "status": payload.status}, client_ip(request))
        return {"id": cursor.lastrowid, "published": True, "created_at": now_iso()}


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
        where, params = ("q.staff_id=?", (user["id"],)) if user["role"] == "staff" else ("1=1", ())
        query = f"""SELECT q.*,u.first_name,u.last_name FROM qualifications q JOIN users u ON u.id=q.staff_id
                    WHERE {where} ORDER BY q.expiry_date"""
        return {"qualifications": rows(db.execute(query, params))}


@app.get("/api/notifications")
def notifications(user: dict[str, Any] = Depends(session_user)) -> dict[str, Any]:
    with db_session() as db:
        query = """SELECT * FROM notifications WHERE user_id=? OR audience_role=? ORDER BY created_at DESC LIMIT 100"""
        return {"notifications": rows(db.execute(query, (user["id"], user["role"])))}


@app.post("/api/notifications/{notification_id}/read")
def read_notification(notification_id: int, request: Request, user: dict[str, Any] = Depends(session_user), x_csrf_token: str | None = Header(default=None)) -> dict[str, bool]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        db.execute("UPDATE notifications SET read_at=? WHERE id=? AND (user_id=? OR audience_role=?)", (now_iso(), notification_id, user["id"], user["role"]))
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
            "expiring_qualifications": db.execute("SELECT COUNT(*) FROM qualifications WHERE status='expiring' OR expiry_date<=?", ((date.today()+timedelta(days=60)).isoformat(),)).fetchone()[0],
            "class_utilisation": round(100 * db.execute("SELECT COUNT(*) FROM bookings WHERE status='confirmed'").fetchone()[0] / max(1, db.execute("SELECT COALESCE(SUM(capacity),1) FROM classes WHERE active=1").fetchone()[0]), 1),
        }
        return {"metrics": metrics}


@app.get("/api/admin/dashboard")
def admin_dashboard(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
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
        today_weekday = date.today().weekday()
        for location in db.execute("SELECT * FROM locations ORDER BY id"):
            reading = db.execute("SELECT temperature,status,note,source,created_at FROM pool_readings WHERE location_id=? ORDER BY created_at DESC LIMIT 1", (location["id"],)).fetchone()
            checklist = db.execute("SELECT created_at,deck_safe,first_aid_ready,equipment_ready,water_checked FROM pool_checklists WHERE location_id=? ORDER BY created_at DESC LIMIT 1", (location["id"],)).fetchone()
            reading_fresh = bool(reading and now - datetime.fromisoformat(reading["created_at"]) <= timedelta(hours=24))
            checklist_fresh = bool(checklist and now - datetime.fromisoformat(checklist["created_at"]) <= timedelta(hours=24))
            today_classes = db.execute("SELECT COUNT(*) FROM classes WHERE active=1 AND location_id=? AND weekday=?", (location["id"], today_weekday)).fetchone()[0]
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
        }


@app.get("/api/admin/locations")
def admin_locations(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        locations = []
        today_weekday = date.today().weekday()
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
            ))
            locations.append({
                **dict(location),
                "latest_reading": dict(reading) if reading else None,
                "latest_checklist": dict(checklist) if checklist else None,
                "today_classes": today_classes,
            })
        return {"locations": locations, "source": "HV Swim operational database", "generated_at": now_iso()}


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


@app.get("/api/admin/exports/enquiries.csv")
def export_enquiries(user: dict[str, Any] = Depends(require_roles("admin"))) -> Response:
    with db_session() as db:
        records = rows(db.execute("SELECT created_at,name,email,phone,swimmer_name,swimmer_age,program_interest,preferred_class,preferred_days,contact_method,status,experience FROM enquiries ORDER BY created_at DESC"))
    return csv_download(
        "hv-swim-enquiries.csv",
        ["Created", "Contact", "Email", "Phone", "Swimmer", "Swimmer age", "Program", "Preferred class", "Preferred days", "Contact method", "Status", "Experience"],
        [[item["created_at"], item["name"], item["email"], item["phone"], item["swimmer_name"], item["swimmer_age"], item["program_interest"], item["preferred_class"], item["preferred_days"], item["contact_method"], item["status"], item["experience"]] for item in records],
    )


@app.get("/api/admin/exports/products.csv")
def export_products(user: dict[str, Any] = Depends(require_roles("admin"))) -> Response:
    with db_session() as db:
        records = rows(db.execute("SELECT sku,title,category,price_cents,status,sizes FROM products ORDER BY category,title"))
    return csv_download(
        "hv-swim-merchandise.csv",
        ["SKU", "Product", "Category", "Retail price AUD", "Status", "Sizes"],
        [[item["sku"], item["title"], item["category"], f'{item["price_cents"] / 100:.2f}', item["status"], item["sizes"]] for item in records],
    )


@app.get("/api/admin/exports/timesheets.csv")
def export_timesheets(user: dict[str, Any] = Depends(require_roles("admin"))) -> Response:
    with db_session() as db:
        query = """SELECT u.first_name,u.last_name,t.clock_in,t.clock_out,l.name location_name,t.hours,t.status,t.approved_at
                   FROM time_entries t JOIN users u ON u.id=t.staff_id JOIN locations l ON l.id=t.location_id
                   ORDER BY t.clock_in DESC"""
        records = rows(db.execute(query))
    return csv_download(
        "hv-swim-timesheets.csv",
        ["Staff", "Clock in", "Clock out", "Location", "Hours", "Status", "Approved at"],
        [[f'{item["first_name"]} {item["last_name"]}'.strip(), item["clock_in"], item["clock_out"], item["location_name"], item["hours"], item["status"], item["approved_at"]] for item in records],
    )


@app.get("/api/admin/site-settings")
def admin_site_settings(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        return {"settings": site_settings_payload(db)}


@app.patch("/api/admin/site-settings")
def update_site_settings(payload: SiteSettingsInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    values = payload.model_dump()
    values["announcement_enabled"] = "1" if values["announcement_enabled"] else "0"
    with db_session() as db:
        for key, value in values.items():
            db.execute("INSERT INTO site_settings(key,value,updated_by,updated_at) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_by=excluded.updated_by,updated_at=excluded.updated_at", (key, str(value), user["id"], now_iso()))
        audit(db, user["id"], "update_public_website", "site_settings", "homepage", {"fields": list(values)}, client_ip(request))
        return {"saved": True, "settings": site_settings_payload(db)}


@app.get("/api/admin/enquiries")
def admin_enquiries(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        query = """SELECT * FROM enquiries ORDER BY CASE status WHEN 'new' THEN 0 WHEN 'contacted' THEN 1 WHEN 'trial_booked' THEN 2 ELSE 3 END,created_at DESC LIMIT 250"""
        return {"enquiries": rows(db.execute(query))}


@app.patch("/api/admin/enquiries/{enquiry_id}")
def update_enquiry(enquiry_id: int, payload: EnquiryStatusInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        enquiry = db.execute("SELECT id,status,name FROM enquiries WHERE id=?", (enquiry_id,)).fetchone()
        if not enquiry:
            raise HTTPException(status_code=404, detail="Enquiry not found")
        db.execute("UPDATE enquiries SET status=? WHERE id=?", (payload.status, enquiry_id))
        audit(db, user["id"], "update_enquiry_status", "enquiry", enquiry_id, {"from": enquiry["status"], "to": payload.status, "name": enquiry["name"]}, client_ip(request))
        return {"saved": True, "id": enquiry_id, "status": payload.status}


@app.get("/api/admin/staff")
def admin_staff(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        query = """SELECT u.id,u.email,u.first_name,u.last_name,u.phone,u.role,u.active,
                   (SELECT COUNT(*) FROM qualifications q WHERE q.staff_id=u.id AND (q.status='expiring' OR q.expiry_date<=?)) expiring_qualifications
                   FROM users u WHERE u.role IN ('staff','admin') ORDER BY u.first_name,u.last_name"""
        cutoff = (date.today() + timedelta(days=60)).isoformat()
        return {"staff": rows(db.execute(query, (cutoff,)))}


@app.get("/api/admin/enrolments")
def admin_enrolments(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
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
            item["is_today"] = item["weekday"] == date.today().weekday()
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
        }


@app.post("/api/admin/waitlist/{waitlist_id}/action")
def admin_waitlist_action(waitlist_id: int, payload: WaitlistActionInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        # Same read-then-write gap as create_booking: lock before checking capacity.
        db.execute("BEGIN IMMEDIATE")
        entry = db.execute(
            """SELECT w.*,c.title,c.capacity,s.first_name swimmer_first,s.customer_id
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
        renumber_waitlist(db, entry["class_id"])
        db.execute("INSERT INTO notifications(user_id,title,message,kind,delivery_channels,created_at) VALUES(?,?,?,?,?,?)", (entry["customer_id"], "A lesson place is confirmed", f"{entry['swimmer_first']} now has a confirmed place in {entry['title']}.", "booking", '["in_app","email"]', now_iso()))
        audit(db, user["id"], "promote_waitlist_entry", "waitlist", waitlist_id, {"booking_id": booking_id, "class_id": entry["class_id"], "swimmer_id": entry["swimmer_id"]}, client_ip(request))
        return {"status": "confirmed", "waitlist_id": waitlist_id, "booking_id": booking_id}


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
        entry = db.execute("SELECT * FROM time_entries WHERE id=? AND status='submitted'", (payload.entry_id,)).fetchone()
        if not entry:
            raise HTTPException(status_code=404, detail="Submitted time entry not found")
        db.execute("UPDATE time_entries SET status='approved',approved_by=?,approved_at=? WHERE id=?", (user["id"], now_iso(), payload.entry_id))
        audit(db, user["id"], "approve_timesheet", "time_entry", payload.entry_id, {"hours": entry["hours"]}, client_ip(request))
        return {"approved": True, "entry_id": payload.entry_id}


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
        location = location_by_slug(db, payload.location_slug)
        staff = db.execute("SELECT id FROM users WHERE id=? AND role IN ('staff','admin') AND active=1", (payload.staff_id,)).fetchone()
        if not staff:
            raise HTTPException(status_code=404, detail="Staff member not found")
        cursor = db.execute("INSERT INTO rosters(staff_id,location_id,shift_date,start_time,end_time,role_label,status) VALUES(?,?,?,?,?,?,?)", (payload.staff_id, location["id"], payload.shift_date.isoformat(), payload.start_time, payload.end_time, payload.role_label, "published"))
        audit(db, user["id"], "publish_roster_shift", "roster", cursor.lastrowid, payload.model_dump(mode="json"), client_ip(request))
        return {"id": cursor.lastrowid, "published": True}


@app.post("/api/admin/notifications")
def create_notification(payload: NotificationInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    if not payload.user_id and not payload.audience_role:
        raise HTTPException(status_code=400, detail="Choose a user or audience role")
    unavailable = []
    if "email" in payload.channels and not (settings.email_provider and settings.email_api_key): unavailable.append("email")
    if "sms" in payload.channels and not (settings.sms_provider and settings.sms_api_key): unavailable.append("sms")
    if "push" in payload.channels and not (settings.web_push_public_key and settings.web_push_private_key): unavailable.append("push")
    with db_session() as db:
        cursor = db.execute("INSERT INTO notifications(user_id,audience_role,title,message,kind,delivery_channels,created_at) VALUES(?,?,?,?,?,?,?)", (payload.user_id, payload.audience_role, payload.title, payload.message, payload.kind, json.dumps(payload.channels), now_iso()))
        audit(db, user["id"], "create_notification", "notification", cursor.lastrowid, {"channels": payload.channels, "unavailable": unavailable}, client_ip(request))
        return {"id": cursor.lastrowid, "queued": True, "in_app_delivered": True, "unavailable_channels": unavailable}


@app.get("/api/admin/integrations")
def integrations(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        return {"integrations": integration_summary(db), "safe_mode": {"xero_sync_enabled": settings.xero_sync_enabled}}


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
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        connection = db.execute("SELECT * FROM integration_connections WHERE provider='xero' AND status='connected'").fetchone()
        if not connection:
            raise HTTPException(status_code=409, detail="Connect the existing Xero organisation first")
        approved = rows(db.execute("SELECT t.*,u.email,u.first_name,u.last_name FROM time_entries t JOIN users u ON u.id=t.staff_id WHERE t.status='approved' AND t.xero_timesheet_id IS NULL"))
        if not approved:
            return {"synced": 0, "message": "No approved hours are waiting for Xero"}
        if not settings.xero_earnings_rate_id:
            return {"synced": 0, "dry_run": True, "entries": approved, "message": "Map XERO_EARNINGS_RATE_ID and staff Xero Employee IDs before enabling payroll transmission."}
        token = decrypt_json(connection["encrypted_tokens"])
        payload = []
        for entry in approved:
            payload.append({"EmployeeID": entry.get("xero_employee_id", "MAP_REQUIRED"), "StartDate": entry["clock_in"][:10], "EndDate": entry["clock_out"][:10], "Status": "DRAFT", "TimesheetLines": [{"EarningsRateID": settings.xero_earnings_rate_id, "NumberOfUnits": [entry["hours"]]}]})
    try:
        result = await xero_post_timesheets(token, payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Xero timesheet sync failed: {type(exc).__name__}")
    return {"synced": 0 if result.get("dry_run") else len(payload), **result}


@app.get("/api/products")
async def products() -> dict[str, Any]:
    if shopify_ready():
        try:
            return {"source": "shopify", "products": await shopify_products()}
        except Exception as exc:
            with db_session() as db:
                fallback = rows(db.execute("SELECT * FROM products ORDER BY category,title"))
            return {"source": "local_fallback", "products": fallback, "warning": f"Shopify unavailable: {type(exc).__name__}"}
    with db_session() as db:
        return {"source": "planned_catalogue", "products": rows(db.execute("SELECT * FROM products ORDER BY category,title"))}


@app.get("/api/admin/merch-production")
async def merch_production(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    supplier_plan = {
        "HV-SWIMWEAR": {"supplier": "specialist_uniform", "method": "Sample specialist chlorine-resistant swimwear; sell through Shopify after approval."},
        "HV-TOWEL": {"supplier": "vistaprint_or_specialist", "method": "Quote embroidered or printed towels, approve one physical sample, then stock in Shopify."},
        "HV-BOTTLE": {"supplier": "vistaprint", "method": "Manual branded-bottle quote and bulk order; hold stock for Shopify fulfilment."},
        "HV-GOGGLES": {"supplier": "specialist_uniform", "method": "Source compliant swimming equipment from a specialist; avoid generic POD."},
        "HV-BAG": {"supplier": "printify_or_vistaprint", "method": "Compare POD and bulk samples; connect the selected item to Shopify."},
        "HV-CAP": {"supplier": "specialist_uniform", "method": "Use a specialist silicone swim-cap supplier and approve print durability."},
        "HV-STAFF-POLO": {"supplier": "vistaprint", "method": "Embroidered performance uniform ordered in approved staff sizes."},
        "HV-TEAM-HOODIE": {"supplier": "printify", "method": "POD hoodie produced and fulfilled through Printify's Shopify connection."},
        "HV-INSTRUCTOR-CAP": {"supplier": "printify_or_vistaprint", "method": "Sample embroidered options before choosing POD or a bulk uniform order."},
    }
    with db_session() as db:
        catalogue = rows(db.execute("SELECT * FROM products ORDER BY category,title"))
    for product in catalogue:
        planned = supplier_plan.get(product["sku"], {"supplier": "manual_review", "method": "Confirm supplier and sample before launch."})
        planned["supplier"] = product.get("supplier_route") or planned["supplier"]
        product["production"] = planned
        product["margin_cents"] = None if product.get("cost_cents") is None else product["price_cents"] - product["cost_cents"]
        product["margin_percent"] = None if product.get("cost_cents") is None or not product["price_cents"] else round((product["price_cents"] - product["cost_cents"]) / product["price_cents"] * 100, 1)
    approved_samples = sum(1 for product in catalogue if product.get("sample_status") == "approved")
    costed_products = sum(1 for product in catalogue if product.get("cost_cents") is not None)
    launchable_products = sum(1 for product in catalogue if product.get("sample_status") == "approved" and product.get("status") in {"approved", "available"})
    live_printify = []
    printify_error = None
    if printify_ready():
        try:
            live_printify = await printify_products()
        except Exception as exc:
            printify_error = f"Printify connection unavailable: {type(exc).__name__}"
    return {
        "catalogue": catalogue,
        "launch_readiness": {
            "total_products": len(catalogue),
            "approved_samples": approved_samples,
            "costed_products": costed_products,
            "launchable_products": launchable_products,
            "readiness_percent": round((approved_samples + costed_products + launchable_products) / (max(len(catalogue), 1) * 3) * 100),
        },
        "providers": {
            "shopify": {"configured": shopify_ready(), "role": "Storefront, checkout, customer orders and inventory"},
            "printify": {"configured": printify_ready(), "role": "Automated POD mockups, production and fulfilment", "products": live_printify, "error": printify_error},
            "vistaprint": {"configured": False, "role": "Manual quotes and bulk ordering for uniforms, bottles and promotional gear", "url": "https://www.vistaprint.com.au/custom-promotional-merch"},
        },
        "workflow": ["Approve artwork", "Order physical samples", "Approve sizes and margins", "Publish products to Shopify", "Test checkout and shipping", "Launch collection"],
    }


@app.patch("/api/admin/products/{product_id}")
def update_product(product_id: int, payload: ProductUpdateInput, request: Request, user: dict[str, Any] = Depends(require_roles("admin")), x_csrf_token: str | None = Header(default=None)) -> dict[str, Any]:
    csrf_guard(request, user, x_csrf_token)
    with db_session() as db:
        product = db.execute("SELECT id,sku,title,price_cents,status FROM products WHERE id=?", (product_id,)).fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        db.execute(
            "UPDATE products SET price_cents=?,status=?,sample_status=?,cost_cents=?,supplier_route=?,personalisation=? WHERE id=?",
            (payload.price_cents, payload.status, payload.sample_status, payload.cost_cents, payload.supplier_route, payload.personalisation, product_id),
        )
        detail = {"sku": product["sku"], "price_cents": payload.price_cents, "status": payload.status, "sample_status": payload.sample_status, "cost_cents": payload.cost_cents, "supplier_route": payload.supplier_route}
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
            """INSERT INTO enquiries(name,email,phone,swimmer_name,swimmer_age,program_interest,preferred_class,preferred_days,contact_method,experience,support_needs,status,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (payload.name, payload.email, payload.phone, payload.swimmer_name, payload.swimmer_age, payload.program_interest, payload.preferred_class, payload.preferred_days, payload.contact_method, payload.experience, payload.support_needs, "new", now_iso()),
        )
        reference = f"HV-ENQ-{cursor.lastrowid:04d}"
        swimmer = payload.swimmer_name or f"swimmer age {payload.swimmer_age or 'not supplied'}"
        program = payload.program_interest or "program match required"
        db.execute("INSERT INTO notifications(audience_role,title,message,kind,delivery_channels,created_at) VALUES(?,?,?,?,?,?)", ("admin", f"New enrolment enquiry · {reference}", f"{payload.name} submitted an enquiry for {swimmer}: {program}.", "enquiry", '["in_app","email"]', now_iso()))
        audit(db, None, "create_enquiry", "enquiry", cursor.lastrowid, {"email": payload.email, "reference": reference, "program": payload.program_interest}, ip)
        return {"id": cursor.lastrowid, "reference": reference, "received": True, "message": "Thanks — the HV Swim team can now follow up with you."}


@app.get("/api/admin/audit")
def audit_log(user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    with db_session() as db:
        query = """SELECT a.*,u.first_name,u.last_name FROM audit_log a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.created_at DESC LIMIT 200"""
        return {"audit": rows(db.execute(query))}


@app.exception_handler(StarletteHTTPException)
async def not_found_page(request: Request, exc: StarletteHTTPException):
    """Browsers asking for a missing page get the branded 404; the API keeps its JSON."""
    wants_html = "text/html" in request.headers.get("accept", "")
    if exc.status_code == 404 and wants_html and not request.url.path.startswith("/api/"):
        page = ROOT / "404.html"
        if page.exists():
            return HTMLResponse(page.read_text(encoding="utf-8"), status_code=404)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


# Keep this mount last so /api routes take precedence.
app.mount("/", StaticFiles(directory=ROOT, html=True), name="site")
