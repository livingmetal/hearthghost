from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from apps.assistant.src.adapters.in_memory_reminder import InMemoryReminderRepository
from apps.assistant.src.adapters.in_memory_todo import InMemoryTodoRepository
from apps.assistant.src.modules.conversation_principal import (
    ConversationPrincipal,
    DenyingConversationPrincipalResolver,
    PrincipalAssurance,
    StaticConversationPrincipalResolver,
)
from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.reminder import ReminderManager, ReminderState
from apps.assistant.src.modules.reminder_command import ReminderCommandService
from apps.assistant.src.modules.todo import TodoManager


NOW = datetime(2026, 8, 11, tzinfo=timezone.utc)


class Clock:
    def now(self):
        return NOW


class ReminderCommandTests(unittest.TestCase):
    def build(self, principals=None):
        clock = Clock()
        todos = TodoManager(repository=InMemoryTodoRepository(), clock=clock)
        reminders = ReminderManager(repository=InMemoryReminderRepository(), clock=clock)
        if principals is None:
            principal = ConversationPrincipal(
                scope=MemoryScope.USER,
                scope_id="owner",
                assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
                source_node_id="android-personal-01",
            )
            principals = StaticConversationPrincipalResolver({"android-personal-01": principal})
        service = ReminderCommandService(reminders=reminders, todos=todos, principals=principals)
        return service, todos, reminders

    def create_due_todo(self, todos):
        return todos.create(
            scope=MemoryScope.USER,
            scope_id="owner",
            text="DB 백업 확인",
            due_at=NOW + timedelta(hours=2),
        )

    def test_schedule_list_and_cancel_are_explicit_and_short_ref_friendly(self):
        service, todos, reminders = self.build()
        todo = self.create_due_todo(todos)
        scheduled = service.handle(node_id="android-personal-01", text=f"할 일 알림: {todo.todo_id[:8]}")
        self.assertTrue(scheduled.succeeded)
        self.assertEqual(scheduled.reason, "reminder_scheduled")
        self.assertIn("기기 전달은 별도 권한", scheduled.response_text)
        reminder = reminders.list_scope(MemoryScope.USER, "owner")[0]
        self.assertEqual(reminder.todo_id, todo.todo_id)

        listed = service.handle(node_id="android-personal-01", text="알림 목록")
        self.assertTrue(listed.succeeded)
        self.assertEqual(listed.reason, "reminder_listed")
        self.assertIn(reminder.reminder_id[:8], listed.response_text)
        self.assertNotIn(reminder.reminder_id, listed.response_text)

        cancelled = service.handle(node_id="android-personal-01", text=f"할 일 알림 취소: {todo.todo_id[:8]}")
        self.assertTrue(cancelled.succeeded)
        self.assertEqual(cancelled.reason, "reminder_cancelled")
        self.assertEqual(reminders.list_scope(MemoryScope.USER, "owner")[0].state, ReminderState.CANCELLED)

    def test_todo_without_valid_future_due_is_rejected(self):
        service, todos, reminders = self.build()
        todo = todos.create(scope=MemoryScope.USER, scope_id="owner", text="기한 없음")
        result = service.handle(node_id="android-personal-01", text=f"할 일 알림: {todo.todo_id[:8]}")
        self.assertTrue(result.recognized)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.reason, "reminder_rejected")
        self.assertEqual(reminders.list_scope(MemoryScope.USER, "owner"), ())

    def test_unbound_node_cannot_schedule_or_list(self):
        service, todos, reminders = self.build(DenyingConversationPrincipalResolver())
        todo = todos.create(
            scope=MemoryScope.USER,
            scope_id="owner",
            text="비밀",
            due_at=NOW + timedelta(hours=2),
        )
        for text in (f"할 일 알림: {todo.todo_id[:8]}", "알림 목록"):
            with self.subTest(text=text):
                result = service.handle(node_id="unknown-node", text=text)
                self.assertTrue(result.recognized)
                self.assertFalse(result.succeeded)
                self.assertEqual(result.reason, "principal_unresolved")
        self.assertEqual(reminders.list_scope(MemoryScope.USER, "owner"), ())

    def test_ordinary_reminder_wording_is_not_intercepted(self):
        service, _, _ = self.build()
        result = service.handle(node_id="android-personal-01", text="내일 알림 좀 해줘")
        self.assertFalse(result.recognized)


if __name__ == "__main__":
    unittest.main()
