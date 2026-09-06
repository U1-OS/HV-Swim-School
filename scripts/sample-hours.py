#!/usr/bin/env python3
"""Generate labelled sample CSV/XLSX through the real isolated workflow APIs.

Never opens the configured business database, emails anyone or calls Xero.
Usage: .venv312/bin/python scripts/sample-hours.py /absolute/output/directory
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
output = Path(sys.argv[1]).expanduser().resolve()
output.mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory(prefix="hv-sample-export-") as temporary:
    os.environ.update(
        HV_DATA_DIR=temporary,
        HV_APP_ENV="development",
        HV_ENVIRONMENT="development",
        HV_PUBLIC_URL="http://testserver",
        DATABASE_URL="",
        HV_DATABASE_URL="",
    )
    from fastapi.testclient import TestClient
    from backend.server import app
    from backend import workforce
    from backend.database import db_session

    def login(client, email, password):
        response = client.post(
            "/api/auth/login", json={"email": email, "password": password}
        )
        response.raise_for_status()
        return {"X-CSRF-Token": response.json()["csrf_token"]}

    def post(client, path, body, headers):
        response = client.post(path, json=body, headers=headers)
        response.raise_for_status()
        return response.json()

    with TestClient(app) as client:
        with db_session() as db:
            staff = db.execute(
                "SELECT id FROM users WHERE email='staff@hvswim.demo'"
            ).fetchone()[0]
            db.execute(
                "UPDATE users SET first_name='SAMPLE ONLY',last_name='Instructor' WHERE id=?",
                (staff,),
            )
            db.execute(
                "UPDATE users SET first_name='SAMPLE ONLY',last_name='Reviewer' WHERE email='admin@hvswim.demo'"
            )
        headers = login(client, "staff@hvswim.demo", "StaffDemo!26")
        clock = datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)
        workforce.now = lambda: clock
        entries = []
        for day in range(3):
            clock = datetime(2026, 8, 3 + day, 0, 0, tzinfo=timezone.utc)
            entry = post(
                client,
                "/api/workforce/clock",
                {
                    "action": "in",
                    "location_slug": "wood-street",
                    "request_id": uuid.uuid4().hex,
                },
                headers,
            )["entry_id"]
            clock += timedelta(hours=2)
            post(
                client,
                "/api/workforce/clock",
                {
                    "action": "break_start",
                    "entry_id": entry,
                    "request_id": uuid.uuid4().hex,
                },
                headers,
            )
            clock += timedelta(minutes=15)
            post(
                client,
                "/api/workforce/clock",
                {
                    "action": "break_end",
                    "entry_id": entry,
                    "request_id": uuid.uuid4().hex,
                },
                headers,
            )
            clock += timedelta(hours=2, seconds=17 + day)
            post(
                client,
                "/api/workforce/clock",
                {"action": "out", "entry_id": entry, "request_id": uuid.uuid4().hex},
                headers,
            )
            entries.append(entry)
        client.cookies.clear()
        headers = login(client, "admin@hvswim.demo", "AdminDemo!26")
        for entry in entries:
            post(
                client,
                f"/api/workforce/entries/{entry}/review",
                {
                    "action": "approve",
                    "version": 1,
                    "reason": "SAMPLE ONLY - fictional export verification",
                },
                headers,
            )
        batch = post(
            client,
            "/api/workforce/exports",
            {"period": "weekly", "on": "2026-08-03", "staff_id": staff},
            headers,
        )
        for extension in ("csv", "xlsx"):
            response = client.get(
                f"/api/workforce/exports/{batch['batch_id']}.{extension}"
            )
            response.raise_for_status()
            target = output / f"HV-Swim-SAMPLE-approved-hours.{extension}"
            target.write_bytes(response.content)
            print(target)
        print(
            "Expected approved total: 43,254 seconds = 12.015 hours; three fictional shifts."
        )
