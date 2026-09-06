"""Xero AU 2.0 draft-timesheet adapter, with durable per-employee outcomes.

The web release intentionally has no live payroll action. An operator must supply
provider-verified pay periods/rates before this adapter can be enabled in a later
deployment. Invoice OAuth is not evidence of payroll readiness. Tests use MockTransport.
Official contract: XeroAPI/Xero-OpenAPI/xero-payroll-au-v2.yaml.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from uuid import UUID

import httpx

from .database import db_session
from .integrations import _xero_headers
from .security import now_iso

API = "https://api.xero.com/payroll.xro/2.0/Timesheets"


def migrate():
    with db_session() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS payroll_jobs(
          id INTEGER PRIMARY KEY, batch_id INTEGER NOT NULL REFERENCES hour_export_batches(id),
          tenant_id TEXT NOT NULL, employee_id TEXT NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
          idempotency_key TEXT UNIQUE NOT NULL, request_json TEXT NOT NULL, expected_seconds INTEGER NOT NULL,
          status TEXT NOT NULL DEFAULT 'prepared' CHECK(status IN('prepared','in_flight','confirmed','review','rejected')),
          provider_id TEXT, safe_error TEXT, updated_at TEXT NOT NULL,
          UNIQUE(tenant_id,employee_id,period_start,period_end))""")
        db.execute(
            """CREATE TABLE IF NOT EXISTS payroll_job_events(id INTEGER PRIMARY KEY,
          job_id INTEGER NOT NULL REFERENCES payroll_jobs(id),state TEXT NOT NULL,provider_id TEXT,created_at TEXT NOT NULL)"""
        )
        for operation in ("UPDATE", "DELETE"):
            db.execute(
                f"CREATE TRIGGER IF NOT EXISTS payroll_events_no_{operation.lower()} BEFORE {operation} ON payroll_job_events BEGIN SELECT RAISE(ABORT,'Payroll history is immutable'); END"
            )
        db.execute(
            "CREATE TRIGGER IF NOT EXISTS payroll_payload_immutable BEFORE UPDATE OF batch_id,tenant_id,employee_id,period_start,period_end,idempotency_key,request_json,expected_seconds ON payroll_jobs BEGIN SELECT RAISE(ABORT,'Payroll job source is immutable'); END"
        )


def uuid_value(value):
    try:
        result = UUID(str(value))
        if result.int == 0:
            raise ValueError
        return str(result)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("A provider-verified, non-zero Xero UUID is required") from exc


def prepare(db, batch_id, tenant_id, mappings, periods):
    """Prepare from an immutable approved batch and independently verified resources.

    mappings: staff_id -> employee/calendar/earnings UUIDs; periods: calendar UUID ->
    start/end/tenant/verified_from_provider. Neither structure accepts browser claims.
    """
    tenant_id = uuid_value(tenant_id)
    batch = db.execute(
        "SELECT snapshot FROM hour_export_batches WHERE id=?", (batch_id,)
    ).fetchone()
    if not batch:
        raise ValueError("Approved export batch not found")
    snapshot = json.loads(batch[0])
    groups = defaultdict(list)
    for row in snapshot["rows"]:
        if (
            row["status"] != "approved"
            or row["origin"] in {"legacy", "amendment"}
            or row["approved_seconds"] <= 0
        ):
            raise ValueError(
                "Legacy, non-positive or amendment rows need manual payroll review"
            )
        groups[row["staff_id"]].append(row)
    plans = []
    for staff_id, records in groups.items():
        mapping = mappings.get(staff_id, {})
        employee = uuid_value(mapping.get("employee_id"))
        calendar = uuid_value(mapping.get("calendar_id"))
        earnings = uuid_value(mapping.get("earnings_rate_id"))
        period = periods.get(calendar, {})
        if (
            not period.get("verified_from_provider")
            or period.get("tenant_id") != tenant_id
        ):
            raise ValueError(
                "Import and verify the employee pay period and rate from this Xero organisation first"
            )
        if (
            mapping.get("verified_tenant_id") != tenant_id
            or mapping.get("earnings_unit") != "HOURS"
        ):
            raise ValueError(
                "Verify employee, calendar and hourly earnings-rate mappings in the same organisation"
            )
        if snapshot["start"] != period.get("start") or snapshot["end"] != period.get(
            "end"
        ):
            raise ValueError(
                "The export must match the complete verified employee pay period"
            )
        daily = defaultdict(int)
        for row in records:
            if not period["start"] <= row["date"] <= period["end"]:
                raise ValueError("Entry date falls outside the verified pay period")
            if row.get("entry_scope") == "weekly":
                raise ValueError(
                    "Allocate manual weekly hours to reviewed days before Xero export"
                )
            daily[row["date"]] += row["approved_seconds"]
        payload = {
            "employeeID": employee,
            "payrollCalendarID": calendar,
            "startDate": period["start"],
            "endDate": period["end"],
            "timesheetLines": [
                {
                    "date": day,
                    "earningsRateID": earnings,
                    "numberOfUnits": float(Decimal(seconds) / 3600),
                }
                for day, seconds in sorted(daily.items())
            ],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        key = (
            "hv-hours-"
            + hashlib.sha256(f"{tenant_id}:{batch_id}:{encoded}".encode()).hexdigest()
        )
        plans.append((employee, period, payload, encoded, key, sum(daily.values())))
    # Validate every employee before adding any jobs. Caller uses BEGIN IMMEDIATE.
    result = []
    for employee, period, payload, encoded, key, seconds in plans:
        existing = db.execute(
            "SELECT * FROM payroll_jobs WHERE tenant_id=? AND employee_id=? AND period_start=? AND period_end=?",
            (tenant_id, employee, period["start"], period["end"]),
        ).fetchone()
        if existing:
            if existing["idempotency_key"] != key:
                raise ValueError(
                    "This employee pay period already has a different batch; reconcile it instead of creating a duplicate"
                )
            result.append(existing["id"])
            continue
        ident = db.execute(
            "INSERT INTO payroll_jobs(batch_id,tenant_id,employee_id,period_start,period_end,idempotency_key,request_json,expected_seconds,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                batch_id,
                tenant_id,
                employee,
                period["start"],
                period["end"],
                key,
                encoded,
                seconds,
                now_iso(),
            ),
        ).lastrowid
        result.append(ident)
    return result


