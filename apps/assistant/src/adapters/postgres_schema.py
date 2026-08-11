"""Versioned HearthGhost PostgreSQL schema migrations.

Migrations are serialized with a transaction-scoped advisory lock. Existing
MVP tables are adopted by idempotent CREATE TABLE IF NOT EXISTS migrations;
no destructive inference or downgrade is attempted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


MIGRATION_LOCK_KEY = 4_410_381_099_431_121_971


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str


MIGRATIONS = (
    Migration(
        1,
        "memory_records_v1",
        """
        CREATE TABLE IF NOT EXISTS memory_records (
            memory_id UUID PRIMARY KEY,
            scope TEXT NOT NULL CHECK (scope IN ('user', 'household')),
            scope_id TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('semantic', 'user_preference', 'note')),
            text TEXT NOT NULL,
            source TEXT NOT NULL CHECK (source = 'addressed_text'),
            source_conversation_session_id TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS memory_scope_created_idx
        ON memory_records(scope, scope_id, created_at DESC, memory_id DESC);
        """,
    ),
    Migration(
        2,
        "todo_records_v1",
        """
        CREATE TABLE IF NOT EXISTS todo_records (
            todo_id UUID PRIMARY KEY,
            scope TEXT NOT NULL CHECK (scope IN ('user', 'household')),
            scope_id TEXT NOT NULL,
            text TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('open', 'completed')),
            created_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ NULL,
            CHECK (
                (state = 'open' AND completed_at IS NULL)
                OR (state = 'completed' AND completed_at IS NOT NULL)
            )
        );
        CREATE INDEX IF NOT EXISTS todo_scope_state_created_idx
        ON todo_records(scope, scope_id, state, created_at DESC, todo_id DESC);
        """,
    ),
    Migration(
        3,
        "todo_due_at_v1",
        """
        ALTER TABLE todo_records
        ADD COLUMN IF NOT EXISTS due_at TIMESTAMPTZ NULL;
        CREATE INDEX IF NOT EXISTS todo_scope_due_idx
        ON todo_records(scope, scope_id, due_at, todo_id)
        WHERE state = 'open' AND due_at IS NOT NULL;
        """,
    ),
    Migration(
        4,
        "reminder_records_v1",
        """
        CREATE TABLE IF NOT EXISTS reminder_records (
            reminder_id UUID PRIMARY KEY,
            scope TEXT NOT NULL CHECK (scope IN ('user', 'household')),
            scope_id TEXT NOT NULL,
            todo_id UUID NOT NULL,
            fire_at TIMESTAMPTZ NOT NULL,
            source TEXT NOT NULL CHECK (source = 'todo_due'),
            created_by_node_id TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('scheduled', 'cancelled')),
            cancelled_at TIMESTAMPTZ NULL,
            CHECK (
                (state = 'scheduled' AND cancelled_at IS NULL)
                OR (state = 'cancelled' AND cancelled_at IS NOT NULL)
            )
        );
        CREATE UNIQUE INDEX IF NOT EXISTS reminder_one_active_per_todo_idx
        ON reminder_records(scope, scope_id, todo_id)
        WHERE state = 'scheduled';
        CREATE INDEX IF NOT EXISTS reminder_due_idx
        ON reminder_records(fire_at, reminder_id)
        WHERE state = 'scheduled';
        CREATE INDEX IF NOT EXISTS reminder_scope_created_idx
        ON reminder_records(scope, scope_id, created_at DESC, reminder_id DESC);
        """,
    ),
)


class PostgresSchemaError(RuntimeError):
    pass


def ensure_postgres_schema(dsn: str, *, connect: Callable | None = None) -> int:
    if not isinstance(dsn, str) or not dsn.strip() or "\x00" in dsn:
        raise ValueError("PostgreSQL DSN is invalid")
    if connect is None:
        import psycopg

        connect = psycopg.connect

    try:
        with connect(dsn, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_KEY,))
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS hearthghost_schema_migrations (
                        version INTEGER PRIMARY KEY CHECK (version > 0),
                        name TEXT NOT NULL UNIQUE,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    "SELECT version, name FROM hearthghost_schema_migrations ORDER BY version"
                )
                rows = cursor.fetchall()
                applied = _validate_applied_migrations(rows)
                latest_known = MIGRATIONS[-1].version if MIGRATIONS else 0
                if applied and max(applied) > latest_known:
                    raise PostgresSchemaError("database schema is newer than this HearthGhost build")

                for migration in MIGRATIONS:
                    if migration.version in applied:
                        if applied[migration.version] != migration.name:
                            raise PostgresSchemaError("database migration name does not match this build")
                        continue
                    cursor.execute(migration.sql)
                    cursor.execute(
                        "INSERT INTO hearthghost_schema_migrations (version, name) VALUES (%s, %s)",
                        (migration.version, migration.name),
                    )
                    applied[migration.version] = migration.name
                return max(applied, default=0)
    except PostgresSchemaError:
        raise
    except Exception as error:
        raise PostgresSchemaError("PostgreSQL schema migration failed") from error


def _validate_applied_migrations(rows: object) -> dict[int, str]:
    if not isinstance(rows, (list, tuple)):
        raise PostgresSchemaError("database migration metadata is invalid")
    applied: dict[int, str] = {}
    expected_names = {migration.version: migration.name for migration in MIGRATIONS}
    for row in rows:
        try:
            version, name = tuple(row)
        except (TypeError, ValueError) as error:
            raise PostgresSchemaError("database migration metadata is invalid") from error
        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version <= 0
            or not isinstance(name, str)
            or not name
            or version in applied
        ):
            raise PostgresSchemaError("database migration metadata is invalid")
        if version in expected_names and name != expected_names[version]:
            raise PostgresSchemaError("database migration name does not match this build")
        applied[version] = name
    if applied:
        versions = sorted(applied)
        if versions != list(range(1, max(versions) + 1)):
            raise PostgresSchemaError("database migration history has gaps")
    return applied
