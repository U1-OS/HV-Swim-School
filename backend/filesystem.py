"""Restrictive permissions for on-disk customer and operational data."""

from __future__ import annotations

from pathlib import Path

PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600


def ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(PRIVATE_DIR_MODE)
    except OSError:
        pass


def harden_private_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        path.chmod(PRIVATE_FILE_MODE)
    except OSError:
        pass


def harden_database_files(db_path: Path) -> None:
    harden_private_file(db_path)
    harden_private_file(Path(f"{db_path}-wal"))
    harden_private_file(Path(f"{db_path}-shm"))
