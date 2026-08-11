"""SQLite-backed long-term memory repository with exact-scope queries."""

from __future__ import annotations

import os
import sqlite3
import stat
from datetime import datetime
from pathlib import Path
from threading import RLock

from apps.assistant.src.modules.memory import (
    MemoryKind,
    MemoryRecord,
    MemoryScope,
    MemorySource,
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_records (
    memory_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    source_conversation_session_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS memory_scope_created_idx
ON memory_records(scope, scope_id, created_at DESC, memory_id DESC);
"""


class SqliteMemoryRepository:
    """Persistent repository requiring an owner-only storage directory."""

    def __init__(self, path: Path) -> None:
        requested = Path(path)
        if requested.is_symlink():
            raise ValueError("memory database path may not be a symlink")
        parent = requested.parent
        if parent.exists():
            if not parent.is_dir():
                raise ValueError("memory database parent must be a directory")
            mode = stat.S_IMODE(parent.stat().st_mode)
            if mode & 0o077:
                raise ValueError("memory database parent must be owner-only")
        else:
            parent.mkdir(mode=0o700, parents=True, exist_ok=False)
        self._path = requested.resolve()
        if self._path.exists() and not self._path.is_file():
            raise ValueError("memory database path must be a file")
        self._lock = RLock()
        self._initialize()

    @property
    def path(self) -> Path:
        return self._path

    def put(self, record: object) -> None:
        if not isinstance(record, MemoryRecord):
            raise TypeError("memory repository accepts MemoryRecord only")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_records (
                    memory_id, scope, scope_id, kind, text, source,
                    source_conversation_session_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.memory_id,
                    record.scope.value,
                    record.scope_id,
                    record.kind.value,
                    record.text,
                    record.source.value,
                    record.source_conversation_session_id,
                    record.created_at.isoformat(),
                ),
            )

    def get(self, memory_id: str) -> MemoryRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT memory_id, scope, scope_id, kind, text, source,
                       source_conversation_session_id, created_at
                FROM memory_records WHERE memory_id = ?
                """,
                (memory_id,),
            ).fetchone()
        return None if row is None else _decode(row)

    def list_scope(self, scope: str, scope_id: str, *, limit: int) -> tuple[MemoryRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT memory_id, scope, scope_id, kind, text, source,
                       source_conversation_session_id, created_at
                FROM memory_records
                WHERE scope = ? AND scope_id = ?
                ORDER BY created_at DESC, memory_id DESC
                LIMIT ?
                """,
                (scope, scope_id, limit),
            ).fetchall()
        return tuple(_decode(row) for row in rows)

    def delete(self, memory_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM memory_records WHERE memory_id = ?",
                (memory_id,),
            )
            return cursor.rowcount == 1

    def _initialize(self) -> None:
        with self._lock:
            with self._connect() as connection:
                connection.executescript(_SCHEMA)
            os.chmod(self._path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._path,
            timeout=5.0,
            isolation_level="DEFERRED",
        )
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        connection.row_factory = sqlite3.Row
        return connection


def _decode(row: sqlite3.Row) -> MemoryRecord:
    try:
        created_at = datetime.fromisoformat(row["created_at"])
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("naive timestamp")
        return MemoryRecord(
            memory_id=row["memory_id"],
            scope=MemoryScope(row["scope"]),
            scope_id=row["scope_id"],
            kind=MemoryKind(row["kind"]),
            text=row["text"],
            source=MemorySource(row["source"]),
            source_conversation_session_id=row["source_conversation_session_id"],
            created_at=created_at,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("memory database contains invalid record") from error
