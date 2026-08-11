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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return list(self.applied_rows)


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self._cursor


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
        self.assertEqual(version, MIGRATIONS[-1].version)
        self.assertEqual(connector.calls[0][1]["connect_timeout"], 5)
        first_sql, first_params = cursor.executed[0]
        self.assertIn("pg_advisory_xact_lock", first_sql)
        self.assertEqual(first_params, (MIGRATION_LOCK_KEY,))
        inserted = [params for sql, params in cursor.executed if "INSERT INTO hearthghost_schema_migrations" in sql]
        self.assertEqual(inserted, [(migration.version, migration.name) for migration in MIGRATIONS])

    def test_existing_v1_applies_v2_through_v4(self):
        cursor = FakeCursor([(1, "memory_records_v1")])
        version = ensure_postgres_schema("postgresql://db/hearthghost", connect=Connector(cursor))
        self.assertEqual(version, 4)
        inserted = [params for sql, params in cursor.executed if "INSERT INTO hearthghost_schema_migrations" in sql]
        self.assertEqual(
            inserted,
            [(2, "todo_records_v1"), (3, "todo_due_at_v1"), (4, "reminder_records_v1")],
        )

    def test_existing_v3_applies_only_v4(self):
        cursor = FakeCursor([
            (1, "memory_records_v1"),
            (2, "todo_records_v1"),
            (3, "todo_due_at_v1"),
        ])
        version = ensure_postgres_schema("postgresql://db/hearthghost", connect=Connector(cursor))
        self.assertEqual(version, 4)
        inserted = [params for sql, params in cursor.executed if "INSERT INTO hearthghost_schema_migrations" in sql]
        self.assertEqual(inserted, [(4, "reminder_records_v1")])
        migration_sql = next(sql for sql, _ in cursor.executed if "CREATE TABLE IF NOT EXISTS reminder_records" in sql)
        self.assertIn("TIMESTAMPTZ", migration_sql)
        self.assertIn("reminder_one_active_per_todo_idx", migration_sql)
        self.assertIn("WHERE state = 'scheduled'", migration_sql)

    def test_current_database_is_idempotent(self):
        cursor = FakeCursor([
            (1, "memory_records_v1"),
            (2, "todo_records_v1"),
            (3, "todo_due_at_v1"),
            (4, "reminder_records_v1"),
        ])
        version = ensure_postgres_schema("postgresql://db/hearthghost", connect=Connector(cursor))
        self.assertEqual(version, 4)
        self.assertFalse(any("INSERT INTO hearthghost_schema_migrations" in sql for sql, _ in cursor.executed))

    def test_future_database_version_fails_closed(self):
        cursor = FakeCursor([
            (1, "memory_records_v1"),
            (2, "todo_records_v1"),
            (3, "todo_due_at_v1"),
            (4, "reminder_records_v1"),
            (5, "future_build"),
        ])
        with self.assertRaisesRegex(PostgresSchemaError, "newer"):
            ensure_postgres_schema("postgresql://db/hearthghost", connect=Connector(cursor))

    def test_known_version_name_mismatch_fails_closed(self):
        cursor = FakeCursor([(1, "different_migration")])
        with self.assertRaisesRegex(PostgresSchemaError, "name"):
            ensure_postgres_schema("postgresql://db/hearthghost", connect=Connector(cursor))

    def test_migration_history_gap_fails_closed(self):
        cursor = FakeCursor([(1, "memory_records_v1"), (3, "todo_due_at_v1")])
        with self.assertRaisesRegex(PostgresSchemaError, "gaps"):
            ensure_postgres_schema("postgresql://db/hearthghost", connect=Connector(cursor))

    def test_invalid_dsn_is_rejected_before_connector(self):
        connector = Connector(FakeCursor())
        for dsn in ("", "   ", "postgresql://db/hearthghost\x00evil"):
            with self.subTest(dsn=dsn), self.assertRaises(ValueError):
                ensure_postgres_schema(dsn, connect=connector)
        self.assertEqual(connector.calls, [])


if __name__ == "__main__":
    unittest.main()
