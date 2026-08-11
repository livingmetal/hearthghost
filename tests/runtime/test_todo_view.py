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


class TodoViewTests(unittest.TestCase):
    def setUp(self):
        clock = Clock()
        self.todos = TodoManager(repository=InMemoryTodoRepository(), clock=clock)
        memory = MemoryManager(repository=InMemoryMemoryRepository(), clock=clock)
        principal = ConversationPrincipal(
            scope=MemoryScope.USER,
            scope_id="owner",
            assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
            source_node_id="android-personal-01",
        )
        self.service = ProductivityCommandService(
            memory=memory,
            todos=self.todos,
            principals=StaticConversationPrincipalResolver({"android-personal-01": principal}),
        )

    def command(self, text: str):
        return self.service.handle(
            node_id="android-personal-01",
            text=text,
            conversation_session_id="conversation-view",
        )

    def test_view_open_todo_with_due_timestamp(self):
        created = self.command("할 일 [2026-08-12T09:00+09:00]: DB 백업 확인").todo
        viewed = self.command(f"할 일 보기: {created.todo_id[:8]}")
        self.assertTrue(viewed.succeeded)
        self.assertEqual(viewed.reason, "todo_viewed")
        self.assertIn("DB 백업 확인", viewed.response_text)
        self.assertIn("상태: open", viewed.response_text)
        self.assertIn("2026-08-12T09:00:00+09:00", viewed.response_text)
        self.assertNotIn(created.todo_id, viewed.response_text)

    def test_view_completed_todo_includes_completion_time(self):
        created = self.command("할 일: 인증서 갱신").todo
        self.command(f"할 일 완료: {created.todo_id[:8]}")
        viewed = self.command(f"todo view: {created.todo_id[:8]}")
        self.assertTrue(viewed.succeeded)
        self.assertEqual(viewed.todo.state, TodoState.COMPLETED)
        self.assertIn("상태: completed", viewed.response_text)
        self.assertIn("완료: 2026-08-11T00:00:00+00:00", viewed.response_text)

    def test_domain_get_cannot_cross_scope(self):
        created = self.command("할 일: 개인 작업").todo
        hidden = self.todos.get(
            created.todo_id,
            scope=MemoryScope.HOUSEHOLD,
            scope_id="home",
        )
        self.assertIsNone(hidden)

    def test_unknown_reference_is_not_found(self):
        result = self.command("할 일 보기: deadbeef")
        self.assertFalse(result.succeeded)
        self.assertEqual(result.reason, "todo_not_found_in_scope")


if __name__ == "__main__":
    unittest.main()
