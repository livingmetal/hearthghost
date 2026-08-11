from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from apps.assistant.src.adapters.in_memory_memory import InMemoryMemoryRepository
from apps.assistant.src.adapters.in_memory_reminder import InMemoryReminderRepository
from apps.assistant.src.adapters.in_memory_todo import InMemoryTodoRepository
from apps.assistant.src.modules.conversation_principal import (
    ConversationPrincipal,
    PrincipalAssurance,
    StaticConversationPrincipalResolver,
)
from apps.assistant.src.modules.memory import MemoryManager, MemoryScope
from apps.assistant.src.modules.productivity_command import ProductivityCommandService
from apps.assistant.src.modules.reminder import ReminderManager, ReminderState
from apps.assistant.src.modules.todo import TodoManager


NOW = datetime(2026, 8, 11, tzinfo=timezone.utc)


class Clock:
    def now(self):
        return NOW


class ProductivityReminderSyncTests(unittest.TestCase):
    def setUp(self):
        clock = Clock()
        principal = ConversationPrincipal(
            scope=MemoryScope.USER,
            scope_id="owner",
            assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
            source_node_id="android-personal-01",
        )
        principals = StaticConversationPrincipalResolver({"android-personal-01": principal})
        self.todos = TodoManager(repository=InMemoryTodoRepository(), clock=clock)
        self.reminders = ReminderManager(repository=InMemoryReminderRepository(), clock=clock)
        self.service = ProductivityCommandService(
            memory=MemoryManager(repository=InMemoryMemoryRepository(), clock=clock),
            todos=self.todos,
            principals=principals,
            reminders=self.reminders,
        )

    def command(self, text):
        return self.service.handle(
            node_id="android-personal-01",
            text=text,
            conversation_session_id="conversation-sync",
        )

    def make_scheduled(self):
        created = self.command("할 일 [2026-08-12T09:00+09:00]: DB 백업 확인").todo
        reminder = self.reminders.schedule_for_todo(
            created,
            created_by_node_id="android-personal-01",
            explicit_user_request=True,
        )
        return created, reminder

    def test_due_change_reschedules_active_reminder(self):
        todo, reminder = self.make_scheduled()
        result = self.command(f"할 일 기한: {todo.todo_id[:8]} [2026-08-13T10:30+09:00]")
        self.assertTrue(result.succeeded)
        active = [r for r in self.reminders.list_scope(MemoryScope.USER, "owner") if r.state is ReminderState.SCHEDULED]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].reminder_id, reminder.reminder_id)
        self.assertEqual(active[0].fire_at.isoformat(), "2026-08-13T10:30:00+09:00")

    def test_due_clear_and_completion_cancel_active_reminder(self):
        for command_template in (
            "할 일 기한 삭제: {ref}",
            "할 일 완료: {ref}",
        ):
            with self.subTest(command_template=command_template):
                self.setUp()
                todo, _ = self.make_scheduled()
                result = self.command(command_template.format(ref=todo.todo_id[:8]))
                self.assertTrue(result.succeeded)
                records = self.reminders.list_scope(MemoryScope.USER, "owner")
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0].state, ReminderState.CANCELLED)

    def test_delete_cancels_before_todo_removal(self):
        todo, _ = self.make_scheduled()
        result = self.command(f"할 일 삭제: {todo.todo_id[:8]}")
        self.assertTrue(result.succeeded)
        records = self.reminders.list_scope(MemoryScope.USER, "owner")
        self.assertEqual(records[0].state, ReminderState.CANCELLED)
        self.assertIsNone(self.todos.get(todo.todo_id, scope=MemoryScope.USER, scope_id="owner"))


if __name__ == "__main__":
    unittest.main()
