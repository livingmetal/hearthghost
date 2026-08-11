from __future__ import annotations

import os
import stat
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from apps.assistant.src.adapters.sqlite_todo import SqliteTodoRepository
from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.todo import TodoManager, TodoState


class Clock:
    def __init__(self):
        self.current = datetime(2026, 8, 11, tzinfo=timezone.utc)

    def now(self):
        return self.current


class SqliteTodoTests(unittest.TestCase):
    def test_persists_create_and_completion_across_repository_reopen(self):
        with TemporaryDirectory() as root:
            parent = Path(root) / "private"
            parent.mkdir(mode=0o700)
            path = parent / "personal.sqlite3"
            clock = Clock()
            manager = TodoManager(repository=SqliteTodoRepository(path), clock=clock)
            created = manager.create(
                scope=MemoryScope.USER,
                scope_id="owner",
                text="rotate test certificate",
            )
            clock.current += timedelta(minutes=1)
            manager.complete(
                created.todo_id,
                scope=MemoryScope.USER,
                scope_id="owner",
            )

            reopened = TodoManager(repository=SqliteTodoRepository(path), clock=clock)
            records = reopened.list_scope(MemoryScope.USER, "owner")

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].todo_id, created.todo_id)
            self.assertEqual(records[0].state, TodoState.COMPLETED)
            self.assertIsNotNone(records[0].completed_at)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_scope_query_does_not_return_other_scope(self):
        with TemporaryDirectory() as root:
            parent = Path(root) / "private"
            parent.mkdir(mode=0o700)
            manager = TodoManager(
                repository=SqliteTodoRepository(parent / "personal.sqlite3"),
                clock=Clock(),
            )
            manager.create(scope=MemoryScope.USER, scope_id="owner", text="personal")
            manager.create(scope=MemoryScope.HOUSEHOLD, scope_id="home", text="shared")

            self.assertEqual(
                [item.text for item in manager.list_scope(MemoryScope.USER, "owner")],
                ["personal"],
            )
            self.assertEqual(
                [item.text for item in manager.list_scope(MemoryScope.HOUSEHOLD, "home")],
                ["shared"],
            )

    def test_rejects_world_accessible_parent_and_symlink_path(self):
        with TemporaryDirectory() as root:
            open_parent = Path(root) / "open"
            open_parent.mkdir(mode=0o755)
            os.chmod(open_parent, 0o755)
            with self.assertRaisesRegex(ValueError, "owner-only"):
                SqliteTodoRepository(open_parent / "todos.sqlite3")

            private = Path(root) / "private"
            private.mkdir(mode=0o700)
            target = private / "target.sqlite3"
            target.touch(mode=0o600)
            link = private / "link.sqlite3"
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                SqliteTodoRepository(link)


if __name__ == "__main__":
    unittest.main()
