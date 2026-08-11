"""SQLite-backed scoped todo repository."""

from __future__ import annotations

import os
import sqlite3
import stat
from datetime import datetime
from pathlib import Path
from threading import RLock

from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.todo import TodoRecord, TodoState


_SCHEMA = """
CREATE TABLE IF NOT EXISTS todo_records (
    todo_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    text TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS todo_scope_created_idx
ON todo_records(scope, scope_id, created_at DESC, todo_id DESC);
"""


class SqliteTodoRepository:
    """Persistent todo repository sharing the hardened personal-data DB path."""

    def __init__(self, path: Path) -> None:
        requested = Path(path)
        if requested.is_symlink():
            raise ValueError("todo database path may not be a symlink")
        parent = requested.parent
        if parent.exists():
            if not parent.is_dir():
                raise ValueError("todo database parent must be a directory")
            mode = stat.S_IMODE(parent.stat().st_mode)
            if mode & 0o077:
                raise ValueError("todo database parent must be owner-only")
        else:
            parent.mkdir(mode=0o700, parents=True, exist_ok=False)
        self._path = requested.resolve()
        if self._path.exists() and not self._path.is_file():
            raise ValueError("todo database path must be a file")
        self._lock = RLock()
        self._initialize()

    def put(self, record: object) -> None:
        if not isinstance(record, TodoRecord):
            raise TypeError("todo repository accepts TodoRecord only")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO todo_records (
                    todo_id, scope, scope_id, text, state, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                _encode(record),
            )

    def get(self, todo_id: str) -> TodoRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT todo_id, scope, scope_id, text, state, created_at, completed_at
                FROM todo_records WHERE todo_id = ?
                """,
                (todo_id,),
            ).fetchone()
        return None if row is None else _decode(row)

    def list_scope(self, scope: str, scope_id: str, *, limit: int) -> tuple[TodoRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT todo_id, scope, scope_id, text, state, created_at, completed_at
                FROM todo_records
                WHERE scope = ? AND scope_id = ?
                ORDER BY created_at DESC, todo_id DESC
                LIMIT ?
                """,
                (scope, scope_id, limit),
            ).fetchall()
        return tuple(_decode(row) for row in rows)

    def replace(self, record: object) -> None:
        if not isinstance(record, TodoRecord):
            raise TypeError("todo repository accepts TodoRecord only")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE todo_records
                SET scope = ?, scope_id = ?, text = ?, state = ?, created_at = ?, completed_at = ?
                WHERE todo_id = ?
                """,
                (
                    record.scope.value,
                    record.scope_id,
                    record.text,
                    record.state.value,
                    record.created_at.isoformat(),
                    record.completed_at.isoformat() if record.completed_at is not None else None,
                    record.todo_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("todo does not exist")

    def delete(self, todo_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM todo_records WHERE todo_id = ?",
                (todo_id,),
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


def _encode(record: TodoRecord) -> tuple[object, ...]:
    return (
        record.todo_id,
        record.scope.value,
        record.scope_id,
        record.text,
        record.state.value,
        record.created_at.isoformat(),
        record.completed_at.isoformat() if record.completed_at is not None else None,
    )


def _decode(row: sqlite3.Row) -> TodoRecord:
    try:
        created_at = datetime.fromisoformat(row["created_at"])
        completed_raw = row["completed_at"]
        completed_at = (
            datetime.fromisoformat(completed_raw)
            if completed_raw is not None
            else None
        )
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("naive created_at")
        if completed_at is not None and (
            completed_at.tzinfo is None or completed_at.utcoffset() is None
        ):
            raise ValueError("naive completed_at")
        state = TodoState(row["state"])
        if state is TodoState.OPEN and completed_at is not None:
            raise ValueError("open todo cannot have completed_at")
        if state is TodoState.COMPLETED and completed_at is None:
            raise ValueError("completed todo requires completed_at")
        return TodoRecord(
            todo_id=row["todo_id"],
            scope=MemoryScope(row["scope"]),
            scope_id=row["scope_id"],
            text=row["text"],
            state=state,
            created_at=created_at,
            completed_at=completed_at,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("todo database contains invalid record") from error
