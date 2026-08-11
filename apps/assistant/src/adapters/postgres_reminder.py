"""PostgreSQL reminder repository with scoped/idempotent scheduling queries."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from apps.assistant.src.adapters.postgres_schema import ensure_postgres_schema
from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.reminder import ReminderRecord, ReminderSource, ReminderState


class PostgresReminderRepository:
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
        return "PostgresReminderRepository(dsn=<redacted>)"

    def put(self, record: object) -> None:
        if not isinstance(record, ReminderRecord):
            raise TypeError("reminder repository accepts ReminderRecord only")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO reminder_records (
                        reminder_id, scope, scope_id, todo_id, fire_at, source,
                        created_by_node_id, created_at, state, cancelled_at,
                        delivery_state, next_attempt_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)
                    """,
                    (
                        record.reminder_id,
                        record.scope.value,
                        record.scope_id,
                        record.todo_id,
                        record.fire_at,
                        record.source.value,
                        record.created_by_node_id,
                        record.created_at,
                        record.state.value,
                        record.cancelled_at,
                        record.fire_at if record.state is ReminderState.SCHEDULED else None,
                    ),
                )

    def get(self, reminder_id: str) -> ReminderRecord | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT reminder_id::text, scope, scope_id, todo_id::text,
                           fire_at, source, created_by_node_id, created_at,
                           state, cancelled_at
                    FROM reminder_records
                    WHERE reminder_id = %s
                    """,
                    (reminder_id,),
                )
                row = cursor.fetchone()
        return None if row is None else _decode(row)

    def find_active_for_todo(self, scope: str, scope_id: str, todo_id: str) -> ReminderRecord | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT reminder_id::text, scope, scope_id, todo_id::text,
                           fire_at, source, created_by_node_id, created_at,
                           state, cancelled_at
                    FROM reminder_records
                    WHERE scope = %s AND scope_id = %s AND todo_id = %s
                      AND state = 'scheduled'
                    LIMIT 2
                    """,
                    (scope, scope_id, todo_id),
                )
                rows = cursor.fetchall()
        if len(rows) > 1:
            raise RuntimeError("multiple active reminders exist for one todo")
        return None if not rows else _decode(rows[0])

    def list_scope(self, scope: str, scope_id: str, *, limit: int) -> tuple[ReminderRecord, ...]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT reminder_id::text, scope, scope_id, todo_id::text,
                           fire_at, source, created_by_node_id, created_at,
                           state, cancelled_at
                    FROM reminder_records
                    WHERE scope = %s AND scope_id = %s
                    ORDER BY created_at DESC, reminder_id DESC
                    LIMIT %s
                    """,
                    (scope, scope_id, limit),
                )
                rows = cursor.fetchall()
        return tuple(_decode(row) for row in rows)

    def replace(self, record: object) -> None:
        if not isinstance(record, ReminderRecord):
            raise TypeError("reminder repository accepts ReminderRecord only")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE reminder_records
                    SET fire_at = %s,
                        state = %s,
                        cancelled_at = %s,
                        delivery_state = CASE
                            WHEN %s = 'scheduled' AND fire_at IS DISTINCT FROM %s THEN 'pending'
                            ELSE delivery_state
                        END,
                        claim_token = CASE
                            WHEN %s = 'scheduled' AND fire_at IS DISTINCT FROM %s THEN NULL
                            ELSE claim_token
                        END,
                        claim_owner = CASE
                            WHEN %s = 'scheduled' AND fire_at IS DISTINCT FROM %s THEN NULL
                            ELSE claim_owner
                        END,
                        claim_until = CASE
                            WHEN %s = 'scheduled' AND fire_at IS DISTINCT FROM %s THEN NULL
                            ELSE claim_until
                        END,
                        attempt_count = CASE
                            WHEN %s = 'scheduled' AND fire_at IS DISTINCT FROM %s THEN 0
                            ELSE attempt_count
                        END,
                        next_attempt_at = CASE
                            WHEN %s = 'scheduled' AND fire_at IS DISTINCT FROM %s THEN %s
                            ELSE next_attempt_at
                        END,
                        delivered_at = CASE
                            WHEN %s = 'scheduled' AND fire_at IS DISTINCT FROM %s THEN NULL
                            ELSE delivered_at
                        END,
                        last_attempt_at = CASE
                            WHEN %s = 'scheduled' AND fire_at IS DISTINCT FROM %s THEN NULL
                            ELSE last_attempt_at
                        END,
                        last_delivery_reason = CASE
                            WHEN %s = 'scheduled' AND fire_at IS DISTINCT FROM %s THEN NULL
                            ELSE last_delivery_reason
                        END
                    WHERE reminder_id = %s AND scope = %s AND scope_id = %s
                    """,
                    (
                        record.fire_at,
                        record.state.value,
                        record.cancelled_at,
                        record.state.value, record.fire_at,
                        record.state.value, record.fire_at,
                        record.state.value, record.fire_at,
                        record.state.value, record.fire_at,
                        record.state.value, record.fire_at,
                        record.state.value, record.fire_at, record.fire_at,
                        record.state.value, record.fire_at,
                        record.state.value, record.fire_at,
                        record.state.value, record.fire_at,
                        record.reminder_id,
                        record.scope.value,
                        record.scope_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("reminder record disappeared or changed scope")

    def delete(self, reminder_id: str) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM reminder_records WHERE reminder_id = %s", (reminder_id,))
                return cursor.rowcount == 1

    def _connect(self):
        return self._connect_factory(self._dsn, connect_timeout=5)


def _decode(row: object) -> ReminderRecord:
    try:
        values = tuple(row)
        if len(values) != 10:
            raise ValueError("unexpected column count")
        fire_at, created_at, cancelled_at = values[4], values[7], values[9]
        if not _aware(fire_at) or not _aware(created_at):
            raise ValueError("reminder timestamps must be timezone-aware")
        if cancelled_at is not None and not _aware(cancelled_at):
            raise ValueError("cancelled_at must be timezone-aware")
        state = ReminderState(values[8])
        if (state is ReminderState.SCHEDULED) != (cancelled_at is None):
            raise ValueError("reminder state and cancelled_at disagree")
        return ReminderRecord(
            reminder_id=str(values[0]),
            scope=MemoryScope(values[1]),
            scope_id=values[2],
            todo_id=str(values[3]),
            fire_at=fire_at,
            source=ReminderSource(values[5]),
            created_by_node_id=values[6],
            created_at=created_at,
            state=state,
            cancelled_at=cancelled_at,
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError("reminder database contains invalid record") from error


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
