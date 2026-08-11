from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from apps.assistant.src.adapters.conversation_protocol import (
    ConversationCommand,
    ConversationProtocol,
)
from apps.assistant.src.adapters.in_memory_conversation import InMemoryConversationRepository
from apps.assistant.src.adapters.in_memory_memory import InMemoryMemoryRepository
from apps.assistant.src.modules.conversation import AdmittedConversationNode, ConversationManager
from apps.assistant.src.modules.conversation_principal import (
    ConversationPrincipal,
    DenyingConversationPrincipalResolver,
    PrincipalAssurance,
    StaticConversationPrincipalResolver,
)
from apps.assistant.src.modules.explicit_memory import ExplicitMemoryParser
from apps.assistant.src.modules.memory import MemoryManager, MemoryScope
from apps.assistant.src.modules.memory_command import MemoryCommandService


class Clock:
    def now(self):
        return datetime(2026, 8, 11, tzinfo=timezone.utc)


class ExplodingOrchestrator:
    def respond(self, node, turn):
        raise AssertionError("LLM/orchestrator must not receive explicit memory commands")


class MemoryConversationProtocolTests(unittest.TestCase):
    def build(self, principals):
        clock = Clock()
        conversation = ConversationManager(
            repository=InMemoryConversationRepository(),
            clock=clock,
            follow_up_timeout=timedelta(seconds=30),
        )
        memory = MemoryManager(
            repository=InMemoryMemoryRepository(),
            clock=clock,
        )
        commands = MemoryCommandService(
            parser=ExplicitMemoryParser(),
            memory=memory,
            principals=principals,
        )
        protocol = ConversationProtocol(
            gateway=object(),
            conversation=conversation,
            orchestrator=ExplodingOrchestrator(),
            memory_commands=commands,
        )
        node = AdmittedConversationNode(
            admitted=True,
            node_id="android-personal-01",
            node_session_id="node-session-1",
            capability="conversation.text",
        )
        opened = protocol._dispatch(
            node,
            ConversationCommand(
                message_type="conversation.open",
                request_id=str(uuid4()),
                node_session_id="node-session-1",
                sequence=1,
            ),
        )
        self.assertTrue(opened.accepted)
        return protocol, node, opened.conversation_session_id, memory

    def test_explicit_memory_is_stored_locally_without_llm(self):
        principal = ConversationPrincipal(
            scope=MemoryScope.USER,
            scope_id="owner",
            assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
            source_node_id="android-personal-01",
        )
        protocol, node, conversation_id, memory = self.build(
            StaticConversationPrincipalResolver({"android-personal-01": principal})
        )

        result = protocol._dispatch(
            node,
            ConversationCommand(
                message_type="conversation.text",
                request_id=str(uuid4()),
                node_session_id="node-session-1",
                sequence=2,
                conversation_session_id=conversation_id,
                text="기억해: 나는 플랫화이트를 선호해",
            ),
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.reason_code, "memory_stored")
        self.assertEqual(result.response_text, "기억했어요.")
        records = memory.list_scope(MemoryScope.USER, "owner")
        self.assertEqual(len(records), 1)
        self.assertIn("플랫화이트", records[0].text)

    def test_unresolved_memory_scope_is_locally_rejected_without_llm(self):
        protocol, node, conversation_id, memory = self.build(
            DenyingConversationPrincipalResolver()
        )

        result = protocol._dispatch(
            node,
            ConversationCommand(
                message_type="conversation.text",
                request_id=str(uuid4()),
                node_session_id="node-session-1",
                sequence=2,
                conversation_session_id=conversation_id,
                text="기억해: 이 값은 저장되면 안 돼",
            ),
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.reason_code, "principal_unresolved")
        self.assertIn("저장하지 않았어요", result.response_text)
        self.assertEqual(memory.list_scope(MemoryScope.USER, "owner"), ())


if __name__ == "__main__":
    unittest.main()
