"""Atomic PostgreSQL claim/lease repository for due reminder delivery work."""

from __future__ import annotations

from datetime import datetime
from typing import Callable
from uuid import uuid4

from apps.assistant.src.adapters.postgres_schema import ensure_postgres_schema
from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.reminder import ReminderRecord, ReminderSource, ReminderState
from apps.assistant.src.modules.reminder_scheduler import ReminderDeliveryClaim


class PostgresReminderClaimRepository:
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
        return "PostgresReminderClaimRepository(dsn=<redacted>)"

    def claim_due(
        self,
        *,
        now: datetime,
        claim_owner: str,
        claim_until: datetime,
    ) -> ReminderDeliveryClaim | None:
        _require_aware(now, "now")
        _require_aware(claim_until, "claim_until")
        if claim_until <= now:
            raise ValueError("claim_until must be after now")
        _require_identifier(claim_owner, "claim_owner")
        claim_token = str(uuid4())
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH candidate AS (
                        SELECT reminder_id
                        FROM reminder_records
                        WHERE state = 'scheduled'
                          AND fire_at <= %s
                          AND (
                              (delivery_state = 'pending' AND next_attempt_at <= %s)
                              OR (delivery_state = 'claimed' AND claim_until <= %s)
                          )
                        ORDER BY fire_at, reminder_id
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE reminder_records AS record
                    SET delivery_state = 'claimed',
                        claim_token = %s,
                        claim_owner = %s,
                        claim_until = %s,
                        attempt_count = record.attempt_count + 1,
                        last_attempt_at = %s,
                        last_delivery_reason = NULL
                    FROM candidate
                    WHERE record.reminder_id = candidate.reminder_id
                    RETURNING
                        record.reminder_id::text, record.scope, record.scope_id,
                        record.todo_id::text, record.fire_at, record.source,
                        record.created_by_node_id, record.created_at,
                        record.state, record.cancelled_at,
                        record.claim_token::text, record.claim_owner,
                        record.claim_until, record.attempt_count,
                        record.last_attempt_at
                    """,
                    (now, now, now, claim_token, claim_owner, claim_until, now),
                )
                row = cursor.fetchone()
        return None if row is None else _decode_claim(row)

    def claim_is_current(self, claim: object) -> bool:
        claim = _require_claim(claim)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 1
                    FROM reminder_records
                    WHERE reminder_id = %s
                      AND scope = %s
                      AND scope_id = %s
                      AND state = 'scheduled'
                      AND delivery_state = 'claimed'
                      AND claim_token = %s
                      AND claim_owner = %s
                      AND claim_until > CURRENT_TIMESTAMP
                      AND fire_at = %s
                    """,
                    (
                        claim.reminder.reminder_id,
                        claim.reminder.scope.value,
                        claim.reminder.scope_id,
                        claim.claim_token,
                        claim.claim_owner,
                        claim.reminder.fire_at,
                    ),
                )
                return cursor.fetchone() is not None

    def mark_delivered(
        self,
        claim: object,
        *,
        delivered_at: datetime,
        reason: str,
    ) -> bool:
        _require_aware(delivered_at, "delivered_at")
        return self._finish(
            _require_claim(claim),
            delivery_state="delivered",
            next_attempt_at=None,
            delivered_at=delivered_at,
            reason=_require_reason(reason),
        )

    def mark_retry(
        self,
        claim: object,
        *,
        next_attempt_at: datetime,
        reason: str,
    ) -> bool:
        _require_aware(next_attempt_at, "next_attempt_at")
        return self._finish(
            _require_claim(claim),
            delivery_state="pending",
            next_attempt_at=next_attempt_at,
            delivered_at=None,
            reason=_require_reason(reason),
        )

    def mark_exhausted(self, claim: object, *, reason: str) -> bool:
        return self._finish(
            _require_claim(claim),
            delivery_state="exhausted",
            next_attempt_at=None,
            delivered_at=None,
            reason=_require_reason(reason),
        )

    def _finish(
        self,
        claim: ReminderDeliveryClaim,
        *,
        delivery_state: str,
        next_attempt_at: datetime | None,
        delivered_at: datetime | None,
        reason: str,
    ) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE reminder_records
                    SET delivery_state = %s,
                        claim_token = NULL,
                        claim_owner = NULL,
                        claim_until = NULL,
                        next_attempt_at = %s,
                        delivered_at = %s,
                        last_delivery_reason = %s
                    WHERE reminder_id = %s
                      AND scope = %s
                      AND scope_id = %s
                      AND state = 'scheduled'
                      AND delivery_state = 'claimed'
                      AND claim_token = %s
                      AND claim_owner = %s
                      AND fire_at = %s
                    """,
                    (
                        delivery_state,
                        next_attempt_at,
                        delivered_at,
                        reason,
                        claim.reminder.reminder_id,
                        claim.reminder.scope.value,
                        claim.reminder.scope_id,
                        claim.claim_token,
                        claim.claim_owner,
                        claim.reminder.fire_at,
                    ),
                )
                return cursor.rowcount == 1

    def _connect(self):
        return self._connect_factory(self._dsn, connect_timeout=5)


def _decode_claim(row: object) -> ReminderDeliveryClaim:
    try:
        values = tuple(row)
        if len(values) != 15:
            raise ValueError("unexpected claim column count")
        fire_at, created_at, cancelled_at = values[4], values[7], values[9]
        claim_until, last_attempt_at = values[12], values[14]
        for timestamp in (fire_at, created_at, claim_until, last_attempt_at):
            _require_aware(timestamp, "claim timestamp")
        if cancelled_at is not None:
            raise ValueError("claimed reminder may not be cancelled")
        reminder = ReminderRecord(
            reminder_id=str(values[0]),
            scope=MemoryScope(values[1]),
            scope_id=values[2],
            todo_id=str(values[3]),
            fire_at=fire_at,
            source=ReminderSource(values[5]),
            created_by_node_id=values[6],
            created_at=created_at,
            state=ReminderState(values[8]),
            cancelled_at=cancelled_at,
        )
        return ReminderDeliveryClaim(
            reminder=reminder,
            claim_token=str(values[10]),
            claim_owner=values[11],
            claim_until=claim_until,
            attempt_count=values[13],
            claimed_at=last_attempt_at,
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError("reminder claim database contains invalid record") from error


def _require_claim(value: object) -> ReminderDeliveryClaim:
    if not isinstance(value, ReminderDeliveryClaim):
        raise TypeError("reminder delivery claim is invalid")
    return value


def _require_aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _require_identifier(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 128
        or "\x00" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(f"{name} is invalid")
    return value


def _require_reason(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 128 or "\x00" in value:
        raise ValueError("delivery reason is invalid")
    return value
