"""Provider contract tests use labelled fake IDs and no live Xero connection."""

import asyncio
import json
import uuid

import httpx
import pytest

from test_api import client


def fixture_job():
    from backend.database import db_session
    from backend.payroll_adapter import prepare

    tenant, employee, calendar, earnings = [str(uuid.uuid4()) for _ in range(4)]
    row = {
        "status": "approved",
        "origin": "clock",
        "approved_seconds": 3601,
        "staff_id": 2,
        "date": "2026-08-03",
    }
    snapshot = {"start": "2026-08-03", "end": "2026-08-09", "rows": [row]}
    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        batch = db.execute(
            "INSERT INTO hour_export_batches(fingerprint,created_by,created_at,snapshot) VALUES(?,1,'2026-08-10',?)",
            (uuid.uuid4().hex, json.dumps(snapshot)),
        ).lastrowid
        mapping = {
            2: {
                "employee_id": employee,
                "calendar_id": calendar,
                "earnings_rate_id": earnings,
                "verified_tenant_id": tenant,
                "earnings_unit": "HOURS",
            }
        }
        periods = {
            calendar: {
                "start": "2026-08-03",
                "end": "2026-08-09",
                "tenant_id": tenant,
                "verified_from_provider": True,
            }
        }
        jobs = prepare(db, batch, tenant, mapping, periods)
        assert jobs == prepare(db, batch, tenant, mapping, periods)
    return jobs, {"tenant_id": tenant, "access_token": "labelled-test-token"}


def test_xero_au_contract_exact_units_and_duplicate_dispatch(client):
    from backend.payroll_adapter import dispatch

    jobs, token = fixture_job()
    calls = []

    def handler(request):
        calls.append(request)
        data = json.loads(request.content)
        assert str(request.url) == "https://api.xero.com/payroll.xro/2.0/Timesheets"
        assert request.headers["Idempotency-Key"].startswith("hv-hours-")
        assert request.headers["Xero-tenant-id"] == token["tenant_id"]
        lines = [
            line | {"timesheetLineID": str(uuid.uuid4())}
            for line in data["timesheetLines"]
        ]
        return httpx.Response(
            200,
            json={
                "timesheet": data
                | {
                    "timesheetID": str(uuid.uuid4()),
                    "status": "Draft",
                    "totalHours": 3601 / 3600,
                    "timesheetLines": lines,
                }
            },
        )

    with pytest.raises(ValueError, match="not authorised"):
        asyncio.run(dispatch(jobs, token, transport=httpx.MockTransport(handler)))
    result = asyncio.run(
        dispatch(jobs, token, authorised=True, transport=httpx.MockTransport(handler))
    )
    assert result[0]["status"] == "confirmed" and result[0]["provider_id"]
    result = asyncio.run(
        dispatch(jobs, token, authorised=True, transport=httpx.MockTransport(handler))
    )
    assert not result[0]["sent"] and len(calls) == 1


def test_uncertain_outcome_never_blindly_retries(client):
    from backend.payroll_adapter import dispatch

    jobs, token = fixture_job()
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("Controlled lost response")

    result = asyncio.run(
        dispatch(jobs, token, authorised=True, transport=httpx.MockTransport(handler))
    )
    assert result[0]["status"] == "review"
    again = asyncio.run(
        dispatch(jobs, token, authorised=True, transport=httpx.MockTransport(handler))
    )
    assert not again[0]["sent"] and len(calls) == 1


def test_partial_employee_results_are_persisted_independently(client):
    from backend.database import db_session
    from backend.payroll_adapter import dispatch

    jobs, token = fixture_job()
    with db_session() as db:
        row = dict(
            db.execute("SELECT * FROM payroll_jobs WHERE id=?", (jobs[0],)).fetchone()
        )
        payload = json.loads(row["request_json"])
        payload["employeeID"] = str(uuid.uuid4())
        second = db.execute(
            "INSERT INTO payroll_jobs(batch_id,tenant_id,employee_id,period_start,period_end,idempotency_key,request_json,expected_seconds,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                row["batch_id"],
                row["tenant_id"],
                payload["employeeID"],
                row["period_start"],
                row["period_end"],
                uuid.uuid4().hex,
                json.dumps(payload),
                3601,
                row["updated_at"],
            ),
        ).lastrowid
    calls = []

    def handler(request):
        data = json.loads(request.content)
        calls.append(data["employeeID"])
        if data["employeeID"] == payload["employeeID"]:
            raise httpx.ReadTimeout("Controlled second-employee response loss")
        lines = [
            line | {"timesheetLineID": str(uuid.uuid4())}
            for line in data["timesheetLines"]
        ]
        return httpx.Response(
            200,
            json={
                "timesheet": data
                | {
                    "timesheetID": str(uuid.uuid4()),
                    "status": "Draft",
                    "totalHours": 3601 / 3600,
                    "timesheetLines": lines,
                }
            },
        )

    result = asyncio.run(
        dispatch(
            jobs + [second],
            token,
            authorised=True,
            transport=httpx.MockTransport(handler),
        )
    )
    assert [r["status"] for r in result] == ["confirmed", "review"]
    retry = asyncio.run(
        dispatch(
            jobs + [second],
            token,
            authorised=True,
            transport=httpx.MockTransport(handler),
        )
    )
    assert all(not r["sent"] for r in retry) and len(calls) == 2


def test_wrong_provider_identity_or_units_requires_review(client):
    from backend.payroll_adapter import dispatch

    jobs, token = fixture_job()

    def handler(request):
        data = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "timesheet": data
                | {
                    "employeeID": str(uuid.uuid4()),
                    "timesheetID": str(uuid.uuid4()),
                    "status": "Draft",
                    "totalHours": 1,
                }
            },
        )

    result = asyncio.run(
        dispatch(jobs, token, authorised=True, transport=httpx.MockTransport(handler))
    )
    assert result[0]["status"] == "review"


def test_mapping_validation_rejects_missing_or_unverified_resources(client):
    from backend.payroll_adapter import uuid_value, prepare
    from backend.database import db_session

    for value in ("", None, "not-real", "00000000-0000-0000-0000-000000000000"):
        with pytest.raises(ValueError):
            uuid_value(value)
    jobs, token = fixture_job()
    with db_session() as db:
        batch = db.execute(
            "SELECT batch_id FROM payroll_jobs WHERE id=?", (jobs[0],)
        ).fetchone()[0]
        with pytest.raises(ValueError):
            prepare(db, batch, token["tenant_id"], {}, {})
