"""Durable PostgreSQL security state for Tool execution.

The replay ledger is intentionally small and credential-free.  Its job is to
make a consumed Policy decision remain consumed across Core restarts and across
multiple Core processes that share the same PostgreSQL database.
"""

from __future__ import annotations

from typing import Callable
from uuid import UUID

from apps.assistant.src.adapters.postgres_schema import ensure_postgres_schema


class PostgresDecisionReplayProtector:
    """Atomically consume Policy decision IDs using PostgreSQL uniqueness."""

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
        return "PostgresDecisionReplayProtector(dsn=<redacted>)"

    def consume(self, decision_id: str) -> bool:
        try:
            UUID(decision_id)
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError("decision_id must be a UUID") from error

        with self._connect_factory(self._dsn, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO tool_policy_decision_consumptions (decision_id)
                    VALUES (%s)
                    ON CONFLICT (decision_id) DO NOTHING
                    RETURNING decision_id::text
                    """,
                    (decision_id,),
                )
                row = cursor.fetchone()
        return row is not None
