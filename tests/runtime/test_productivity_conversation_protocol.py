from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from apps.assistant.src.adapters.conversation_protocol import ConversationCommand, ConversationProtocol
from apps.assistant.src.adapters.in_memory_conversation import InMemoryConversationRepository
from apps.assistant.src.adapters.in_memory_memory import InMemoryMemoryRepository
from apps.assistant.src.adapters.in_memory_todo import InMemoryTodoRepository
from apps.assistant.src.modules.conversation import AdmittedConversationNode, ConversationManager
from apps.assistant.src.modules.conversation_principal import (
    ConversationPrincipal,
    PrincipalAssurance,
    StaticConversationPrincipalResolver,
)
from apps.assistant.src.modules.memory import MemoryManager, MemoryScope
from apps.assistant.src.modules.productivity_command import ProductivityCommandService
from apps.assistant.src.modules.todo import TodoManager


class Clock:
    def now(self):
        return datetime(2026, 8, 11, tzinfo=timezone.utc)


class ExplodingOrchestrator:
    def respond(self, node, turn):
        raise AssertionError("local productivity command reached the LLM")


class ProductivityConversationProtocolTests(unittest.TestCase):
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
        self.memory = MemoryManager(repository=InMemoryMemoryRepository(), clock=clock)
        self.todos = TodoManager(repository=InMemoryTodoRepository(), clock=clock)
        productivity = ProductivityCommandService(
            memory=self.memory,
            todos=self.todos,
            principals=principals,
        )
        self.protocol = ConversationProtocol(
            gateway=object(),
            conversation=self.conversation,
            orchestrator=ExplodingOrchestrator(),
            productivity_commands=productivity,
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

    def test_note_is_local(self):
        result = self.command("메모해: 다음 점검 때 UPS 배터리 확인", 2)
        self.assertTrue(result.accepted)
        self.assertEqual(result.reason_code, "note_stored")
        self.assertTrue(result.response_text.startswith("메모했어요. ["))
        self.assertEqual(len(self.memory.list_scope(MemoryScope.USER, "owner")), 1)

    def test_todo_create_and_complete_are_local(self):
        created = self.command("할 일: 인증서 갱신", 2)
        self.assertTrue(created.accepted)
        self.assertEqual(created.reason_code, "todo_created")
        todo = self.todos.list_scope(MemoryScope.USER, "owner")[0]
        self.assertIn(todo.todo_id[:8], created.response_text)

        completed = self.command(f"할 일 완료: {todo.todo_id[:8]}", 3)
        self.assertTrue(completed.accepted)
        self.assertEqual(completed.reason_code, "todo_completed")

    def test_due_todo_and_invalid_due_are_both_local(self):
        created = self.command("할 일 [2026-08-12T09:00+09:00]: DB 백업 확인", 2)
        self.assertTrue(created.accepted)
        self.assertEqual(created.reason_code, "todo_created")
        self.assertIn("2026-08-12T09:00:00+09:00", created.response_text)

        invalid = self.command("할 일 [2026-08-13T09:00]: DB 백업 재확인", 3)
        self.assertTrue(invalid.accepted)
        self.assertEqual(invalid.reason_code, "todo_due_invalid")
        self.assertIn("+09:00", invalid.response_text)
        self.assertEqual(len(self.todos.list_scope(MemoryScope.USER, "owner")), 1)


if __name__ == "__main__":
    unittest.main()
