from datetime import datetime, timezone
import unittest

from apps.assistant.src.adapters.postgres_memory import PostgresMemoryRepository
from apps.assistant.src.modules.memory import MemoryKind, MemoryRecord, MemoryScope, MemorySource


class FakeCursor:
    def __init__(self, rows=None):
        self.calls = []
        self.rows = list(rows or [])
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


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
        self.cursors = list(cursors)
        self.calls = []

    def __call__(self, dsn, **kwargs):
        self.calls.append((dsn, kwargs))
        return FakeConnection(self.cursors.pop(0))


class PostgresMemoryTests(unittest.TestCase):
    def test_dsn_is_redacted_and_write_is_parameterized(self):
        schema = FakeCursor()
        write = FakeCursor()
        connect = Connector([schema, write])
        repository = PostgresMemoryRepository("postgresql://user:very-secret@db/hearthghost", connect=connect)
        record = MemoryRecord(
            memory_id="8d37ae38-1bf6-4b70-8985-e91349331072",
            scope=MemoryScope.USER,
            scope_id="owner",
            kind=MemoryKind.SEMANTIC,
            text="내가 명시적으로 기억시킨 문장",
            source=MemorySource.ADDRESSED_TEXT,
            source_conversation_session_id="conversation-1",
            created_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        )
        repository.put(record)
        self.assertNotIn("very-secret", repr(repository))
        query, params = write.calls[0]
        self.assertIn("VALUES (%s, %s, %s", query)
        self.assertNotIn(record.text, query)
        self.assertIn(record.text, params)
        self.assertEqual(connect.calls[0][1]["connect_timeout"], 5)

    def test_scope_query_binds_scope_and_identifier(self):
        schema = FakeCursor()
        rows = FakeCursor([])
        connect = Connector([schema, rows])
        repository = PostgresMemoryRepository("postgresql://db/hearthghost", connect=connect)
        self.assertEqual(repository.list_scope("user", "owner", limit=20), ())
        query, params = rows.calls[0]
        self.assertIn("WHERE scope = %s AND scope_id = %s", query)
        self.assertEqual(params, ("user", "owner", 20))


if __name__ == "__main__":
    unittest.main()
