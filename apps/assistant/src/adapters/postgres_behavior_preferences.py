"""PostgreSQL principal-scoped behavior preferences with optimistic revisions."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from apps.assistant.src.adapters.postgres_schema import ensure_postgres_schema
from apps.assistant.src.modules.persona import PersonaProfile
from apps.assistant.src.ports.behavior_preferences import (
    BehaviorPreferenceConflictError,
    StoredBehaviorPreferences,
)


class PostgresBehaviorPreferenceRepository:
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
        return "PostgresBehaviorPreferenceRepository(dsn=<redacted>)"

    def get(self, scope: str, scope_id: str) -> StoredBehaviorPreferences | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT scope, scope_id, character_name, humor, verbosity,
                           formality, initiative, expression_style,
                           followup_timeout_sec, proactive_frequency, revision, updated_at,
                           updated_by_node_id
                    FROM behavior_preference_records
                    WHERE scope = %s AND scope_id = %s
                    """,
                    (scope, scope_id),
                )
                row = cursor.fetchone()
        return None if row is None else _decode(row)

    def put(
        self,
        record: StoredBehaviorPreferences,
        *,
        expected_revision: int | None,
    ) -> StoredBehaviorPreferences:
        if not isinstance(record, StoredBehaviorPreferences):
            raise TypeError("behavior preference repository accepts StoredBehaviorPreferences only")
        values = (
            record.scope,
            record.scope_id,
            record.persona.name,
            record.persona.humor,
            record.persona.verbosity,
            record.persona.formality,
            record.persona.initiative,
            record.persona.expression_style,
            record.followup_timeout_sec,
            record.proactive_frequency,
            record.revision,
            record.updated_at,
            record.updated_by_node_id,
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                if expected_revision is None:
                    cursor.execute(
                        """
                        INSERT INTO behavior_preference_records (
                            scope, scope_id, character_name, humor, verbosity,
                            formality, initiative, expression_style,
                            followup_timeout_sec, proactive_frequency, revision, updated_at,
                            updated_by_node_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (scope, scope_id) DO NOTHING
                        """,
                        values,
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE behavior_preference_records
                        SET character_name = %s,
                            humor = %s,
                            verbosity = %s,
                            formality = %s,
                            initiative = %s,
                            expression_style = %s,
                            followup_timeout_sec = %s,
                            proactive_frequency = %s,
                            revision = %s,
                            updated_at = %s,
                            updated_by_node_id = %s
                        WHERE scope = %s AND scope_id = %s AND revision = %s
                        """,
                        (
                            record.persona.name,
                            record.persona.humor,
                            record.persona.verbosity,
                            record.persona.formality,
                            record.persona.initiative,
                            record.persona.expression_style,
                            record.followup_timeout_sec,
                            record.proactive_frequency,
                            record.revision,
                            record.updated_at,
                            record.updated_by_node_id,
                            record.scope,
                            record.scope_id,
                            expected_revision,
                        ),
                    )
                if cursor.rowcount != 1:
                    raise BehaviorPreferenceConflictError("behavior preference revision changed")
        return record

    def _connect(self):
        return self._connect_factory(self._dsn, connect_timeout=5)


def _decode(row: object) -> StoredBehaviorPreferences:
    try:
        values = tuple(row)
        if len(values) != 13:
            raise ValueError("unexpected column count")
        updated_at = values[11]
        if (
            not isinstance(updated_at, datetime)
            or updated_at.tzinfo is None
            or updated_at.utcoffset() is None
        ):
            raise ValueError("naive timestamp")
        revision = values[10]
        followup_timeout_sec = values[8]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision <= 0:
            raise ValueError("invalid revision")
        if (
            not isinstance(followup_timeout_sec, int)
            or isinstance(followup_timeout_sec, bool)
            or not 5 <= followup_timeout_sec <= 120
        ):
            raise ValueError("invalid timeout")
        return StoredBehaviorPreferences(
            scope=values[0],
            scope_id=values[1],
            persona=PersonaProfile(
                name=values[2],
                humor=values[3],
                verbosity=values[4],
                formality=values[5],
                initiative=values[6],
                expression_style=values[7],
            ),
            followup_timeout_sec=followup_timeout_sec,
            proactive_frequency=values[9],
            revision=revision,
            updated_at=updated_at,
            updated_by_node_id=values[12],
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError("behavior preference database contains invalid record") from error
