"""PostgreSQL-backed long-term memory repository with exact-scope isolation."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from apps.assistant.src.adapters.postgres_schema import ensure_postgres_schema
from apps.assistant.src.modules.memory import (
    MemoryKind,
    MemoryRecord,
    MemoryScope,
    MemorySource,
)


class PostgresMemoryRepository:
    """Persistent repository using parameterized SQL and exact-scope queries."""

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
        return "PostgresMemoryRepository(dsn=<redacted>)"

    def put(self, record: object) -> None:
        if not isinstance(record, MemoryRecord):
            raise TypeError("memory repository accepts MemoryRecord only")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO memory_records (
                        memory_id, scope, scope_id, kind, text, source,
                        source_conversation_session_id, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record.memory_id,
                        record.scope.value,
                        record.scope_id,
                        record.kind.value,
                        record.text,
                        record.source.value,
                        record.source_conversation_session_id,
                        record.created_at,
                    ),
                )

    def get(self, memory_id: str) -> MemoryRecord | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT memory_id::text, scope, scope_id, kind, text, source,
                           source_conversation_session_id, created_at
                    FROM memory_records WHERE memory_id = %s
                    """,
                    (memory_id,),
                )
                row = cursor.fetchone()
        return None if row is None else _decode(row)

    def list_scope(self, scope: str, scope_id: str, *, limit: int) -> tuple[MemoryRecord, ...]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT memory_id::text, scope, scope_id, kind, text, source,
                           source_conversation_session_id, created_at
                    FROM memory_records
                    WHERE scope = %s AND scope_id = %s
                    ORDER BY created_at DESC, memory_id DESC
                    LIMIT %s
                    """,
                    (scope, scope_id, limit),
                )
                rows = cursor.fetchall()
        return tuple(_decode(row) for row in rows)

    def delete(self, memory_id: str) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM memory_records WHERE memory_id = %s", (memory_id,))
                return cursor.rowcount == 1

    def _connect(self):
        return self._connect_factory(self._dsn, connect_timeout=5)


def _decode(row: object) -> MemoryRecord:
    try:
        values = tuple(row)
        if len(values) != 8:
            raise ValueError("unexpected column count")
        created_at = values[7]
        if not isinstance(created_at, datetime) or created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("naive timestamp")
        return MemoryRecord(
            memory_id=str(values[0]),
            scope=MemoryScope(values[1]),
            scope_id=values[2],
            kind=MemoryKind(values[3]),
            text=values[4],
            source=MemorySource(values[5]),
            source_conversation_session_id=values[6],
            created_at=created_at,
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError("memory database contains invalid record") from error
