from __future__ import annotations

import unittest

from apps.assistant.src.adapters.behavior_preference_protocol import parse_behavior_preference_update
from apps.assistant.src.adapters.fake_llm import FakeLLMAdapter
from apps.assistant.src.adapters.in_memory_behavior_preferences import InMemoryBehaviorPreferenceRepository
from apps.assistant.src.modules.behavior_preference_command import BehaviorPreferenceCommandService
from apps.assistant.src.modules.behavior_preference_interpreter import (
    BehaviorPreferenceInterpreter,
    BehaviorPreferenceService,
)
from apps.assistant.src.modules.behavior_preferences import BehaviorPreferenceManager
from apps.assistant.src.modules.conversation_principal import (
    ConversationPrincipal,
    DenyingConversationPrincipalResolver,
    PrincipalAssurance,
    StaticConversationPrincipalResolver,
)
from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.node_security import SystemClock
from apps.assistant.src.modules.persona import PersonaProfile, require_persona_name
from apps.assistant.src.modules.privacy_gateway import DEFAULT_CLOUD_PRIVACY_POLICY, PrivacyGateway


class PersonaDisplayProfileTests(unittest.TestCase):
    def _preference_stack(self):
        llm = FakeLLMAdapter()
        privacy = PrivacyGateway(llm=llm, policy=DEFAULT_CLOUD_PRIVACY_POLICY)
        manager = BehaviorPreferenceManager(
            repository=InMemoryBehaviorPreferenceRepository(),
            clock=SystemClock(),
        )
        service = BehaviorPreferenceService(
            interpreter=BehaviorPreferenceInterpreter(privacy_gateway=privacy),
            manager=manager,
        )
        principal = ConversationPrincipal(
            scope=MemoryScope.USER,
            scope_id="owner",
            assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
            source_node_id="android-personal-01",
        )
        commands = BehaviorPreferenceCommandService(
            preferences=service,
            principals=StaticConversationPrincipalResolver({"android-personal-01": principal}),
        )
        return commands, manager, llm

    @staticmethod
    def snapshot(manager):
        return manager.snapshot(scope="user", scope_id="owner")

    def test_unicode_persona_names_are_display_safe(self):
        self.assertEqual(require_persona_name("루나"), "루나")
        self.assertEqual(require_persona_name("Luna 2"), "Luna 2")
        self.assertEqual(PersonaProfile(name="오르키아").name, "오르키아")

    def test_controls_format_characters_and_untrimmed_names_are_rejected(self):
        for name in (" Luna", "Luna ", "Luna\nAdmin", "Luna\u202eAdmin", "Luna\u200bAdmin", "x" * 81):
            with self.subTest(name=repr(name)), self.assertRaises(ValueError):
                require_persona_name(name)

    def test_typed_character_name_update_changes_exact_scope_only(self):
        commands, manager, _ = self._preference_stack()
        before = self.snapshot(manager)
        result = commands.handle(node_id="android-personal-01", text="이름을 루나로 바꿔줘")
        self.assertTrue(result.recognized)
        self.assertTrue(result.applied)
        after = self.snapshot(manager)
        self.assertEqual(after.persona.name, "루나")
        self.assertEqual(after.persona.humor, before.persona.humor)
        self.assertEqual(after.followup_timeout_sec, before.followup_timeout_sec)
        self.assertEqual(manager.snapshot(scope="user", scope_id="spouse").persona.name, "HearthGhost")

    def test_ordinary_conversation_does_not_invoke_preference_llm(self):
        commands, manager, llm = self._preference_stack()
        before = self.snapshot(manager)
        result = commands.handle(node_id="android-personal-01", text="오늘 날씨가 꽤 좋네")
        self.assertFalse(result.recognized)
        self.assertEqual(llm.requests, [])
        self.assertEqual(self.snapshot(manager), before)

    def test_unbound_node_cannot_change_persona(self):
        commands, manager, _ = self._preference_stack()
        denied = BehaviorPreferenceCommandService(
            preferences=commands._preferences,
            principals=DenyingConversationPrincipalResolver(),
        )
        before = self.snapshot(manager)
        result = denied.handle(node_id="unknown-node", text="이름을 루나로 바꿔줘")
        self.assertTrue(result.recognized)
        self.assertFalse(result.applied)
        self.assertEqual(result.reason, "principal_unresolved")
        self.assertEqual(self.snapshot(manager), before)

    def test_protocol_accepts_name_but_rejects_hidden_control_payload(self):
        payload = {
            "contract_version": "1.0",
            "proposal_id": "11111111-1111-4111-8111-111111111111",
            "proposed_at": "2026-08-11T20:00:00+09:00",
            "scope": "user",
            "scope_id": "owner",
            "origin": "user_interface",
            "status": "proposed",
            "changes": [{"path": "character.name", "value": "루나"}],
        }
        proposal = parse_behavior_preference_update(payload)
        self.assertEqual(proposal.changes[0].value, "루나")
        payload["changes"] = [{"path": "character.name", "value": "루나\u202eAdmin"}]
        with self.assertRaises(ValueError):
            parse_behavior_preference_update(payload)


if __name__ == "__main__":
    unittest.main()
