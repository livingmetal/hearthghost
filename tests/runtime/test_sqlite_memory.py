from __future__ import annotations

import os
import sqlite3
import stat
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from apps.assistant.src.adapters.sqlite_memory import SqliteMemoryRepository
from apps.assistant.src.modules.memory import (
    MemoryKind,
    MemoryRecord,
    MemoryScope,
    MemorySource,
)


class SqliteMemoryTests(unittest.TestCase):
    def record(self, memory_id="11111111-1111-4111-8111-111111111111"):
        return MemoryRecord(
            memory_id=memory_id,
            scope=MemoryScope.USER,
            scope_id="owner",
            kind=MemoryKind.SEMANTIC,
            text="I prefer low-acidity coffee.",
            source=MemorySource.ADDRESSED_TEXT,
            source_conversation_session_id="conversation-1",
            created_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        )

    def test_database_persists_and_is_owner_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            path = root / "memory.sqlite3"
            first = SqliteMemoryRepository(path)
            record = self.record()
            first.put(record)

            second = SqliteMemoryRepository(path)
            self.assertEqual(second.get(record.memory_id), record)
            self.assertEqual(second.list_scope("user", "owner", limit=20), (record,))
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_cross_scope_query_returns_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            repository = SqliteMemoryRepository(root / "memory.sqlite3")
            repository.put(self.record())

            self.assertEqual(repository.list_scope("household", "home", limit=20), ())

    def test_existing_shared_parent_is_rejected_without_chmod(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o755)

            with self.assertRaisesRegex(ValueError, "owner-only"):
                SqliteMemoryRepository(root / "memory.sqlite3")

            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o755)

    def test_symlink_database_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            target = root / "target.sqlite3"
            target.touch(mode=0o600)
            link = root / "memory.sqlite3"
            link.symlink_to(target)

            with self.assertRaisesRegex(ValueError, "symlink"):
                SqliteMemoryRepository(link)

    def test_invalid_persisted_enum_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.chmod(root, 0o700)
            path = root / "memory.sqlite3"
            repository = SqliteMemoryRepository(path)
            record = self.record()
            repository.put(record)
            with sqlite3.connect(path) as connection:
                connection.execute(
                    "UPDATE memory_records SET source = ? WHERE memory_id = ?",
                    ("camera_snapshot", record.memory_id),
                )

            with self.assertRaisesRegex(RuntimeError, "invalid record"):
                repository.get(record.memory_id)


if __name__ == "__main__":
    unittest.main()
