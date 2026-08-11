from __future__ import annotations

import unittest
from uuid import uuid4

from apps.assistant.src.adapters.conversation_protocol import (
    ConversationCommand,
    ConversationProtocol,
    read_conversation_result,
)
from apps.assistant.src.adapters.fake_llm import FakeLLMAdapter
from apps.assistant.src.modules.behavior_preferences import BehaviorPreferenceChange
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
        self.principals = StaticConversationPrincipalResolver(
            {
                "android-personal-01": ConversationPrincipal(
                    scope=MemoryScope.USER,
                    scope_id="owner",
                    assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
                    source_node_id="android-personal-01",
                ),
                "android-personal-02": ConversationPrincipal(
                    scope=MemoryScope.USER,
                    scope_id="spouse",
                    assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
                    source_node_id="android-personal-02",
                ),
            }
        )
        self.core = build_core(llm=self.llm, conversation_principal_resolver=self.principals)
        self.protocol = ConversationProtocol(
            gateway=object(),
            conversation=self.core.conversation,
            orchestrator=self.core.orchestrator,
            preference_commands=self.core.preference_commands,
            behavior_preferences=self.core.behavior_preferences,
            conversation_principals=self.core.memory_principals,
        )
        self.node = AdmittedConversationNode(True, "android-personal-01", "node-session-1", "conversation.text")
        opened = self.protocol._dispatch(
            self.node,
            ConversationCommand("conversation.open", str(uuid4()), "node-session-1", 1),
        )
        self.conversation_id = opened.conversation_session_id
        self.assertEqual(opened.character_profile, {"name": "HearthGhost"})

    def test_name_preference_applies_locally_and_same_result_has_new_scoped_profile(self):
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
        self.assertEqual(
            self.core.behavior_preferences.snapshot(scope="user", scope_id="owner").persona.name,
            "루나",
        )
        self.assertEqual(
            self.core.behavior_preferences.snapshot(scope="user", scope_id="spouse").persona.name,
            "HearthGhost",
        )
        self.assertEqual(self.core.orchestrator.persona.name, "HearthGhost")
        self.assertEqual(len(self.llm.requests), 1)
        self.assertIn("BEHAVIOR_PREFERENCE_INTERPRETER_V1", self.llm.requests[0].instructions)

    def test_exact_character_selection_skips_interpreter_and_anchors_next_llm_turn(self):
        selected = self.protocol._dispatch(
            self.node,
            ConversationCommand(
                "conversation.text",
                str(uuid4()),
                "node-session-1",
                2,
                self.conversation_id,
                "캐릭터: 영희",
            ),
        )
        self.assertTrue(selected.accepted)
        self.assertEqual(selected.reason_code, "character_profile_selected")
        self.assertEqual(selected.character_profile, {"name": "영희"})
        self.assertIn("영희 캐릭터로 전환", selected.response_text)
        self.assertEqual(len(self.llm.requests), 0)

        ordinary = self.protocol._dispatch(
            self.node,
            ConversationCommand(
                "conversation.text",
                str(uuid4()),
                "node-session-1",
                3,
                self.conversation_id,
                "오늘 저녁 뭐부터 하면 좋을까?",
            ),
        )
        self.assertTrue(ordinary.accepted)
        self.assertEqual(ordinary.character_profile, {"name": "영희"})
        self.assertEqual(len(self.llm.requests), 1)
        instructions = self.llm.requests[0].instructions
        self.assertIn("Character identity: Younghee", instructions)
        self.assertIn("bright, quick, personable Korean cadence", instructions)
        self.assertNotIn("BEHAVIOR_PREFERENCE_INTERPRETER_V1", instructions)

    def test_exact_cheolsu_selection_is_scoped_and_does_not_change_spouse(self):
        selected = self.protocol._dispatch(
            self.node,
            ConversationCommand(
                "conversation.text",
                str(uuid4()),
                "node-session-1",
                2,
                self.conversation_id,
                "캐릭터: 철수",
            ),
        )
        self.assertTrue(selected.accepted)
        self.assertEqual(selected.character_profile, {"name": "철수"})
        self.assertEqual(len(self.llm.requests), 0)
        self.assertEqual(
            self.core.behavior_preferences.snapshot(scope="user", scope_id="owner").persona.name,
            "철수",
        )
        self.assertEqual(
            self.core.behavior_preferences.snapshot(scope="user", scope_id="spouse").persona.name,
            "HearthGhost",
        )

    def test_followup_preference_updates_only_current_principal_session(self):
        result = self.protocol._dispatch(
            self.node,
            ConversationCommand(
                "conversation.text",
                str(uuid4()),
                "node-session-1",
                2,
                self.conversation_id,
                "30초 정도 기다려",
            ),
        )
        self.assertTrue(result.accepted)
        session = self.core.conversation._repository.get(self.conversation_id)
        self.assertEqual(session.follow_up_timeout_sec, 30)

        other = AdmittedConversationNode(True, "android-personal-02", "node-session-2", "conversation.text")
        opened = self.protocol._dispatch(
            other,
            ConversationCommand("conversation.open", str(uuid4()), "node-session-2", 1),
        )
        other_session = self.core.conversation._repository.get(opened.conversation_session_id)
        self.assertEqual(other_session.follow_up_timeout_sec, 45)

    def test_ordinary_text_uses_scoped_persona_in_normal_llm_prompt(self):
        self.core.behavior_preferences.apply(
            (BehaviorPreferenceChange("character.name", "Luna"),),
            scope="user",
            scope_id="owner",
            updated_by_node_id="android-personal-01",
        )
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
        self.assertEqual(result.character_profile, {"name": "Luna"})
        self.assertEqual(len(self.llm.requests), 1)
        self.assertIn("persistent character name is Luna", self.llm.requests[0].instructions)
        self.assertNotIn("BEHAVIOR_PREFERENCE_INTERPRETER_V1", self.llm.requests[0].instructions)

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
        self.assertNotIn("BEHAVIOR_PREFERENCE_INTERPRETER_V1", self.llm.requests[0].instructions)

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
