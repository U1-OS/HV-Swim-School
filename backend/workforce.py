"""Exact, auditable working-hours services on the existing HV time-entry ledger.

No pay rates, award interpretations or automatic break deductions are applied here.
Clock records are UTC seconds. Legacy rounded totals retain their original provenance.
"""

from __future__ import annotations

import calendar
import csv
import hashlib
import io
import json
import sqlite3
import zipfile
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from fastapi import Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from .database import audit, db_session, rows

TZ = ZoneInfo("Australia/Melbourne")


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def stamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("An explicit timestamp timezone is required")
    return result.astimezone(timezone.utc)


def duration(start: datetime, finish: datetime) -> int:
    return int((finish - start).total_seconds())


def migrate() -> None:
    """Additive, repeatable migration; never rewrite legacy hours or discard records."""
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        columns = {r[1] for r in db.execute("PRAGMA table_info(time_entries)")}
        for key, definition in {
            "origin": "TEXT NOT NULL DEFAULT 'legacy'",
            "worked_seconds": "INTEGER",
            "elapsed_seconds": "INTEGER",
            "unpaid_seconds": "INTEGER NOT NULL DEFAULT 0",
            "paid_break_seconds": "INTEGER NOT NULL DEFAULT 0",
            "entry_version": "INTEGER NOT NULL DEFAULT 1",
            "review_state": "TEXT NOT NULL DEFAULT 'draft'",
            "review_comment": "TEXT NOT NULL DEFAULT ''",
            "amendment_of": "INTEGER REFERENCES time_entries(id)",
        }.items():
            if key not in columns:
                db.execute(f"ALTER TABLE time_entries ADD COLUMN {key} {definition}")
        if "review_state" not in columns:
            db.execute(
                "UPDATE time_entries SET review_state=CASE WHEN status='exported' THEN 'approved' ELSE status END"
            )
        db.execute(
            "CREATE TABLE IF NOT EXISTS workforce_migrations(version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL)"
        )
        db.execute(
            "INSERT OR IGNORE INTO workforce_migrations VALUES(1,?)",
            (now().isoformat(),),
        )
        # Fail closed rather than start a clock without its concurrency guard.
        try:
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uniq_open_shift_per_staff ON time_entries(staff_id) WHERE clock_out IS NULL"
            )
        except sqlite3.IntegrityError as exc:
            raise RuntimeError(
                "Duplicate open shifts need reviewed correction before workforce startup"
            ) from exc
        statements = [
            """CREATE TABLE IF NOT EXISTS shift_breaks(id INTEGER PRIMARY KEY,
              entry_id INTEGER NOT NULL REFERENCES time_entries(id), started_at TEXT NOT NULL,
              ended_at TEXT, paid INTEGER NOT NULL CHECK(paid IN(0,1)), actor_id INTEGER NOT NULL REFERENCES users(id))""",
            "CREATE UNIQUE INDEX IF NOT EXISTS uniq_running_break ON shift_breaks(entry_id) WHERE ended_at IS NULL",
            """CREATE TABLE IF NOT EXISTS clock_requests(staff_id INTEGER NOT NULL REFERENCES users(id),
              request_id TEXT NOT NULL, fingerprint TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL,
              PRIMARY KEY(staff_id,request_id))""",
            """CREATE TABLE IF NOT EXISTS time_entry_events(id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL REFERENCES time_entries(id),
              actor_id INTEGER NOT NULL REFERENCES users(id), action TEXT NOT NULL, reason TEXT NOT NULL,
              before_json TEXT, after_json TEXT NOT NULL, created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS hour_export_batches(id INTEGER PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL,
              created_by INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, snapshot TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS hour_export_items(batch_id INTEGER NOT NULL REFERENCES hour_export_batches(id),
              entry_id INTEGER NOT NULL REFERENCES time_entries(id), entry_version INTEGER NOT NULL, work_date TEXT NOT NULL,
              UNIQUE(entry_id,entry_version,work_date))""",
            """CREATE TABLE IF NOT EXISTS workforce_settings(id INTEGER PRIMARY KEY CHECK(id=1),
              week_start INTEGER NOT NULL CHECK(week_start BETWEEN 0 AND 6), fortnight_anchor TEXT NOT NULL,
              long_shift_hours INTEGER NOT NULL CHECK(long_shift_hours BETWEEN 8 AND 48))""",
            "INSERT OR IGNORE INTO workforce_settings VALUES(1,0,'2026-01-05',16)",
            "CREATE INDEX IF NOT EXISTS idx_time_staff_start ON time_entries(staff_id,clock_in,clock_out)",
        ]
        for statement in statements:
            db.execute(statement)
        for table in ("time_entry_events", "hour_export_batches", "hour_export_items"):
            for operation in ("UPDATE", "DELETE"):
                db.execute(
                    f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'Accounting history is immutable'); END"
                )


def scope_ids(db, user, *, review=False) -> list[int] | None:
    if user["role"] == "admin":
        return None
    if user["role"] != "staff":
        raise HTTPException(403, "Staff account required")
    if review:
        raise HTTPException(403, "Management approval required")
    return [user["id"]]


def authorised_entry(db, user, entry_id, *, review=False):
    row = db.execute("SELECT * FROM time_entries WHERE id=?", (entry_id,)).fetchone()
    allowed = scope_ids(db, user, review=review)
    if not row or (allowed is not None and row["staff_id"] not in allowed):
        raise HTTPException(404, "Time entry not found in your permitted team")
    return row


