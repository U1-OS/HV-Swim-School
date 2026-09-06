#!/usr/bin/env python3
"""Consistent, non-overwriting SQLite backup. Does not copy encryption keys or uploads."""

import argparse
import os
import sqlite3
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path)
parser.add_argument("destination", type=Path)
args = parser.parse_args()
source, destination = (
    args.source.expanduser().resolve(),
    args.destination.expanduser().resolve(),
)
if not source.is_file():
    parser.error("Source database does not exist")
if source == destination or destination.exists():
    parser.error(
        "Destination must be a new file; backups never overwrite an existing file"
    )
if not destination.parent.is_dir():
    parser.error("Create a protected destination directory first")
descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
os.close(descriptor)
with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original:
    with sqlite3.connect(destination) as backup:
        original.backup(backup)
        if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise SystemExit(
                "Backup integrity check failed; retain this file for investigation, do not restore it"
            )
print(
    f"Verified SQLite backup: {destination}. Back up private uploads and encryption keys separately."
)
