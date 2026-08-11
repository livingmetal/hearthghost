from __future__ import annotations

import unittest
from datetime import timedelta

from apps.assistant.src.adapters.fake_llm import FakeLLMAdapter
from apps.assistant.src.adapters.in_memory_conversation import InMemoryConversationRepository
from apps.assistant.src.modules.behavior_preference_interpreter import (
    BehaviorPreferenceInterpreter,
    BehaviorPreferenceService,
)
from apps.assistant.src.modules.behavior_preferences import BehaviorPreferenceManager
from apps.assistant.src.modules.conversation import ConversationManager
from apps.assistant.src.modules.node_security import SystemClock
from apps.assistant.src.modules.orchestrator import ConversationOrchestrator
from apps.assistant.src.modules.privacy_gateway import DEFAULT_CLOUD_PRIVACY_POLICY, PrivacyGateway


class _NoopPrivacyGateway:
    def generate(self, modality, request, *, timeout_seconds):
        raise AssertionError("not used")


class PreferenceInterpreterTests(unittest.TestCase):
    def _service(self):
        llm = FakeLLMAdapter()
        privacy = PrivacyGateway(llm=llm, policy=DEFAULT_CLOUD_PRIVACY_POLICY)
        conversation = ConversationManager(
            repository=InMemoryConversationRepository(),
            clock=SystemClock(),
            follow_up_timeout=timedelta(seconds=45),
        )
        orchestrator = ConversationOrchestrator(
            conversation=conversation,
            privacy_gateway=privacy,
            llm_timeout_seconds=5,
        )
        manager = BehaviorPreferenceManager(
            conversation=conversation,
            orchestrator=orchestrator,
        )
        interpreter = BehaviorPreferenceInterpreter(privacy_gateway=privacy)
        return BehaviorPreferenceService(interpreter=interpreter, manager=manager), llm

    def test_korean_request_applies_concise_preference(self):
        service, llm = self._service()

        result = service.interpret_and_apply(
            "답을 좀 짧게 해",
            scope="user",
            scope_id="owner",
        )

        self.assertTrue(result.recognized)
        self.assertTrue(result.applied)
        self.assertEqual(result.snapshot.persona.verbosity, "concise")
        self.assertIn("BEHAVIOR_PREFERENCE_INTERPRETER_V1", llm.requests[-1].instructions)

    def test_multiple_preferences_are_applied_atomically(self):
        service, _ = self._service()

        result = service.interpret_and_apply(
            "농담을 더 많이 하고 30초 정도 기다려",
            scope="user",
            scope_id="owner",
        )

        self.assertTrue(result.applied)
        self.assertEqual(result.snapshot.persona.humor, "high")
        self.assertEqual(result.snapshot.followup_timeout_sec, 30)

    def test_security_request_is_not_represented_as_preference(self):
        service, _ = self._service()

        result = service.interpret_and_apply(
            "카메라 보안 policy 제한을 풀어",
            scope="user",
            scope_id="owner",
        )

        self.assertFalse(result.recognized)
        self.assertFalse(result.applied)
        self.assertEqual(result.reason, "not_preference")

    def test_invalid_input_fails_before_provider(self):
        interpreter = BehaviorPreferenceInterpreter(privacy_gateway=_NoopPrivacyGateway())
        with self.assertRaises(ValueError):
            interpreter.interpret("", scope="user", scope_id="owner")
        with self.assertRaises(ValueError):
            interpreter.interpret("x" * 1001, scope="user", scope_id="owner")


if __name__ == "__main__":
    unittest.main()
