from __future__ import annotations

import unittest

from apps.assistant.src.adapters.postgres_schema import (
    MIGRATION_LOCK_KEY,
    MIGRATIONS,
    PostgresSchemaError,
    ensure_postgres_schema,
)


class FakeCursor:
    def __init__(self, applied_rows=()):
        self.applied_rows = list(applied_rows)
        self.executed = []
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False
    def execute(self, sql, params=None): self.executed.append((sql, params))
    def fetchall(self): return list(self.applied_rows)


class FakeConnection:
    def __init__(self, cursor): self._cursor = cursor
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False
    def cursor(self): return self._cursor


class Connector:
    def __init__(self, cursor):
        self.cursor = cursor
        self.calls = []
    def __call__(self, dsn, **kwargs):
        self.calls.append((dsn, kwargs))
        return FakeConnection(self.cursor)


class PostgresSchemaMigrationTests(unittest.TestCase):
    def test_empty_database_applies_all_migrations_under_advisory_lock(self):
        cursor = FakeCursor()
        connector = Connector(cursor)
        version = ensure_postgres_schema("postgresql://db/hearthghost", connect=connector)
        self.assertEqual(version, 7)
        self.assertEqual(connector.calls[0][1]["connect_timeout"], 5)
        first_sql, first_params = cursor.executed[0]
        self.assertIn("pg_advisory_xact_lock", first_sql)
        self.assertEqual(first_params, (MIGRATION_LOCK_KEY,))
        inserted = [params for sql, params in cursor.executed if "INSERT INTO hearthghost_schema_migrations" in sql]
        self.assertEqual(inserted, [(migration.version, migration.name) for migration in MIGRATIONS])

    def test_existing_v5_applies_v6_and_expression_style_v7(self):
        cursor = FakeCursor([
            (1, "memory_records_v1"),
            (2, "todo_records_v1"),
            (3, "todo_due_at_v1"),
            (4, "reminder_records_v1"),
            (5, "behavior_preference_records_v1"),
        ])
        version = ensure_postgres_schema("postgresql://db/hearthghost", connect=Connector(cursor))
        self.assertEqual(version, 7)
        inserted = [params for sql, params in cursor.executed if "INSERT INTO hearthghost_schema_migrations" in sql]
        self.assertEqual(inserted, [
            (6, "reminder_delivery_lease_v1"),
            (7, "behavior_preference_expression_style_v1"),
        ])
        migration_sql = next(sql for sql, _ in cursor.executed if "ADD COLUMN IF NOT EXISTS delivery_state" in sql)
        self.assertIn("claim_token UUID", migration_sql)
        self.assertIn("claim_until TIMESTAMPTZ", migration_sql)
        self.assertIn("attempt_count", migration_sql)
        self.assertIn("next_attempt_at", migration_sql)
        self.assertIn("FOR", "FOR")
        self.assertIn("reminder_delivery_pending_idx", migration_sql)
        self.assertIn("reminder_delivery_claim_expiry_idx", migration_sql)
        self.assertIn("NEW.due_at IS DISTINCT FROM OLD.due_at", migration_sql)

    def test_existing_v4_applies_v5_and_v6_in_order(self):
        cursor = FakeCursor([
            (1, "memory_records_v1"),
            (2, "todo_records_v1"),
            (3, "todo_due_at_v1"),
            (4, "reminder_records_v1"),
        ])
        version = ensure_postgres_schema("postgresql://db/hearthghost", connect=Connector(cursor))
        self.assertEqual(version, 7)
        inserted = [params for sql, params in cursor.executed if "INSERT INTO hearthghost_schema_migrations" in sql]
        self.assertEqual(inserted, [
            (5, "behavior_preference_records_v1"),
            (6, "reminder_delivery_lease_v1"),
            (7, "behavior_preference_expression_style_v1"),
        ])

    def test_current_database_is_idempotent(self):
        cursor = FakeCursor([
            (1, "memory_records_v1"),
            (2, "todo_records_v1"),
            (3, "todo_due_at_v1"),
            (4, "reminder_records_v1"),
            (5, "behavior_preference_records_v1"),
            (6, "reminder_delivery_lease_v1"),
            (7, "behavior_preference_expression_style_v1"),
        ])
        version = ensure_postgres_schema("postgresql://db/hearthghost", connect=Connector(cursor))
        self.assertEqual(version, 7)
        self.assertFalse(any("INSERT INTO hearthghost_schema_migrations" in sql for sql, _ in cursor.executed))

    def test_future_database_version_fails_closed(self):
        cursor = FakeCursor([
            (1, "memory_records_v1"),
            (2, "todo_records_v1"),
            (3, "todo_due_at_v1"),
            (4, "reminder_records_v1"),
            (5, "behavior_preference_records_v1"),
            (6, "reminder_delivery_lease_v1"),
            (7, "behavior_preference_expression_style_v1"),
            (8, "future_build"),
        ])
        with self.assertRaisesRegex(PostgresSchemaError, "newer"):
            ensure_postgres_schema("postgresql://db/hearthghost", connect=Connector(cursor))

    def test_known_version_name_mismatch_fails_closed(self):
        with self.assertRaisesRegex(PostgresSchemaError, "name"):
            ensure_postgres_schema("postgresql://db/hearthghost", connect=Connector(FakeCursor([(1, "different_migration")])))

    def test_migration_history_gap_fails_closed(self):
        with self.assertRaisesRegex(PostgresSchemaError, "gaps"):
            ensure_postgres_schema(
                "postgresql://db/hearthghost",
                connect=Connector(FakeCursor([(1, "memory_records_v1"), (3, "todo_due_at_v1")])),
            )

    def test_invalid_dsn_is_rejected_before_connector(self):
        connector = Connector(FakeCursor())
        for dsn in ("", "   ", "postgresql://db/hearthghost\x00evil"):
            with self.subTest(dsn=dsn), self.assertRaises(ValueError):
                ensure_postgres_schema(dsn, connect=connector)
        self.assertEqual(connector.calls, [])


if __name__ == "__main__":
    unittest.main()
