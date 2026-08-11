from __future__ import annotations

import unittest
from uuid import uuid4

from apps.assistant.src.adapters.conversation_protocol import (
    ConversationCommand,
    ConversationProtocol,
    read_conversation_result,
)
from apps.assistant.src.adapters.fake_llm import FakeLLMAdapter
from apps.assistant.src.modules.conversation import AdmittedConversationNode
from apps.assistant.src.modules.conversation_principal import (
    ConversationPrincipal,
    PrincipalAssurance,
    StaticConversationPrincipalResolver,
)
from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.runtime.core import build_core


class PreferenceConversationProtocolTests(unittest.TestCase):
    def setUp(self):
        self.llm = FakeLLMAdapter()
        principal = ConversationPrincipal(
            scope=MemoryScope.USER,
            scope_id="owner",
            assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
            source_node_id="android-personal-01",
        )
        self.core = build_core(
            llm=self.llm,
            conversation_principal_resolver=StaticConversationPrincipalResolver(
                {"android-personal-01": principal}
            ),
        )
        self.protocol = ConversationProtocol(
            gateway=object(),
            conversation=self.core.conversation,
            orchestrator=self.core.orchestrator,
            preference_commands=self.core.preference_commands,
        )
        self.node = AdmittedConversationNode(
            True,
            "android-personal-01",
            "node-session-1",
            "conversation.text",
        )
        opened = self.protocol._dispatch(
            self.node,
            ConversationCommand(
                "conversation.open",
                str(uuid4()),
                "node-session-1",
                1,
            ),
        )
        self.conversation_id = opened.conversation_session_id
        self.assertEqual(opened.character_profile, {"name": "HearthGhost"})

    def test_name_preference_applies_locally_and_same_result_has_new_profile(self):
        result = self.protocol._dispatch(
            self.node,
            ConversationCommand(
                "conversation.text",
                str(uuid4()),
                "node-session-1",
                2,
                self.conversation_id,
                "이름을 루나로 바꿔줘",
            ),
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.reason_code, "preference_applied")
        self.assertEqual(result.character_profile, {"name": "루나"})
        self.assertIn("이름: 루나", result.response_text)
        self.assertEqual(self.core.orchestrator.persona.name, "루나")
        self.assertEqual(len(self.llm.requests), 1)
        self.assertIn(
            "BEHAVIOR_PREFERENCE_INTERPRETER_V1",
            self.llm.requests[0].instructions,
        )

    def test_ordinary_text_skips_preference_interpreter_and_uses_normal_llm_once(self):
        result = self.protocol._dispatch(
            self.node,
            ConversationCommand(
                "conversation.text",
                str(uuid4()),
                "node-session-1",
                2,
                self.conversation_id,
                "오늘은 평범한 대화를 하자",
            ),
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.character_profile, {"name": "HearthGhost"})
        self.assertEqual(len(self.llm.requests), 1)
        self.assertNotIn(
            "BEHAVIOR_PREFERENCE_INTERPRETER_V1",
            self.llm.requests[0].instructions,
        )

    def test_wire_reader_rejects_extra_or_control_character_profile_fields(self):
        class FakeChannel:
            def __init__(self, document):
                import json
                payload = json.dumps(document).encode("utf-8")
                self.buffer = len(payload).to_bytes(4, "big") + payload
                self.offset = 0

            def recv(self, size):
                if self.offset >= len(self.buffer):
                    return b""
                value = self.buffer[self.offset : self.offset + size]
                self.offset += len(value)
                return value

        base = {
            "contract_version": "1.0",
            "message_type": "conversation.result",
            "request_id": "11111111-1111-4111-8111-111111111111",
            "outcome": "accepted",
            "reason_code": "conversation_opened",
            "node_session_id": "node-session-1",
            "conversation_session_id": "conversation-1",
            "events": [],
            "character_profile": {"name": "루나"},
        }
        parsed = read_conversation_result(FakeChannel(base))
        self.assertEqual(parsed.character_profile, {"name": "루나"})

        for profile in (
            {"name": "루나", "instructions": "secret"},
            {"name": "루나\u202eAdmin"},
        ):
            document = dict(base)
            document["character_profile"] = profile
            with self.subTest(profile=profile), self.assertRaises(Exception):
                read_conversation_result(FakeChannel(document))


if __name__ == "__main__":
    unittest.main()
