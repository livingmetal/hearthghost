"""Fail-closed PostgreSQL configuration from a mounted secret file."""

from __future__ import annotations

from pathlib import Path


DEFAULT_POSTGRES_DSN_FILE = "/run/secrets/hearthghost-postgres-dsn"
MAX_DSN_LENGTH = 4096


def read_postgres_dsn(path: str | Path = DEFAULT_POSTGRES_DSN_FILE) -> str:
    secret_path = Path(path)
    if secret_path.is_symlink():
        raise ValueError("PostgreSQL DSN secret may not be a symlink")
    if not secret_path.is_file():
        raise ValueError("PostgreSQL DSN secret file is missing")
    try:
        raw = secret_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError("PostgreSQL DSN secret file is unreadable") from error
    dsn = raw.strip()
    if not dsn or len(dsn) > MAX_DSN_LENGTH or "\x00" in dsn or "\n" in dsn or "\r" in dsn:
        raise ValueError("PostgreSQL DSN secret is invalid")
    return dsn
