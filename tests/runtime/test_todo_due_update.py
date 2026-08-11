from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from apps.assistant.src.adapters.in_memory_memory import InMemoryMemoryRepository
from apps.assistant.src.adapters.in_memory_todo import InMemoryTodoRepository
from apps.assistant.src.modules.conversation_principal import (
    ConversationPrincipal,
    PrincipalAssurance,
    StaticConversationPrincipalResolver,
)
from apps.assistant.src.modules.memory import MemoryManager, MemoryScope
from apps.assistant.src.modules.productivity_command import ProductivityCommandService
from apps.assistant.src.modules.todo import TodoManager, TodoState


class Clock:
    def now(self):
        return datetime(2026, 8, 11, tzinfo=timezone.utc)


class TodoDueUpdateTests(unittest.TestCase):
    def setUp(self):
        clock = Clock()
        self.memory = MemoryManager(repository=InMemoryMemoryRepository(), clock=clock)
        self.todos = TodoManager(repository=InMemoryTodoRepository(), clock=clock)
        principal = ConversationPrincipal(
            scope=MemoryScope.USER,
            scope_id="owner",
            assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
            source_node_id="android-personal-01",
        )
        self.service = ProductivityCommandService(
            memory=self.memory,
            todos=self.todos,
            principals=StaticConversationPrincipalResolver({"android-personal-01": principal}),
        )

    def command(self, text: str):
        return self.service.handle(
            node_id="android-personal-01",
            text=text,
            conversation_session_id="conversation-due-update",
        )

    def test_set_and_clear_due_with_short_reference(self):
        created = self.command("할 일: DB 백업 확인").todo
        reference = created.todo_id[:8]

        updated = self.command(f"할 일 기한: {reference} [2026-08-13T10:30+09:00]")
        expected = datetime(2026, 8, 13, 10, 30, tzinfo=timezone(timedelta(hours=9)))
        self.assertTrue(updated.succeeded)
        self.assertEqual(updated.reason, "todo_due_set")
        self.assertEqual(updated.todo.due_at, expected)
        self.assertEqual(self.todos.list_scope(MemoryScope.USER, "owner")[0].due_at, expected)

        cleared = self.command(f"할 일 기한 삭제: {reference}")
        self.assertTrue(cleared.succeeded)
        self.assertEqual(cleared.reason, "todo_due_cleared")
        self.assertIsNone(cleared.todo.due_at)
        self.assertIsNone(self.todos.list_scope(MemoryScope.USER, "owner")[0].due_at)

    def test_due_update_without_timezone_fails_closed_and_preserves_existing_due(self):
        created = self.command("할 일 [2026-08-12T09:00+09:00]: 인증서 갱신").todo
        original = created.due_at
        result = self.command(f"할 일 기한: {created.todo_id[:8]} [2026-08-13T09:00]")
        self.assertTrue(result.recognized)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.reason, "todo_due_invalid")
        self.assertEqual(self.todos.list_scope(MemoryScope.USER, "owner")[0].due_at, original)

    def test_completed_todo_due_metadata_is_immutable(self):
        created = self.command("할 일: 인증서 갱신").todo
        reference = created.todo_id[:8]
        completed = self.command(f"할 일 완료: {reference}")
        self.assertTrue(completed.succeeded)
        self.assertEqual(completed.todo.state, TodoState.COMPLETED)

        result = self.command(f"할 일 기한: {reference} [2026-08-13T09:00+09:00]")
        self.assertFalse(result.succeeded)
        self.assertEqual(result.reason, "todo_not_found_in_scope")
        current = self.todos.list_scope(MemoryScope.USER, "owner")[0]
        self.assertEqual(current.state, TodoState.COMPLETED)
        self.assertIsNone(current.due_at)

    def test_due_update_cannot_cross_scope(self):
        created = self.command("할 일: 개인 작업").todo
        changed = self.todos.set_due(
            created.todo_id,
            scope=MemoryScope.HOUSEHOLD,
            scope_id="home",
            due_at=datetime(2026, 8, 13, tzinfo=timezone.utc),
        )
        self.assertIsNone(changed)
        self.assertIsNone(self.todos.list_scope(MemoryScope.USER, "owner")[0].due_at)


if __name__ == "__main__":
    unittest.main()
