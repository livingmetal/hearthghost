from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from apps.assistant.src.adapters.postgres_reminder import PostgresReminderRepository
from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.reminder import ReminderRecord, ReminderSource, ReminderState


NOW = datetime(2026, 8, 11, tzinfo=timezone.utc)


class FakeCursor:
    def __init__(self, rows=None, rowcount=1):
        self.rows = list(rows or [])
        self.rowcount = rowcount
        self.executed = []

    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False
    def execute(self, sql, params=None): self.executed.append((sql, params))
    def fetchone(self): return self.rows[0] if self.rows else None
    def fetchall(self): return list(self.rows)


class FakeConnection:
    def __init__(self, cursor): self._cursor = cursor
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False
    def cursor(self): return self._cursor


class Connector:
    def __init__(self, cursors):
        self._cursors = list(cursors)
        self.calls = []
    def __call__(self, dsn, **kwargs):
        self.calls.append((dsn, kwargs))
        return FakeConnection(self._cursors.pop(0))


class PostgresReminderRepositoryTests(unittest.TestCase):
    def record(self):
        return ReminderRecord(
            reminder_id="22222222-2222-2222-2222-222222222222",
            scope=MemoryScope.USER,
            scope_id="owner",
            todo_id="11111111-1111-1111-1111-111111111111",
            fire_at=NOW + timedelta(hours=2),
            source=ReminderSource.TODO_DUE,
            created_by_node_id="android-personal-01",
            created_at=NOW,
        )

    def row(self, *, state="scheduled", cancelled_at=None):
        record = self.record()
        return (
            record.reminder_id, "user", "owner", record.todo_id, record.fire_at,
            "todo_due", record.created_by_node_id, record.created_at, state, cancelled_at,
        )

    def test_dsn_is_redacted_and_connect_timeout_is_bounded(self):
        connector = Connector([FakeCursor()])
        repository = PostgresReminderRepository("postgresql://u:secret@db/hearthghost", connect=connector)
        self.assertNotIn("secret", repr(repository))
        self.assertEqual(connector.calls[0][1]["connect_timeout"], 5)

    def test_put_uses_parameter_binding_and_initializes_delivery_attempt_at_due_time(self):
        schema = FakeCursor()
        write = FakeCursor()
        connector = Connector([schema, write])
        repository = PostgresReminderRepository("postgresql://db/hearthghost", connect=connector)
        record = self.record()
        repository.put(record)
        sql, params = write.executed[0]
        self.assertIn("INSERT INTO reminder_records", sql)
        self.assertIn("delivery_state, next_attempt_at", sql)
        self.assertNotIn(record.created_by_node_id, sql)
        self.assertIn(record.created_by_node_id, params)
        self.assertEqual(len(params), 11)
        self.assertEqual(params[-1], record.fire_at)

    def test_find_active_binds_scope_scope_id_and_todo_id(self):
        schema = FakeCursor()
        query = FakeCursor([self.row()])
        connector = Connector([schema, query])
        repository = PostgresReminderRepository("postgresql://db/hearthghost", connect=connector)
        record = repository.find_active_for_todo("user", "owner", "11111111-1111-1111-1111-111111111111")
        sql, params = query.executed[0]
        self.assertIn("scope = %s AND scope_id = %s AND todo_id = %s", sql)
        self.assertIn("state = 'scheduled'", sql)
        self.assertIn("LIMIT 2", sql)
        self.assertEqual(params, ("user", "owner", "11111111-1111-1111-1111-111111111111"))
        self.assertEqual(record.scope, MemoryScope.USER)

    def test_replace_rechecks_scope_and_only_resets_delivery_on_scheduled_due_change(self):
        schema = FakeCursor()
        update = FakeCursor(rowcount=1)
        connector = Connector([schema, update])
        repository = PostgresReminderRepository("postgresql://db/hearthghost", connect=connector)
        record = self.record()
        moved = ReminderRecord(
            reminder_id=record.reminder_id,
            scope=record.scope,
            scope_id=record.scope_id,
            todo_id=record.todo_id,
            fire_at=record.fire_at + timedelta(hours=1),
            source=record.source,
            created_by_node_id=record.created_by_node_id,
            created_at=record.created_at,
        )
        repository.replace(moved)
        sql, params = update.executed[0]
        self.assertIn("delivery_state = CASE", sql)
        self.assertIn("attempt_count = CASE", sql)
        self.assertIn("WHERE reminder_id = %s AND scope = %s AND scope_id = %s", sql)
        self.assertEqual(params[-3], record.reminder_id)
        self.assertEqual(params[-2:], ("user", "owner"))

    def test_cancellation_does_not_deliberately_erase_delivery_audit_state(self):
        schema = FakeCursor()
        update = FakeCursor(rowcount=1)
        connector = Connector([schema, update])
        repository = PostgresReminderRepository("postgresql://db/hearthghost", connect=connector)
        record = self.record()
        cancelled = ReminderRecord(
            reminder_id=record.reminder_id,
            scope=record.scope,
            scope_id=record.scope_id,
            todo_id=record.todo_id,
            fire_at=record.fire_at,
            source=record.source,
            created_by_node_id=record.created_by_node_id,
            created_at=record.created_at,
            state=ReminderState.CANCELLED,
            cancelled_at=NOW + timedelta(minutes=1),
        )
        repository.replace(cancelled)
        sql, params = update.executed[0]
        self.assertIn("WHEN %s = 'scheduled'", sql)
        self.assertEqual(params[3], "cancelled")

    def test_invalid_state_timestamp_pair_is_rejected_on_read(self):
        connector = Connector([FakeCursor(), FakeCursor([self.row(state="cancelled", cancelled_at=None)])])
        repository = PostgresReminderRepository("postgresql://db/hearthghost", connect=connector)
        with self.assertRaisesRegex(RuntimeError, "invalid record"):
            repository.get("22222222-2222-2222-2222-222222222222")

    def test_multiple_active_rows_fail_closed(self):
        connector = Connector([FakeCursor(), FakeCursor([self.row(), self.row()])])
        repository = PostgresReminderRepository("postgresql://db/hearthghost", connect=connector)
        with self.assertRaisesRegex(RuntimeError, "multiple active"):
            repository.find_active_for_todo("user", "owner", "11111111-1111-1111-1111-111111111111")


if __name__ == "__main__":
    unittest.main()
