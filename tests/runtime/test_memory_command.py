from __future__ import annotations

import unittest
from datetime import datetime, timezone

from apps.assistant.src.adapters.in_memory_memory import InMemoryMemoryRepository
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


class ExplodingPrincipalResolver:
    def resolve(self, node_id):
        raise RuntimeError("resolver unavailable")


class MemoryCommandTests(unittest.TestCase):
    def service(self, principals):
        repository = InMemoryMemoryRepository()
        memory = MemoryManager(repository=repository, clock=Clock())
        return MemoryCommandService(
            parser=ExplicitMemoryParser(),
            memory=memory,
            principals=principals,
        ), memory

    def test_non_memory_text_is_not_intercepted(self):
        service, memory = self.service(DenyingConversationPrincipalResolver())

        result = service.handle(
            node_id="android-personal-01",
            text="오늘 날씨 어때?",
            conversation_session_id="conversation-1",
        )

        self.assertFalse(result.recognized)
        self.assertFalse(result.stored)
        self.assertEqual(memory.list_scope(MemoryScope.USER, "owner"), ())

    def test_explicit_request_fails_closed_without_principal_binding(self):
        service, _ = self.service(DenyingConversationPrincipalResolver())

        result = service.handle(
            node_id="android-personal-01",
            text="기억해: 나는 아메리카노보다 플랫화이트를 선호해",
            conversation_session_id="conversation-1",
        )

        self.assertTrue(result.recognized)
        self.assertFalse(result.stored)
        self.assertEqual(result.reason, "principal_unresolved")

    def test_personal_node_binding_stores_only_in_authorized_user_scope(self):
        principal = ConversationPrincipal(
            scope=MemoryScope.USER,
            scope_id="owner",
            assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
            source_node_id="android-personal-01",
        )
        service, memory = self.service(
            StaticConversationPrincipalResolver({"android-personal-01": principal})
        )

        result = service.handle(
            node_id="android-personal-01",
            text="기억해: 나는 아메리카노보다 플랫화이트를 선호해",
            conversation_session_id="conversation-1",
        )

        self.assertTrue(result.recognized)
        self.assertTrue(result.stored)
        self.assertEqual(result.reason, "memory_stored")
        records = memory.list_scope(MemoryScope.USER, "owner")
        self.assertEqual(len(records), 1)
        self.assertIn("플랫화이트", records[0].text)
        self.assertEqual(memory.list_scope(MemoryScope.HOUSEHOLD, "home"), ())

    def test_household_binding_never_writes_user_scope(self):
        principal = ConversationPrincipal(
            scope=MemoryScope.HOUSEHOLD,
            scope_id="home",
            assurance=PrincipalAssurance.HOUSEHOLD_NODE_BINDING,
            source_node_id="shared-kitchen-display",
        )
        service, memory = self.service(
            StaticConversationPrincipalResolver({"shared-kitchen-display": principal})
        )

        result = service.handle(
            node_id="shared-kitchen-display",
            text="우유는 금요일에 사야 해, 기억해줘",
            conversation_session_id="conversation-2",
        )

        self.assertTrue(result.stored)
        self.assertEqual(len(memory.list_scope(MemoryScope.HOUSEHOLD, "home")), 1)
        self.assertEqual(memory.list_scope(MemoryScope.USER, "owner"), ())

    def test_resolver_failure_does_not_fall_back_to_node_id_scope(self):
        service, _ = self.service(ExplodingPrincipalResolver())

        result = service.handle(
            node_id="owner",
            text="기억해: 민감한 값",
            conversation_session_id="conversation-3",
        )

        self.assertTrue(result.recognized)
        self.assertFalse(result.stored)
        self.assertEqual(result.reason, "principal_resolution_failed")


if __name__ == "__main__":
    unittest.main()
