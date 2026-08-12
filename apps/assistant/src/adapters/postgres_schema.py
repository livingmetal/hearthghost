"""Versioned HearthGhost PostgreSQL schema migrations.

Migrations are serialized with a transaction-scoped advisory lock. Existing
MVP tables are adopted by idempotent migrations; no downgrade is attempted.
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
            todo_id UUID NOT NULL REFERENCES todo_records(todo_id) ON DELETE CASCADE,
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

        CREATE OR REPLACE FUNCTION hearthghost_validate_reminder_scope()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM todo_records
                WHERE todo_id = NEW.todo_id
                  AND scope = NEW.scope
                  AND scope_id = NEW.scope_id
            ) THEN
                RAISE EXCEPTION 'reminder scope does not match todo scope';
            END IF;
            RETURN NEW;
        END;
        $$;
        DROP TRIGGER IF EXISTS hearthghost_validate_reminder_scope_trigger ON reminder_records;
        CREATE TRIGGER hearthghost_validate_reminder_scope_trigger
        BEFORE INSERT OR UPDATE OF todo_id, scope, scope_id ON reminder_records
        FOR EACH ROW EXECUTE FUNCTION hearthghost_validate_reminder_scope();

        CREATE OR REPLACE FUNCTION hearthghost_sync_todo_reminder()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.state <> 'open'
               OR NEW.due_at IS NULL
               OR NEW.due_at <= CURRENT_TIMESTAMP
               OR NEW.due_at > CURRENT_TIMESTAMP + INTERVAL '366 days' THEN
                UPDATE reminder_records
                SET state = 'cancelled', cancelled_at = CURRENT_TIMESTAMP
                WHERE todo_id = NEW.todo_id
                  AND scope = NEW.scope
                  AND scope_id = NEW.scope_id
                  AND state = 'scheduled';
            ELSE
                UPDATE reminder_records
                SET fire_at = NEW.due_at
                WHERE todo_id = NEW.todo_id
                  AND scope = NEW.scope
                  AND scope_id = NEW.scope_id
                  AND state = 'scheduled';
            END IF;
            RETURN NEW;
        END;
        $$;
        DROP TRIGGER IF EXISTS hearthghost_sync_todo_reminder_trigger ON todo_records;
        CREATE TRIGGER hearthghost_sync_todo_reminder_trigger
        AFTER UPDATE OF due_at, state ON todo_records
        FOR EACH ROW EXECUTE FUNCTION hearthghost_sync_todo_reminder();
        """,
    ),
    Migration(
        5,
        "behavior_preference_records_v1",
        """
        CREATE TABLE IF NOT EXISTS behavior_preference_records (
            scope TEXT NOT NULL CHECK (scope IN ('user', 'household')),
            scope_id TEXT NOT NULL,
            character_name TEXT NOT NULL CHECK (char_length(character_name) BETWEEN 1 AND 80),
            humor TEXT NOT NULL CHECK (humor IN ('low', 'moderate', 'high')),
            verbosity TEXT NOT NULL CHECK (verbosity IN ('concise', 'normal', 'detailed')),
            formality TEXT NOT NULL CHECK (formality IN ('casual', 'neutral', 'formal')),
            initiative TEXT NOT NULL CHECK (initiative IN ('low', 'moderate', 'high')),
            followup_timeout_sec INTEGER NOT NULL CHECK (followup_timeout_sec BETWEEN 5 AND 120),
            proactive_frequency TEXT NOT NULL CHECK (proactive_frequency IN ('off', 'low', 'moderate')),
            revision BIGINT NOT NULL CHECK (revision > 0),
            updated_at TIMESTAMPTZ NOT NULL,
            updated_by_node_id TEXT NOT NULL,
            PRIMARY KEY (scope, scope_id)
        );
        CREATE INDEX IF NOT EXISTS behavior_preference_updated_idx
        ON behavior_preference_records(updated_at DESC, scope, scope_id);
        """,
    ),
    Migration(
        6,
        "reminder_delivery_lease_v1",
        """
        ALTER TABLE reminder_records
            ADD COLUMN IF NOT EXISTS delivery_state TEXT NOT NULL DEFAULT 'pending',
            ADD COLUMN IF NOT EXISTS claim_token UUID NULL,
            ADD COLUMN IF NOT EXISTS claim_owner TEXT NULL,
            ADD COLUMN IF NOT EXISTS claim_until TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS last_delivery_reason TEXT NULL;

        UPDATE reminder_records
        SET next_attempt_at = fire_at
        WHERE state = 'scheduled'
          AND delivery_state = 'pending'
          AND next_attempt_at IS NULL;

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'reminder_delivery_state_check'
            ) THEN
                ALTER TABLE reminder_records
                ADD CONSTRAINT reminder_delivery_state_check CHECK (
                    delivery_state IN ('pending', 'claimed', 'delivered', 'exhausted')
                    AND attempt_count >= 0
                    AND (last_delivery_reason IS NULL OR char_length(last_delivery_reason) <= 128)
                    AND (
                        state = 'cancelled'
                        OR (
                            delivery_state = 'pending'
                            AND claim_token IS NULL
                            AND claim_owner IS NULL
                            AND claim_until IS NULL
                            AND delivered_at IS NULL
                            AND next_attempt_at IS NOT NULL
                        )
                        OR (
                            delivery_state = 'claimed'
                            AND claim_token IS NOT NULL
                            AND claim_owner IS NOT NULL
                            AND claim_until IS NOT NULL
                            AND delivered_at IS NULL
                        )
                        OR (
                            delivery_state = 'delivered'
                            AND claim_token IS NULL
                            AND claim_owner IS NULL
                            AND claim_until IS NULL
                            AND next_attempt_at IS NULL
                            AND delivered_at IS NOT NULL
                        )
                        OR (
                            delivery_state = 'exhausted'
                            AND claim_token IS NULL
                            AND claim_owner IS NULL
                            AND claim_until IS NULL
                            AND next_attempt_at IS NULL
                            AND delivered_at IS NULL
                        )
                    )
                );
            END IF;
        END;
        $$;

        CREATE INDEX IF NOT EXISTS reminder_delivery_pending_idx
        ON reminder_records(next_attempt_at, fire_at, reminder_id)
        WHERE state = 'scheduled' AND delivery_state = 'pending';
        CREATE INDEX IF NOT EXISTS reminder_delivery_claim_expiry_idx
        ON reminder_records(claim_until, reminder_id)
        WHERE state = 'scheduled' AND delivery_state = 'claimed';

        CREATE OR REPLACE FUNCTION hearthghost_sync_todo_reminder()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.state <> 'open'
               OR NEW.due_at IS NULL
               OR NEW.due_at <= CURRENT_TIMESTAMP
               OR NEW.due_at > CURRENT_TIMESTAMP + INTERVAL '366 days' THEN
                UPDATE reminder_records
                SET state = 'cancelled',
                    cancelled_at = CURRENT_TIMESTAMP,
                    claim_token = NULL,
                    claim_owner = NULL,
                    claim_until = NULL,
                    next_attempt_at = NULL,
                    delivery_state = CASE
                        WHEN delivery_state = 'delivered' THEN 'delivered'
                        ELSE 'exhausted'
                    END,
                    last_delivery_reason = CASE
                        WHEN delivery_state = 'delivered' THEN last_delivery_reason
                        ELSE 'todo_unschedulable'
                    END
                WHERE todo_id = NEW.todo_id
                  AND scope = NEW.scope
                  AND scope_id = NEW.scope_id
                  AND state = 'scheduled';
            ELSIF NEW.due_at IS DISTINCT FROM OLD.due_at THEN
                UPDATE reminder_records
                SET fire_at = NEW.due_at,
                    delivery_state = 'pending',
                    claim_token = NULL,
                    claim_owner = NULL,
                    claim_until = NULL,
                    attempt_count = 0,
                    next_attempt_at = NEW.due_at,
                    delivered_at = NULL,
                    last_attempt_at = NULL,
                    last_delivery_reason = NULL
                WHERE todo_id = NEW.todo_id
                  AND scope = NEW.scope
                  AND scope_id = NEW.scope_id
                  AND state = 'scheduled';
            END IF;
            RETURN NEW;
        END;
        $$;
        """,
    ),
    Migration(
        7,
        "behavior_preference_expression_style_v1",
        """
        ALTER TABLE behavior_preference_records
        ADD COLUMN IF NOT EXISTS expression_style TEXT NOT NULL DEFAULT 'balanced';

        UPDATE behavior_preference_records
        SET expression_style = 'playful'
        WHERE character_name = '영희' AND expression_style = 'balanced';

        UPDATE behavior_preference_records
        SET expression_style = 'reserved'
        WHERE character_name = '철수' AND expression_style = 'balanced';

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'behavior_preference_expression_style_check'
                  AND conrelid = 'behavior_preference_records'::regclass
            ) THEN
                ALTER TABLE behavior_preference_records
                ADD CONSTRAINT behavior_preference_expression_style_check CHECK (
                    expression_style IN (
                        'balanced', 'playful', 'reserved',
                        'tsundere', 'mesugaki', 'yandere'
                    )
                );
            END IF;
        END;
        $$;
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
