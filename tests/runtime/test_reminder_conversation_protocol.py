from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from apps.assistant.src.adapters.conversation_protocol import ConversationCommand, ConversationProtocol
from apps.assistant.src.adapters.in_memory_conversation import InMemoryConversationRepository
from apps.assistant.src.adapters.in_memory_reminder import InMemoryReminderRepository
from apps.assistant.src.adapters.in_memory_todo import InMemoryTodoRepository
from apps.assistant.src.modules.conversation import AdmittedConversationNode, ConversationManager
from apps.assistant.src.modules.conversation_principal import (
    ConversationPrincipal,
    PrincipalAssurance,
    StaticConversationPrincipalResolver,
)
from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.reminder import ReminderManager
from apps.assistant.src.modules.reminder_command import ReminderCommandService
from apps.assistant.src.modules.todo import TodoManager


NOW = datetime(2026, 8, 11, tzinfo=timezone.utc)


class Clock:
    def now(self):
        return NOW


class ExplodingOrchestrator:
    def respond(self, node, turn):
        raise AssertionError("local reminder command reached the LLM")


class ReminderConversationProtocolTests(unittest.TestCase):
    def setUp(self):
        clock = Clock()
        self.conversation = ConversationManager(
            repository=InMemoryConversationRepository(),
            clock=clock,
            follow_up_timeout=timedelta(seconds=30),
        )
        principal = ConversationPrincipal(
            scope=MemoryScope.USER,
            scope_id="owner",
            assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
            source_node_id="android-personal-01",
        )
        principals = StaticConversationPrincipalResolver({"android-personal-01": principal})
        self.todos = TodoManager(repository=InMemoryTodoRepository(), clock=clock)
        self.reminders = ReminderManager(repository=InMemoryReminderRepository(), clock=clock)
        reminder_commands = ReminderCommandService(
            reminders=self.reminders,
            todos=self.todos,
            principals=principals,
        )
        self.protocol = ConversationProtocol(
            gateway=object(),
            conversation=self.conversation,
            orchestrator=ExplodingOrchestrator(),
            reminder_commands=reminder_commands,
        )
        self.node = AdmittedConversationNode(
            True,
            "android-personal-01",
            "node-session-1",
            "conversation.text",
        )
        opened = self.protocol._dispatch(
            self.node,
            ConversationCommand("conversation.open", str(uuid4()), "node-session-1", 1),
        )
        self.conversation_id = opened.conversation_session_id
        self.todo = self.todos.create(
            scope=MemoryScope.USER,
            scope_id="owner",
            text="DB 백업 확인",
            due_at=NOW + timedelta(hours=2),
        )

    def command(self, text, sequence):
        return self.protocol._dispatch(
            self.node,
            ConversationCommand(
                "conversation.text",
                str(uuid4()),
                "node-session-1",
                sequence,
                self.conversation_id,
                text,
            ),
        )

    def test_schedule_and_list_are_completed_locally(self):
        scheduled = self.command(f"할 일 알림: {self.todo.todo_id[:8]}", 2)
        self.assertTrue(scheduled.accepted)
        self.assertEqual(scheduled.reason_code, "reminder_scheduled")
        self.assertIn("별도 권한", scheduled.response_text)
        listed = self.command("알림 목록", 3)
        self.assertTrue(listed.accepted)
        self.assertEqual(listed.reason_code, "reminder_listed")
        self.assertIn(self.todo.todo_id[:8], listed.response_text)

    def test_invalid_schedule_is_denied_locally_without_llm(self):
        no_due = self.todos.create(scope=MemoryScope.USER, scope_id="owner", text="기한 없음")
        result = self.command(f"할 일 알림: {no_due.todo_id[:8]}", 2)
        self.assertTrue(result.accepted)
        self.assertEqual(result.reason_code, "reminder_rejected")
        self.assertIn("기한", result.response_text)


if __name__ == "__main__":
    unittest.main()