def verify_response(payload, response, expected_seconds):
    if not isinstance(response, dict):
        raise ValueError("Provider returned an invalid timesheet response")
    if response.get("problem"):
        raise ValueError("Provider reported a payroll problem")
    sheet = response.get("timesheet") or {}
    if not isinstance(sheet, dict):
        raise ValueError("Provider returned an invalid timesheet")
    provider_id = uuid_value(sheet.get("timesheetID"))
    for key in ("employeeID", "payrollCalendarID"):
        if sheet.get(key) != payload[key]:
            raise ValueError("Provider returned a different employee or calendar")
    for key in ("startDate", "endDate"):
        if str(sheet.get(key, ""))[:10] != payload[key]:
            raise ValueError("Provider returned a different pay period")
    if sheet.get("status") != "Draft":
        raise ValueError("Expected a draft timesheet; approval remains in Xero")
    expected = {
        (line["date"], line["earningsRateID"]): Decimal(str(line["numberOfUnits"]))
        for line in payload["timesheetLines"]
    }
    actual = {}
    for line in sheet.get("timesheetLines", []):
        uuid_value(line.get("timesheetLineID"))
        key = (str(line.get("date", ""))[:10], line.get("earningsRateID"))
        if key in actual:
            raise ValueError("Provider returned duplicate daily lines")
        actual[key] = Decimal(str(line.get("numberOfUnits")))
    if actual.keys() != expected.keys():
        raise ValueError("Provider timesheet lines do not match")
    tolerance = Decimal("0.01")  # hundredth of a second, not a payroll rounding policy
    if any(abs(actual[k] - expected[k]) * 3600 > tolerance for k in expected):
        raise ValueError("Provider daily units do not reconcile")
    if abs(Decimal(str(sheet.get("totalHours"))) * 3600 - expected_seconds) > tolerance:
        raise ValueError("Provider total does not reconcile to approved seconds")
    return provider_id


async def dispatch(job_ids, token, *, authorised=False, transport=None):
    """Explicit dispatch, no automatic uncertain retries; one durable result per person.

    There is no HTTP route enabling this function in this release. Setting a legacy
    XERO_SYNC_ENABLED variable cannot activate it. Token refresh belongs to the existing
    serialized OAuth boundary before invocation; secrets never enter job snapshots.
    """
    if not authorised:
        raise ValueError("Live payroll transmission is not authorised")
    tenant = uuid_value(token.get("tenant_id"))
    results = []
    async with httpx.AsyncClient(timeout=20, transport=transport) as client:
        for job_id in job_ids:
            with db_session() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT * FROM payroll_jobs WHERE id=? AND tenant_id=?",
                    (job_id, tenant),
                ).fetchone()
                if not row:
                    raise ValueError("Payroll job does not belong to this organisation")
                if row["status"] != "prepared":
                    results.append(
                        {
                            "job_id": job_id,
                            "status": row["status"],
                            "provider_id": row["provider_id"],
                            "sent": False,
                        }
                    )
                    continue
                db.execute(
                    "UPDATE payroll_jobs SET status='in_flight',updated_at=? WHERE id=?",
                    (now_iso(), job_id),
                )
                db.execute(
                    "INSERT INTO payroll_job_events(job_id,state,created_at) VALUES(?,'in_flight',?)",
                    (job_id, now_iso()),
                )
            payload = json.loads(row["request_json"])
            provider_id = None
            state = "review"
            error = None
            try:
                response = await client.post(
                    API,
                    json=payload,
                    headers=_xero_headers(
                        token, idempotency_key=row["idempotency_key"]
                    ),
                )
                if response.status_code in (400, 401, 403, 422):
                    state = "rejected"
                    error = "Xero rejected the request. Check mappings, scope and approval before preparing any replacement."
                else:
                    response.raise_for_status()
                    data = response.json()
                    provider_id = verify_response(
                        payload, data, row["expected_seconds"]
                    )
                    state = "confirmed"
            except (httpx.HTTPError, ValueError, TypeError, ArithmeticError, KeyError):
                error = "Provider outcome or reconciliation is uncertain. Check this employee period in Xero; no automatic retry is permitted."
            with db_session() as db:
                db.execute(
                    "UPDATE payroll_jobs SET status=?,provider_id=?,safe_error=?,updated_at=? WHERE id=?",
                    (state, provider_id, error, now_iso(), job_id),
                )
                db.execute(
                    "INSERT INTO payroll_job_events(job_id,state,provider_id,created_at) VALUES(?,?,?,?)",
                    (job_id, state, provider_id, now_iso()),
                )
            results.append(
                {
                    "job_id": job_id,
                    "status": state,
                    "provider_id": provider_id,
                    "sent": True,
                }
            )
    return results
