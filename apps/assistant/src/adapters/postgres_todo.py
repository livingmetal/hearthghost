"""PostgreSQL-backed todo repository with exact-scope storage semantics."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from apps.assistant.src.adapters.postgres_schema import ensure_postgres_schema
from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.todo import TodoRecord, TodoState


class PostgresTodoRepository:
    def __init__(self, dsn: str, *, connect: Callable | None = None) -> None:
        if not isinstance(dsn, str) or not dsn.strip() or "\x00" in dsn:
            raise ValueError("PostgreSQL DSN is invalid")
        if connect is None:
            import psycopg

            connect = psycopg.connect
        self._dsn = dsn
        self._connect_factory = connect
        ensure_postgres_schema(dsn, connect=connect)

    def __repr__(self) -> str:
        return "PostgresTodoRepository(dsn=<redacted>)"

    def put(self, record: object) -> None:
        if not isinstance(record, TodoRecord):
            raise TypeError("todo repository accepts TodoRecord only")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO todo_records (
                        todo_id, scope, scope_id, text, state, created_at, due_at, completed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record.todo_id,
                        record.scope.value,
                        record.scope_id,
                        record.text,
                        record.state.value,
                        record.created_at,
                        record.due_at,
                        record.completed_at,
                    ),
                )

    def get(self, todo_id: str) -> TodoRecord | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT todo_id::text, scope, scope_id, text, state,
                           created_at, due_at, completed_at
                    FROM todo_records WHERE todo_id = %s
                    """,
                    (todo_id,),
                )
                row = cursor.fetchone()
        return None if row is None else _decode(row)

    def list_scope(self, scope: str, scope_id: str, *, limit: int) -> tuple[TodoRecord, ...]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT todo_id::text, scope, scope_id, text, state,
                           created_at, due_at, completed_at
                    FROM todo_records
                    WHERE scope = %s AND scope_id = %s
                    ORDER BY created_at DESC, todo_id DESC
                    LIMIT %s
                    """,
                    (scope, scope_id, limit),
                )
                rows = cursor.fetchall()
        return tuple(_decode(row) for row in rows)

    def replace(self, record: object) -> None:
        if not isinstance(record, TodoRecord):
            raise TypeError("todo repository accepts TodoRecord only")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE todo_records
                    SET text = %s, state = %s, due_at = %s, completed_at = %s
                    WHERE todo_id = %s AND scope = %s AND scope_id = %s
                    """,
                    (
                        record.text,
                        record.state.value,
                        record.due_at,
                        record.completed_at,
                        record.todo_id,
                        record.scope.value,
                        record.scope_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("todo record disappeared or changed scope")

    def delete(self, todo_id: str) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM todo_records WHERE todo_id = %s", (todo_id,))
                return cursor.rowcount == 1

    def _connect(self):
        return self._connect_factory(self._dsn, connect_timeout=5)


def _decode(row: object) -> TodoRecord:
    try:
        values = tuple(row)
        if len(values) != 8:
            raise ValueError("unexpected column count")
        created_at = values[5]
        due_at = values[6]
        completed_at = values[7]
        for name, value in (("created_at", created_at), ("due_at", due_at), ("completed_at", completed_at)):
            if value is not None and (
                not isinstance(value, datetime)
                or value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError(f"{name} must be timezone-aware")
        state = TodoState(values[4])
        if (state is TodoState.OPEN) != (completed_at is None):
            raise ValueError("todo state and completed_at disagree")
        return TodoRecord(
            todo_id=str(values[0]),
            scope=MemoryScope(values[1]),
            scope_id=values[2],
            text=values[3],
            state=state,
            created_at=created_at,
            due_at=due_at,
            completed_at=completed_at,
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError("todo database contains invalid record") from error
