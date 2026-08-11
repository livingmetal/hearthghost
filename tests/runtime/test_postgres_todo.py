from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from apps.assistant.src.adapters.postgres_todo import PostgresTodoRepository
from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.todo import TodoRecord, TodoState


class FakeCursor:
    def __init__(self, rows=None, rowcount=1):
        self.rows = list(rows or [])
        self.rowcount = rowcount
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


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
    def __init__(self, cursors):
        self._cursors = list(cursors)
        self.calls = []

    def __call__(self, dsn, **kwargs):
        self.calls.append((dsn, kwargs))
        return FakeConnection(self._cursors.pop(0))


class PostgresTodoRepositoryTests(unittest.TestCase):
    def record(self):
        return TodoRecord(
            todo_id="11111111-1111-1111-1111-111111111111",
            scope=MemoryScope.USER,
            scope_id="owner",
            text="우유 사기",
            state=TodoState.OPEN,
            created_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
            due_at=datetime(2026, 8, 12, 9, tzinfo=timezone(timedelta(hours=9))),
        )

    def test_dsn_is_redacted_and_connect_timeout_is_bounded(self):
        connector = Connector([FakeCursor()])
        repository = PostgresTodoRepository("postgresql://u:secret@db/hearthghost", connect=connector)
        self.assertNotIn("secret", repr(repository))
        self.assertEqual(connector.calls[0][1]["connect_timeout"], 5)

    def test_put_uses_parameter_binding_and_persists_due_at(self):
        schema = FakeCursor()
        write = FakeCursor()
        connector = Connector([schema, write])
        repository = PostgresTodoRepository("postgresql://db/hearthghost", connect=connector)
        record = self.record()
        repository.put(record)

        sql, params = write.executed[0]
        self.assertIn("INSERT INTO todo_records", sql)
        self.assertIn("due_at", sql)
        self.assertNotIn(record.text, sql)
        self.assertIn(record.text, params)
        self.assertEqual(params[-1], record.due_at)
        self.assertEqual(len(params), 8)

    def test_list_scope_binds_scope_scope_id_and_limit_and_decodes_due_at(self):
        schema = FakeCursor()
        due_at = datetime(2026, 8, 12, tzinfo=timezone.utc)
        row = (
            "11111111-1111-1111-1111-111111111111",
            "user",
            "owner",
            "우유 사기",
            "open",
            datetime(2026, 8, 11, tzinfo=timezone.utc),
            None,
            due_at,
        )
        query = FakeCursor([row])
        connector = Connector([schema, query])
        repository = PostgresTodoRepository("postgresql://db/hearthghost", connect=connector)
        records = repository.list_scope("user", "owner", limit=10)

        sql, params = query.executed[0]
        self.assertIn("WHERE scope = %s AND scope_id = %s", sql)
        self.assertIn("due_at", sql)
        self.assertEqual(params, ("user", "owner", 10))
        self.assertEqual(records[0].scope, MemoryScope.USER)
        self.assertEqual(records[0].state, TodoState.OPEN)
        self.assertEqual(records[0].due_at, due_at)

    def test_replace_rechecks_scope_and_preserves_due_at(self):
        schema = FakeCursor()
        update = FakeCursor(rowcount=1)
        connector = Connector([schema, update])
        repository = PostgresTodoRepository("postgresql://db/hearthghost", connect=connector)
        record = self.record()
        completed = TodoRecord(
            todo_id=record.todo_id,
            scope=record.scope,
            scope_id=record.scope_id,
            text=record.text,
            state=TodoState.COMPLETED,
            created_at=record.created_at,
            completed_at=datetime(2026, 8, 11, 1, tzinfo=timezone.utc),
            due_at=record.due_at,
        )
        repository.replace(completed)

        sql, params = update.executed[0]
        self.assertIn("due_at = %s", sql)
        self.assertIn("WHERE todo_id = %s AND scope = %s AND scope_id = %s", sql)
        self.assertEqual(params[3], record.due_at)
        self.assertEqual(params[-2:], ("user", "owner"))

    def test_invalid_state_timestamp_pair_is_rejected_on_read(self):
        schema = FakeCursor()
        bad = FakeCursor([
            (
                "11111111-1111-1111-1111-111111111111",
                "user",
                "owner",
                "우유 사기",
                "completed",
                datetime(2026, 8, 11, tzinfo=timezone.utc),
                None,
                None,
            )
        ])
        connector = Connector([schema, bad])
        repository = PostgresTodoRepository("postgresql://db/hearthghost", connect=connector)
        with self.assertRaisesRegex(RuntimeError, "invalid record"):
            repository.get("11111111-1111-1111-1111-111111111111")

    def test_naive_due_at_is_rejected_on_read(self):
        schema = FakeCursor()
        bad = FakeCursor([
            (
                "11111111-1111-1111-1111-111111111111",
                "user",
                "owner",
                "우유 사기",
                "open",
                datetime(2026, 8, 11, tzinfo=timezone.utc),
                None,
                datetime(2026, 8, 12, 9),
            )
        ])
        connector = Connector([schema, bad])
        repository = PostgresTodoRepository("postgresql://db/hearthghost", connect=connector)
        with self.assertRaisesRegex(RuntimeError, "invalid record"):
            repository.get("11111111-1111-1111-1111-111111111111")


if __name__ == "__main__":
    unittest.main()
