from __future__ import annotations

import unittest
from datetime import datetime, timezone

from apps.assistant.src.adapters.in_memory_memory import InMemoryMemoryRepository
from apps.assistant.src.adapters.in_memory_todo import InMemoryTodoRepository
from apps.assistant.src.modules.conversation_principal import (
    ConversationPrincipal,
    DenyingConversationPrincipalResolver,
    PrincipalAssurance,
    StaticConversationPrincipalResolver,
)
from apps.assistant.src.modules.memory import MemoryKind, MemoryManager, MemoryScope
from apps.assistant.src.modules.productivity_command import ProductivityCommandService
from apps.assistant.src.modules.todo import TodoManager, TodoState


class Clock:
    def now(self):
        return datetime(2026, 8, 11, tzinfo=timezone.utc)


class ProductivityCommandTests(unittest.TestCase):
    def build(self, principals):
        clock = Clock()
        memory = MemoryManager(repository=InMemoryMemoryRepository(), clock=clock)
        todos = TodoManager(repository=InMemoryTodoRepository(), clock=clock)
        service = ProductivityCommandService(memory=memory, todos=todos, principals=principals)
        return service, memory, todos

    def personal_principals(self):
        principal = ConversationPrincipal(
            scope=MemoryScope.USER,
            scope_id="owner",
            assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
            source_node_id="android-personal-01",
        )
        return StaticConversationPrincipalResolver({"android-personal-01": principal})

    def test_note_reuses_scoped_memory_note_kind(self):
        service, memory, _ = self.build(self.personal_principals())
        result = service.handle(
            node_id="android-personal-01",
            text="메모해: 서버실 UPS 배터리 점검",
            conversation_session_id="conversation-1",
        )
        self.assertTrue(result.succeeded)
        self.assertEqual(result.reason, "note_stored")
        records = memory.list_scope(MemoryScope.USER, "owner")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].kind, MemoryKind.NOTE)

    def test_todo_create_and_complete_with_short_ref_are_scope_bound(self):
        service, _, todos = self.build(self.personal_principals())
        created = service.handle(
            node_id="android-personal-01",
            text="할 일: 방화벽 점검 일정 확인",
            conversation_session_id="conversation-1",
        )
        self.assertTrue(created.succeeded)
        self.assertEqual(created.todo.state, TodoState.OPEN)
        self.assertIn(created.todo.todo_id[:8], created.response_text)

        listed = service.handle(
            node_id="android-personal-01",
            text="할 일 목록",
            conversation_session_id="conversation-1",
        )
        self.assertTrue(listed.succeeded)
        self.assertEqual(listed.reason, "todo_listed")
        self.assertIn(f"[{created.todo.todo_id[:8]}]", listed.response_text)
        self.assertNotIn(created.todo.todo_id, listed.response_text)

        completed = service.handle(
            node_id="android-personal-01",
            text=f"할 일 완료: {created.todo.todo_id[:8]}",
            conversation_session_id="conversation-1",
        )
        self.assertTrue(completed.succeeded)
        self.assertEqual(completed.todo.state, TodoState.COMPLETED)
        self.assertEqual(todos.list_scope(MemoryScope.USER, "owner")[0].state, TodoState.COMPLETED)

    def test_todo_delete_with_short_ref(self):
        service, _, todos = self.build(self.personal_principals())
        created = service.handle(
            node_id="android-personal-01",
            text="todo: rotate certificate",
            conversation_session_id="conversation-delete",
        ).todo
        deleted = service.handle(
            node_id="android-personal-01",
            text=f"할 일 삭제: {created.todo_id[:8]}",
            conversation_session_id="conversation-delete",
        )
        self.assertTrue(deleted.succeeded)
        self.assertEqual(deleted.reason, "todo_deleted")
        self.assertEqual(todos.list_scope(MemoryScope.USER, "owner"), ())

    def test_list_returns_only_open_todos(self):
        service, _, _ = self.build(self.personal_principals())
        first = service.handle(
            node_id="android-personal-01",
            text="할 일: 첫 번째",
            conversation_session_id="conversation-list",
        ).todo
        service.handle(
            node_id="android-personal-01",
            text="할 일: 두 번째",
            conversation_session_id="conversation-list",
        )
        service.handle(
            node_id="android-personal-01",
            text=f"할 일 완료: {first.todo_id}",
            conversation_session_id="conversation-list",
        )
        listed = service.handle(
            node_id="android-personal-01",
            text="todo list",
            conversation_session_id="conversation-list",
        )
        self.assertNotIn("첫 번째", listed.response_text)
        self.assertIn("두 번째", listed.response_text)

    def test_unbound_node_cannot_create_note_or_todo(self):
        service, memory, todos = self.build(DenyingConversationPrincipalResolver())
        for text in ("메모해: 비밀", "할 일: 비밀", "할 일 목록"):
            with self.subTest(text=text):
                result = service.handle(
                    node_id="unknown-node",
                    text=text,
                    conversation_session_id="conversation-2",
                )
                self.assertTrue(result.recognized)
                self.assertFalse(result.succeeded)
                self.assertEqual(result.reason, "principal_unresolved")
        self.assertEqual(memory.list_scope(MemoryScope.USER, "owner"), ())
        self.assertEqual(todos.list_scope(MemoryScope.USER, "owner"), ())

    def test_completion_cannot_cross_scope(self):
        service, _, todos = self.build(self.personal_principals())
        created = service.handle(
            node_id="android-personal-01",
            text="todo: rotate certificate",
            conversation_session_id="conversation-3",
        ).todo
        self.assertIsNone(todos.complete(created.todo_id, scope=MemoryScope.HOUSEHOLD, scope_id="home"))
        self.assertEqual(todos.list_scope(MemoryScope.USER, "owner")[0].state, TodoState.OPEN)

    def test_ordinary_text_is_not_intercepted(self):
        service, _, _ = self.build(self.personal_principals())
        result = service.handle(
            node_id="android-personal-01",
            text="오늘 할 일 뭐가 있지?",
            conversation_session_id="conversation-4",
        )
        self.assertFalse(result.recognized)


if __name__ == "__main__":
    unittest.main()