def record_event(db, user, entry_id, action, reason, before=None):
    after = dict(
        db.execute("SELECT * FROM time_entries WHERE id=?", (entry_id,)).fetchone()
    )
    after["breaks"] = rows(
        db.execute("SELECT * FROM shift_breaks WHERE entry_id=?", (entry_id,))
    )
    db.execute(
        "INSERT INTO time_entry_events(entry_id,actor_id,action,reason,before_json,after_json,created_at) VALUES(?,?,?,?,?,?,?)",
        (
            entry_id,
            user["id"],
            action,
            reason,
            json.dumps(dict(before)) if before else None,
            json.dumps(after),
            now().isoformat(),
        ),
    )
    audit(
        db,
        user["id"],
        action,
        "time_entry",
        entry_id,
        {"version": after["entry_version"], "reason": reason},
    )


class ClockAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["in", "out", "break_start", "break_end"]
    location_slug: str = "wood-street"
    request_id: str | None = Field(
        default=None, min_length=16, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    entry_id: int | None = Field(default=None, gt=0)
    paid_break: bool = False


def clock_action(db, user, payload: ClockAction) -> dict:
    db.execute("BEGIN IMMEDIATE")
    fingerprint = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    if payload.request_id:
        previous = db.execute(
            "SELECT * FROM clock_requests WHERE staff_id=? AND request_id=?",
            (user["id"], payload.request_id),
        ).fetchone()
        if previous:
            if previous["fingerprint"] != fingerprint:
                raise HTTPException(
                    409,
                    "This request reference was already used for a different action",
                )
            return json.loads(previous["result"]) | {"replayed": True}
    at = now()
    active = db.execute(
        "SELECT * FROM time_entries WHERE staff_id=? AND clock_out IS NULL",
        (user["id"],),
    ).fetchone()
    if payload.action == "in":
        if active:
            if not payload.request_id:
                raise HTTPException(409, "You are already clocked on")
            result = {
                "state": "on_break" if active["break_started_at"] else "working",
                "entry_id": active["id"],
                "clock_in": active["clock_in"],
                "already_active": True,
            }
        else:
            location = db.execute(
                "SELECT id FROM locations WHERE slug=?", (payload.location_slug,)
            ).fetchone()
            if not location:
                raise HTTPException(422, "Choose an existing workplace")
            day = at.astimezone(TZ).date()
            # Do not mix actual clocking and a manual total for the same period.
            conflict = db.execute(
                "SELECT id FROM time_entries WHERE staff_id=? AND (origin='manual' OR entry_scope='weekly') AND (work_date=? OR (entry_scope='weekly' AND week_start<=? AND date(week_start,'+6 days')>=?))",
                (user["id"], day.isoformat(), day.isoformat(), day.isoformat()),
            ).fetchone()
            if conflict:
                raise HTTPException(
                    409,
                    "A manual hours total covers today. Ask management to reconcile it before starting a shift.",
                )
            entry_id = db.execute(
                "INSERT INTO time_entries(staff_id,location_id,clock_in,work_date,week_start,origin,review_state) VALUES(?,?,?,?,?,'clock','open')",
                (
                    user["id"],
                    location[0],
                    at.isoformat(),
                    day.isoformat(),
                    (day - timedelta(days=day.weekday())).isoformat(),
                ),
            ).lastrowid
            record_event(db, user, entry_id, "start_shift", "Staff started shift")
            result = {
                "state": "working",
                "entry_id": entry_id,
                "clock_in": at.isoformat(),
                "break_minutes": 0,
            }
    else:
        if not active or (payload.entry_id and active["id"] != payload.entry_id):
            raise HTTPException(
                409,
                "The active shift changed. Refresh the current shift before continuing.",
            )
        entry_id = active["id"]
        if active["origin"] != "clock":
            raise HTTPException(
                409,
                "This legacy open shift needs management correction before clocking can resume",
            )
        running = db.execute(
            "SELECT * FROM shift_breaks WHERE entry_id=? AND ended_at IS NULL",
            (entry_id,),
        ).fetchone()
        if payload.action == "break_start":
            if running:
                raise HTTPException(409, "A break is already running")
            db.execute(
                "INSERT INTO shift_breaks(entry_id,started_at,paid,actor_id) VALUES(?,?,?,?)",
                (entry_id, at.isoformat(), int(payload.paid_break), user["id"]),
            )
            db.execute(
                "UPDATE time_entries SET break_started_at=? WHERE id=?",
                (at.isoformat(), entry_id),
            )
            result = {
                "state": "on_break",
                "entry_id": entry_id,
                "break_started_at": at.isoformat(),
            }
        else:
            if payload.action == "break_end" and not running:
                raise HTTPException(409, "No break is currently running")
            if running:
                db.execute(
                    "UPDATE shift_breaks SET ended_at=? WHERE id=?",
                    (at.isoformat(), running["id"]),
                )
            intervals = rows(
                db.execute("SELECT * FROM shift_breaks WHERE entry_id=?", (entry_id,))
            )
            unpaid = sum(
                duration(stamp(b["started_at"]), stamp(b["ended_at"]))
                for b in intervals
                if not b["paid"]
            )
            paid = sum(
                duration(stamp(b["started_at"]), stamp(b["ended_at"]))
                for b in intervals
                if b["paid"]
            )
            db.execute(
                "UPDATE time_entries SET break_started_at=NULL,unpaid_seconds=?,paid_break_seconds=?,break_minutes=? WHERE id=?",
                (unpaid, paid, (unpaid + paid) // 60, entry_id),
            )
            result = {
                "state": "working",
                "entry_id": entry_id,
                "break_minutes": (unpaid + paid) // 60,
            }
            if payload.action == "out":
                elapsed = duration(stamp(active["clock_in"]), at)
                if elapsed < unpaid + paid:
                    raise HTTPException(
                        409, "Invalid time intervals need management review"
                    )
                worked = elapsed - unpaid
                db.execute(
                    "UPDATE time_entries SET clock_out=?,elapsed_seconds=?,worked_seconds=?,hours=?,status='submitted',review_state='submitted' WHERE id=?",
                    (at.isoformat(), elapsed, worked, worked / 3600, entry_id),
                )
                result.update(
                    state="clocked_off",
                    clock_out=at.isoformat(),
                    hours=worked / 3600,
                    worked_seconds=worked,
                    submitted=True,
                )
        record_event(db, user, entry_id, payload.action, "Staff clock action", active)
    result["server_time"] = at.isoformat()
    if payload.request_id:
        db.execute(
            "INSERT INTO clock_requests VALUES(?,?,?,?,?)",
            (
                user["id"],
                payload.request_id,
                fingerprint,
                json.dumps(result),
                at.isoformat(),
            ),
        )
    return result


def entry_interval(entry):
    """Manual totals occupy their whole allocation period, never fake clock hours."""
    if entry["origin"] == "manual" or entry["entry_scope"] == "weekly":
        start = date.fromisoformat(
            entry["week_start"]
            if entry["entry_scope"] == "weekly"
            else entry["work_date"]
        )
        end = start + timedelta(days=7 if entry["entry_scope"] == "weekly" else 1)
        return (
            datetime.combine(start, datetime.min.time(), TZ).astimezone(timezone.utc),
            datetime.combine(end, datetime.min.time(), TZ).astimezone(timezone.utc),
        )
    return (
        stamp(entry["clock_in"]),
        (
            stamp(entry["clock_out"])
            if entry["clock_out"]
            else datetime.max.replace(tzinfo=timezone.utc)
        ),
    )


def assert_no_entry_overlap(db, staff_id, entry, exclude_id=None):
    if entry["origin"] == "amendment":
        return
    start, end = entry_interval(entry)
    others = db.execute(
        "SELECT * FROM time_entries WHERE staff_id=? AND origin<>'amendment' AND id<>?",
        (staff_id, exclude_id or -1),
    ).fetchall()
    for other in others:
        lo, hi = entry_interval(other)
        if start < hi and end > lo:
            raise HTTPException(
                409,
                "Hours overlap another clock entry or manual allocation period. Ask management to reconcile the records before approval.",
            )


def flag_export_overlaps(db, snapshot):
    # Historical approval is not evidence that duplicate allocation was reconciled.
    for entry_id in {row["entry_id"] for row in snapshot["rows"]}:
        entry = db.execute(
            "SELECT * FROM time_entries WHERE id=?", (entry_id,)
        ).fetchone()
        try:
            assert_no_entry_overlap(db, entry["staff_id"], entry, entry_id)
        except HTTPException as exc:
            snapshot["issues"].append({"entry_id": entry_id, "reason": exc.detail})


def approve_entry(
    db,
    user,
    entry_id,
    *,
    action="approve",
    reason="Reviewed recorded hours",
    version=None,
):
    entry = authorised_entry(db, user, entry_id, review=True)
    if entry["staff_id"] == user["id"]:
        raise HTTPException(
            403,
            "You cannot approve or reject your own hours. Another authorised reviewer is required.",
        )
    if version is not None and version != entry["entry_version"]:
        raise HTTPException(409, "The entry changed. Review its latest version first.")
    if entry["status"] != "submitted" or not entry["clock_out"]:
        raise HTTPException(409, "Only completed submitted entries can be reviewed")
    if action == "approve":
        assert_no_entry_overlap(db, entry["staff_id"], entry, entry_id)
        db.execute(
            "UPDATE time_entries SET status='approved',review_state='approved',review_comment=?,approved_by=?,approved_at=? WHERE id=?",
            (reason, user["id"], now().isoformat(), entry_id),
        )
    else:
        db.execute(
            "UPDATE time_entries SET status='draft',review_state='rejected',review_comment=?,approved_by=NULL,approved_at=NULL WHERE id=?",
            (reason, entry_id),
        )
    record_event(db, user, entry_id, action, reason, entry)
    return {"approved": action == "approve", "entry_id": entry_id}


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["approve", "reject", "resubmit"]
    reason: str = Field(min_length=3, max_length=500)
    version: int = Field(ge=1)


class BreakInput(BaseModel):
    started_at: datetime
    ended_at: datetime
    paid: bool = False


class CorrectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    reason: str = Field(min_length=8, max_length=500)
    clock_in: datetime
    clock_out: datetime
    breaks: list[BreakInput] = Field(default_factory=list, max_length=24)


class AmendmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    work_date: date
    adjustment_seconds: int = Field(ge=-86400, le=86400)
    reason: str = Field(min_length=8, max_length=500)


class PeriodInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: Literal["daily", "weekly", "fortnightly", "monthly", "custom"] = "weekly"
    on: date | None = None
    start: date | None = None
    end: date | None = None
    staff_id: int | None = None
    location_id: int | None = None
    status: Literal["all", "open", "submitted", "approved", "rejected", "draft"] = "all"


class SettingsInput(BaseModel):
    week_start: int = Field(ge=0, le=6)
    fortnight_anchor: date
    long_shift_hours: int = Field(ge=8, le=48)


def period_bounds(db, filters: PeriodInput):
    config = dict(db.execute("SELECT * FROM workforce_settings WHERE id=1").fetchone())
    on = filters.on or now().astimezone(TZ).date()
    if filters.period == "daily":
        start, end = on, on
    elif filters.period == "weekly":
        start = on - timedelta(days=(on.weekday() - config["week_start"]) % 7)
        end = start + timedelta(days=6)
    elif filters.period == "fortnightly":
        anchor = date.fromisoformat(config["fortnight_anchor"])
        start = anchor + timedelta(days=((on - anchor).days // 14) * 14)
        end = start + timedelta(days=13)
    elif filters.period == "monthly":
        start, end = on.replace(day=1), on.replace(
            day=calendar.monthrange(on.year, on.month)[1]
        )
    else:
        if not filters.start or not filters.end:
            raise HTTPException(422, "Choose a custom start and end date")
        start, end = filters.start, filters.end
    if end < start or (end - start).days > 366:
        raise HTTPException(422, "Use a reporting period of at most 367 days")
    return start, end, config


def overlap_seconds(a, b, start, end):
    return max(0, duration(max(a, start), min(b, end)))


def report(db, user, filters: PeriodInput) -> dict:
    start, end, config = period_bounds(db, filters)
    permitted = scope_ids(db, user)
    if (
        filters.staff_id is not None
        and permitted is not None
        and filters.staff_id not in permitted
    ):
        raise HTTPException(403, "That worker is outside your permitted team")
    query = """SELECT t.*,u.first_name,u.last_name,u.staff_number,l.name location_name,
      a.first_name approver_first,a.last_name approver_last FROM time_entries t JOIN users u ON u.id=t.staff_id
      JOIN locations l ON l.id=t.location_id LEFT JOIN users a ON a.id=t.approved_by WHERE 1=1"""
    params = []
    if permitted is not None:
        query += (
            " AND t.staff_id IN (" + (",".join("?" for _ in permitted) or "NULL") + ")"
        )
        params += permitted
    for key in ("staff_id", "location_id"):
        if getattr(filters, key) is not None:
            query += f" AND t.{key}=?"
            params.append(getattr(filters, key))
    source = rows(db.execute(query + " ORDER BY t.clock_in,t.id", params))
    lower = datetime.combine(start, time.min, TZ).astimezone(timezone.utc)
    upper = datetime.combine(end + timedelta(days=1), time.min, TZ).astimezone(
        timezone.utc
    )
    result, issues, open_shifts = [], [], []
    for entry in source:
        status = (
            "open"
            if not entry["clock_out"]
            else (
                "approved"
                if entry["status"] == "exported"
                else (
                    entry["review_state"]
                    if entry["review_state"] == "rejected"
                    else entry["status"]
                )
            )
        )
        if filters.status != "all" and status != filters.status:
            continue
        if not entry["clock_out"]:
            if stamp(entry["clock_in"]) < upper and now() >= lower:
                open_shifts.append(
                    {
                        "id": entry["id"],
                        "staff_id": entry["staff_id"],
                        "name": f"{entry['first_name']} {entry['last_name']}",
                        "clock_in": entry["clock_in"],
                        "location": entry["location_name"],
                        "long_running": duration(stamp(entry["clock_in"]), now())
                        > config["long_shift_hours"] * 3600,
                    }
                )
            continue
        slices = []
        if entry["origin"] == "clock":
            a, b = stamp(entry["clock_in"]), stamp(entry["clock_out"])
            if a >= upper or b <= lower:
                continue
            breaks = rows(
                db.execute(
                    "SELECT * FROM shift_breaks WHERE entry_id=?", (entry["id"],)
                )
            )
            day = max(start, a.astimezone(TZ).date())
            while (
                day <= end
                and datetime.combine(day, time.min, TZ).astimezone(timezone.utc) < b
            ):
                lo = datetime.combine(day, time.min, TZ).astimezone(timezone.utc)
                hi = datetime.combine(day + timedelta(days=1), time.min, TZ).astimezone(
                    timezone.utc
                )
                elapsed = overlap_seconds(a, b, lo, hi)
                unpaid = sum(
                    overlap_seconds(
                        stamp(r["started_at"]), stamp(r["ended_at"]), lo, hi
                    )
                    for r in breaks
                    if r["ended_at"] and not r["paid"]
                )
                paid = sum(
                    overlap_seconds(
                        stamp(r["started_at"]), stamp(r["ended_at"]), lo, hi
                    )
                    for r in breaks
                    if r["ended_at"] and r["paid"]
                )
                slices.append((day, elapsed - unpaid, unpaid, paid))
                day += timedelta(days=1)
        else:
            day = date.fromisoformat(
                entry["work_date"]
                or stamp(entry["clock_in"]).astimezone(TZ).date().isoformat()
            )
            last = day + timedelta(days=6) if entry["entry_scope"] == "weekly" else day
            if day > end or last < start:
                continue
            if day < start or last > end:
                issues.append(
                    {
                        "entry_id": entry["id"],
                        "reason": "Manual weekly total crosses this period. A reviewed daily allocation is required; it has not been prorated.",
                    }
                )
                continue
            seconds = (
                entry["worked_seconds"]
                if entry["worked_seconds"] is not None
                else int(Decimal(str(entry["hours"] or 0)) * 3600)
            )
            slices.append(
                (
                    day,
                    seconds,
                    entry["unpaid_seconds"] or entry["break_minutes"] * 60,
                    entry["paid_break_seconds"],
                )
            )
        for day, worked, unpaid, paid in slices:
            exported = db.execute(
                "SELECT batch_id FROM hour_export_items WHERE entry_id=? AND entry_version=? AND work_date=?",
                (entry["id"], entry["entry_version"], day.isoformat()),
            ).fetchone()
            result.append(
                {
                    "entry_id": entry["id"],
                    "version": entry["entry_version"],
                    "staff_id": entry["staff_id"],
                    "worker_number": entry["staff_number"],
                    "staff_name": f"{entry['first_name']} {entry['last_name']}".strip(),
                    "date": day.isoformat(),
                    "timezone": "Australia/Melbourne",
                    "location": entry["location_name"],
                    "clock_in": (
                        stamp(entry["clock_in"]).astimezone(TZ).isoformat()
                        if entry["origin"] == "clock"
                        else "Not clock-recorded"
                    ),
                    "clock_out": (
                        stamp(entry["clock_out"]).astimezone(TZ).isoformat()
                        if entry["origin"] == "clock"
                        else "Not clock-recorded"
                    ),
                    "worked_seconds": worked,
                    "unpaid_break_seconds": unpaid,
                    "paid_break_seconds": paid,
                    "approved_seconds": worked if status == "approved" else 0,
                    "status": status,
                    "origin": entry["origin"],
                    "approved_by": entry["approved_by"],
                    "approved_at": entry["approved_at"],
                    "approver": f"{entry['approver_first'] or ''} {entry['approver_last'] or ''}".strip(),
                    "export_batch": exported[0] if exported else None,
                    "notes": entry["notes"] or "",
                    "review_comment": entry["review_comment"],
                    "amendment_of": entry["amendment_of"],
                }
            )
            result[-1]["entry_scope"] = entry["entry_scope"]
            result[-1]["export_note"] = (
                "Reviewed working time; no pay rules applied. "
                + (
                    "Weekly total: daily allocation required for payroll."
                    if entry["entry_scope"] == "weekly"
                    else "Daily work-date allocation."
                )
            )
    totals = {
        key: sum(r[key] for r in result)
        for key in (
            "worked_seconds",
            "approved_seconds",
            "paid_break_seconds",
            "unpaid_break_seconds",
        )
    }
    totals.update(
        unapproved_seconds=totals["worked_seconds"] - totals["approved_seconds"],
        shift_count=len({r["entry_id"] for r in result}),
        open_count=len(open_shifts),
        exported_seconds=sum(r["worked_seconds"] for r in result if r["export_batch"]),
    )
    daily = {}
    for row in result:
        bucket = daily.setdefault(
            row["date"],
            {"date": row["date"], "worked_seconds": 0, "approved_seconds": 0},
        )
        for key in ("worked_seconds", "approved_seconds"):
            bucket[key] += row[key]
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "timezone": "Australia/Melbourne",
        "generated_at": now().isoformat(),
        "settings": config,
        "rows": result,
        "totals": totals,
        "daily": list(daily.values()),
        "open_shifts": open_shifts,
        "issues": issues,
        "pay_rules_applied": False,
    }


EXPORT_FIELDS = [
    ("worker_number", "Worker number"),
    ("staff_name", "Staff name"),
    ("date", "Business date"),
    ("timezone", "Timezone"),
    ("location", "Location"),
    ("clock_in", "Shift start"),
    ("clock_out", "Shift finish"),
    ("unpaid_break_seconds", "Unpaid break seconds"),
    ("paid_break_seconds", "Paid break seconds"),
    ("worked_seconds", "Worked seconds"),
    ("approved_hours", "Approved hours"),
    ("entry_id", "Entry ID"),
    ("version", "Version"),
    ("approved_at", "Approved at UTC"),
    ("approver", "Approved by"),
    ("origin", "Source"),
    ("amendment_of", "Amends entry"),
]


EXPORT_FIELDS.append(("export_note", "Accounting note"))


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(
        ("=", "+", "-", "@", "\t", "\r")
    ):
        return "'" + value
    return value


def export_rows(snapshot):
    return [
        [
            safe_cell(
                (row["approved_seconds"] / 3600)
                if key == "approved_hours"
                else row.get(key, "")
            )
            for key, _ in EXPORT_FIELDS
        ]
        for row in snapshot["rows"]
    ]


def workbook_bytes(snapshot) -> bytes:
    """Small deployable OOXML writer; all text is inline strings, never Excel formulas."""

    def col(n):
        text = ""
        while n:
            n, k = divmod(n - 1, 26)
            text = chr(65 + k) + text
        return text

    def sheet(data, summary=False):
        xml = []
        for i, row in enumerate(data, 1):
            cells = []
            for j, value in enumerate(row, 1):
                address = f"{col(j)}{i}"
                if isinstance(value, (int, float)):
                    cells.append(
                        f'<c r="{address}" s="{2 if isinstance(value,float) else 0}"><v>{value}</v></c>'
                    )
                else:
                    text = "".join(
                        c for c in str(value or "") if c in "\t\n\r" or ord(c) >= 32
                    )
                    cells.append(
                        f'<c r="{address}" t="inlineStr" s="{1 if i==1 else 0}"><is><t xml:space="preserve">{escape(text)}</t></is></c>'
                    )
            xml.append(
                f'<row r="{i}" ht="{34 if i==1 else 44}" customHeight="1">'
                + "".join(cells)
                + "</row>"
            )

        def column_width(index):
            if summary:
                return 36 if index == 1 else 88
            return 40 if index == 18 else 32 if index in (2, 5, 6, 7, 14, 15) else 24

        widths = "".join(
            f'<col min="{i}" max="{i}" width="{column_width(i)}" customWidth="1"/>'
            for i in range(1, len(data[0]) + 1)
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>'
            + widths
            + "</cols><sheetData>"
            + "".join(xml)
            + '</sheetData><autoFilter ref="A1:'
            + col(len(data[0]))
            + str(len(data))
            + '"/></worksheet>'
        )

    summary = [
        ["HV Swim approved hours", "Value"],
        ["Period", snapshot["start"] + " to " + snapshot["end"]],
        ["Timezone", "Australia/Melbourne"],
        ["Approved seconds", snapshot["totals"]["approved_seconds"]],
        ["Approved hours", snapshot["totals"]["approved_seconds"] / 3600],
        ["Exported rows", len(snapshot["rows"])],
        ["Prepared at", snapshot["generated_at"]],
        ["Units", "Seconds are authoritative. Hours are decimal display values."],
        ["Boundary", "Approved working time, not award-classified payroll or payment."],
        ["Source", "Immutable HV Swim approved-entry snapshot"],
    ]
    content_types = (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in (1, 2)
        )
        + "</Types>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        parts = {
            "[Content_Types].xml": content_types,
            "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
            "xl/workbook.xml": '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Approved hours" sheetId="1" r:id="rId1"/><sheet name="Summary" sheetId="2" r:id="rId2"/></sheets></workbook>',
            "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(
                f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                for i in (1, 2)
            )
            + '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
            "xl/styles.xml": '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF061A3B"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"><alignment vertical="center"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" applyFill="1"><alignment wrapText="1" vertical="center"/></xf><xf numFmtId="4" fontId="0" fillId="0" borderId="0" applyNumberFormat="1"/></cellXfs></styleSheet>',
            "xl/worksheets/sheet1.xml": sheet(
                [[label for _, label in EXPORT_FIELDS]] + export_rows(snapshot)
            ),
            "xl/worksheets/sheet2.xml": sheet(summary),
        }
        for name, text in parts.items():
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            if name == "xl/styles.xml":
                text = text.replace(
                    '<alignment vertical="center"/>',
                    '<alignment vertical="center" wrapText="1"/>',
                ).replace('numFmtId="4"', 'numFmtId="0"')
            if name == "xl/worksheets/sheet2.xml":
                text = sheet(summary, True)
            z.writestr(info, text.encode())
    return buffer.getvalue()


def register(app, session_user, csrf_guard):
    @app.get("/api/workforce/shift")
    def current_shift(user=Depends(session_user)):
        with db_session() as db:
            scope_ids(db, user)
            entry = db.execute(
                "SELECT t.*,l.name location_name FROM time_entries t JOIN locations l ON l.id=t.location_id WHERE staff_id=? AND clock_out IS NULL",
                (user["id"],),
            ).fetchone()
            today = report(db, user, PeriodInput(period="daily", staff_id=user["id"]))
            week = report(db, user, PeriodInput(staff_id=user["id"]))
            return {
                "entry": dict(entry) if entry else None,
                "breaks": (
                    rows(
                        db.execute(
                            "SELECT * FROM shift_breaks WHERE entry_id=?",
                            (entry["id"],),
                        )
                    )
                    if entry
                    else []
                ),
                "server_time": now().isoformat(),
                "today_seconds": today["totals"]["worked_seconds"],
                "week_seconds": week["totals"]["worked_seconds"],
                "long_shift_hours": week["settings"]["long_shift_hours"],
            }

    @app.post("/api/workforce/clock")
    def clock(
        payload: ClockAction,
        request: Request,
        user=Depends(session_user),
        x_csrf_token: str | None = Header(default=None),
    ):
        csrf_guard(request, user, x_csrf_token)
        with db_session() as db:
            scope_ids(db, user)
            return clock_action(db, user, payload)

    @app.get("/api/workforce/report")
    def hours_report(filters: PeriodInput = Depends(), user=Depends(session_user)):
        with db_session() as db:
            return report(db, user, filters)

    @app.get("/api/workforce/people")
    def people(user=Depends(session_user)):
        with db_session() as db:
            permitted = scope_ids(db, user)
            staff = rows(
                db.execute(
                    "SELECT id,first_name,last_name,staff_number,active FROM users WHERE role IN ('staff','admin') ORDER BY first_name"
                )
            )
            return {
                "staff": [
                    r for r in staff if permitted is None or r["id"] in permitted
                ],
                "locations": rows(db.execute("SELECT id,name,slug FROM locations")),
                "can_review": user["role"] == "admin",
            }

    @app.get("/api/workforce/export-preview")
    def export_preview(filters: PeriodInput = Depends(), user=Depends(session_user)):
        with db_session() as db:
            permitted = scope_ids(db, user, review=True)
            snapshot = report(
                db, user, filters.model_copy(update={"status": "approved"})
            )
            snapshot["rows"] = [
                r
                for r in snapshot["rows"]
                if not r["export_batch"]
                and (permitted is None or r["staff_id"] in permitted)
            ]
            snapshot["totals"] = {
                "approved_seconds": sum(r["approved_seconds"] for r in snapshot["rows"])
            }
            flag_export_overlaps(db, snapshot)
            return snapshot

    @app.get("/api/workforce/entries/{entry_id}/history")
    def history(entry_id: int, user=Depends(session_user)):
        with db_session() as db:
            authorised_entry(db, user, entry_id)
            events = rows(
                db.execute(
                    "SELECT e.*,u.first_name,u.last_name FROM time_entry_events e JOIN users u ON u.id=e.actor_id WHERE entry_id=? ORDER BY e.id",
                    (entry_id,),
                )
            )
            for e in events:
                e["before"] = (
                    json.loads(e.pop("before_json")) if e["before_json"] else None
                )
                e["after"] = json.loads(e.pop("after_json"))
            return {
                "events": events,
                "breaks": rows(
                    db.execute(
                        "SELECT * FROM shift_breaks WHERE entry_id=?", (entry_id,)
                    )
                ),
            }

    @app.post("/api/workforce/entries/{entry_id}/review")
    def review(
        entry_id: int,
        payload: ReviewInput,
        request: Request,
        user=Depends(session_user),
        x_csrf_token: str | None = Header(default=None),
    ):
        csrf_guard(request, user, x_csrf_token)
        if not payload.reason.strip():
            raise HTTPException(422, "Enter a review reason")
        with db_session() as db:
            db.execute("BEGIN IMMEDIATE")
            if payload.action == "resubmit":
                entry = authorised_entry(db, user, entry_id)
                if (
                    entry["staff_id"] != user["id"]
                    or entry["status"] != "draft"
                    or not entry["clock_out"]
                    or entry["entry_version"] != payload.version
                ):
                    raise HTTPException(
                        409, "Only your own completed current draft can be resubmitted"
                    )
                db.execute(
                    "UPDATE time_entries SET status='submitted',review_state='submitted',review_comment=? WHERE id=?",
                    (payload.reason, entry_id),
                )
                record_event(db, user, entry_id, "resubmit", payload.reason, entry)
                return {"submitted": True}
            return approve_entry(
                db,
                user,
                entry_id,
                action=payload.action,
                reason=payload.reason,
                version=payload.version,
            )

    @app.post("/api/workforce/entries/{entry_id}/correct")
    def correct(
        entry_id: int,
        payload: CorrectionInput,
        request: Request,
        user=Depends(session_user),
        x_csrf_token: str | None = Header(default=None),
    ):
        csrf_guard(request, user, x_csrf_token)
        try:
            a, b = stamp(payload.clock_in.isoformat()), stamp(
                payload.clock_out.isoformat()
            )
            breaks = sorted(
                [
                    (
                        stamp(r.started_at.isoformat()),
                        stamp(r.ended_at.isoformat()),
                        r.paid,
                    )
                    for r in payload.breaks
                ]
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if (
            b <= a
            or b > now()
            or duration(a, b) > 7 * 86400
            or len(payload.reason.strip()) < 8
        ):
            raise HTTPException(
                422,
                "Use a completed, non-future interval of at most seven days and a meaningful reason",
            )
        previous = a
        for lo, hi, _ in breaks:
            if lo < previous or hi <= lo or hi > b:
                raise HTTPException(
                    422, "Breaks must be within the shift and cannot overlap"
                )
            previous = hi
        with db_session() as db:
            db.execute("BEGIN IMMEDIATE")
            entry = authorised_entry(db, user, entry_id, review=True)
            if entry["entry_version"] != payload.version:
                raise HTTPException(409, "Entry changed; reload before correcting")
            if (
                entry["status"] == "exported"
                or entry["xero_timesheet_id"]
                or db.execute(
                    "SELECT 1 FROM hour_export_items WHERE entry_id=?", (entry_id,)
                ).fetchone()
            ):
                raise HTTPException(
                    409,
                    "Exported hours are immutable. Create a separately approved amendment instead.",
                )
            assert_no_entry_overlap(
                db,
                entry["staff_id"],
                dict(entry)
                | {
                    "origin": "clock",
                    "entry_scope": "daily",
                    "clock_in": a.isoformat(),
                    "clock_out": b.isoformat(),
                },
                entry_id,
            )
            old_breaks = rows(
                db.execute("SELECT * FROM shift_breaks WHERE entry_id=?", (entry_id,))
            )
            unpaid = sum(duration(lo, hi) for lo, hi, paid in breaks if not paid)
            paid = sum(duration(lo, hi) for lo, hi, paid in breaks if paid)
            day = a.astimezone(TZ).date()
            db.execute(
                "UPDATE time_entries SET clock_in=?,clock_out=?,hours=?,elapsed_seconds=?,worked_seconds=?,unpaid_seconds=?,paid_break_seconds=?,break_minutes=?,break_started_at=NULL,origin='clock',entry_scope='daily',work_date=?,week_start=?,status='submitted',review_state='submitted',approved_by=NULL,approved_at=NULL,entry_version=entry_version+1 WHERE id=?",
                (
                    a.isoformat(),
                    b.isoformat(),
                    (duration(a, b) - unpaid) / 3600,
                    duration(a, b),
                    duration(a, b) - unpaid,
                    unpaid,
                    paid,
                    (unpaid + paid) // 60,
                    day.isoformat(),
                    (day - timedelta(days=day.weekday())).isoformat(),
                    entry_id,
                ),
            )
            db.execute("DELETE FROM shift_breaks WHERE entry_id=?", (entry_id,))
            for lo, hi, paid in breaks:
                db.execute(
                    "INSERT INTO shift_breaks(entry_id,started_at,ended_at,paid,actor_id) VALUES(?,?,?,?,?)",
                    (entry_id, lo.isoformat(), hi.isoformat(), int(paid), user["id"]),
                )
            record_event(
                db,
                user,
                entry_id,
                "correct",
                payload.reason,
                dict(entry) | {"breaks": old_breaks},
            )
            return {"corrected": True, "requires_reapproval": True}

    @app.post("/api/workforce/entries/{entry_id}/amend")
    def amend(
        entry_id: int,
        payload: AmendmentInput,
        request: Request,
        user=Depends(session_user),
        x_csrf_token: str | None = Header(default=None),
    ):
        csrf_guard(request, user, x_csrf_token)
        with db_session() as db:
            db.execute("BEGIN IMMEDIATE")
            entry = authorised_entry(db, user, entry_id, review=True)
            if (
                not db.execute(
                    "SELECT 1 FROM hour_export_items WHERE entry_id=? AND work_date=?",
                    (entry_id, payload.work_date.isoformat()),
                ).fetchone()
                or not payload.adjustment_seconds
                or payload.work_date > now().astimezone(TZ).date()
            ):
                raise HTTPException(
                    409,
                    "Amendments require exported hours on the affected date, a non-zero adjustment and a non-future work date",
                )
            if len(payload.reason.strip()) < 8:
                raise HTTPException(
                    422, "Explain the amendment in at least eight characters"
                )
            at = datetime.combine(payload.work_date, time.min, TZ).isoformat()
            new_id = db.execute(
                "INSERT INTO time_entries(staff_id,location_id,clock_in,clock_out,hours,worked_seconds,status,review_state,origin,amendment_of,work_date,week_start,notes) VALUES(?,?,?,?,?,?,'submitted','submitted','amendment',?,?,?,?)",
                (
                    entry["staff_id"],
                    entry["location_id"],
                    at,
                    at,
                    payload.adjustment_seconds / 3600,
                    payload.adjustment_seconds,
                    entry_id,
                    payload.work_date.isoformat(),
                    (
                        payload.work_date - timedelta(days=payload.work_date.weekday())
                    ).isoformat(),
                    payload.reason,
                ),
            ).lastrowid
            record_event(db, user, new_id, "amend", payload.reason)
            return {"entry_id": new_id, "requires_approval": True}

    @app.get("/api/workforce/exports")
    def batches(user=Depends(session_user)):
        with db_session() as db:
            scope_ids(db, user, review=True)
            result = []
            for batch in db.execute(
                "SELECT * FROM hour_export_batches ORDER BY id DESC"
            ):
                snapshot = json.loads(batch["snapshot"])
                permitted = scope_ids(db, user, review=True)
                if permitted is not None and any(
                    r["staff_id"] not in permitted for r in snapshot["rows"]
                ):
                    continue
                result.append(
                    {
                        "id": batch["id"],
                        "created_at": batch["created_at"],
                        "start": snapshot["start"],
                        "end": snapshot["end"],
                        "approved_seconds": snapshot["totals"]["approved_seconds"],
                        "rows": len(snapshot["rows"]),
                    }
                )
            return {"batches": result}

    @app.post("/api/workforce/exports")
    def create_batch(
        payload: PeriodInput,
        request: Request,
        user=Depends(session_user),
        x_csrf_token: str | None = Header(default=None),
    ):
        csrf_guard(request, user, x_csrf_token)
        with db_session() as db:
            db.execute("BEGIN IMMEDIATE")
            permitted = scope_ids(db, user, review=True)
            snapshot = report(
                db, user, payload.model_copy(update={"status": "approved"})
            )
            snapshot["rows"] = [
                r
                for r in snapshot["rows"]
                if not r["export_batch"]
                and (permitted is None or r["staff_id"] in permitted)
            ]
            flag_export_overlaps(db, snapshot)
            if snapshot["issues"]:
                raise HTTPException(
                    409,
                    "Resolve overlapping hours or unallocated weekly totals before export",
                )
            if not snapshot["rows"]:
                raise HTTPException(
                    409,
                    "No new approved hours. Re-download the existing batch instead.",
                )
            snapshot["totals"] = {
                "approved_seconds": sum(r["approved_seconds"] for r in snapshot["rows"])
            }
            fingerprint = hashlib.sha256(
                json.dumps(
                    [
                        (r["entry_id"], r["version"], r["date"], r["approved_seconds"])
                        for r in snapshot["rows"]
                    ],
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            ident = db.execute(
                "INSERT INTO hour_export_batches(fingerprint,created_by,created_at,snapshot) VALUES(?,?,?,?)",
                (fingerprint, user["id"], now().isoformat(), json.dumps(snapshot)),
            ).lastrowid
            for row in snapshot["rows"]:
                db.execute(
                    "INSERT INTO hour_export_items VALUES(?,?,?,?)",
                    (ident, row["entry_id"], row["version"], row["date"]),
                )
            audit(
                db,
                user["id"],
                "create_approved_hours_export",
                "hour_export",
                ident,
                {
                    "approved_seconds": snapshot["totals"]["approved_seconds"],
                    "rows": len(snapshot["rows"]),
                },
            )
            return {"batch_id": ident, "transmitted": False}

    @app.get("/api/workforce/exports/{batch_id}.{format}")
    def download(
        batch_id: int, format: Literal["csv", "xlsx"], user=Depends(session_user)
    ):
        with db_session() as db:
            permitted = scope_ids(db, user, review=True)
            batch = db.execute(
                "SELECT * FROM hour_export_batches WHERE id=?", (batch_id,)
            ).fetchone()
            if not batch:
                raise HTTPException(404, "Export not found")
            snapshot = json.loads(batch["snapshot"])
            if permitted is not None and any(
                r["staff_id"] not in permitted for r in snapshot["rows"]
            ):
                raise HTTPException(404, "Export not found in your permitted team")
        if format == "csv":
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow([v for _, v in EXPORT_FIELDS])
            writer.writerows(export_rows(snapshot))
            content = buffer.getvalue().encode("utf-8-sig")
            media = "text/csv"
        else:
            content = workbook_bytes(snapshot)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return Response(
            content,
            media_type=media,
            headers={
                "Content-Disposition": f'attachment; filename="hv-approved-hours-{batch_id}.{format}"',
                "Cache-Control": "no-store",
            },
        )

    @app.patch("/api/workforce/settings")
    def settings_update(
        payload: SettingsInput,
        request: Request,
        user=Depends(session_user),
        x_csrf_token: str | None = Header(default=None),
    ):
        csrf_guard(request, user, x_csrf_token)
        if user["role"] != "admin":
            raise HTTPException(403, "Owner access required")
        with db_session() as db:
            db.execute(
                "UPDATE workforce_settings SET week_start=?,fortnight_anchor=?,long_shift_hours=? WHERE id=1",
                (
                    payload.week_start,
                    payload.fortnight_anchor.isoformat(),
                    payload.long_shift_hours,
                ),
            )
            audit(
                db,
                user["id"],
                "workforce_settings",
                "settings",
                detail=payload.model_dump(mode="json"),
            )
        return {"saved": True}
