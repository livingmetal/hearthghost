from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from apps.assistant.src.adapters.in_memory_conversation import InMemoryConversationRepository
from apps.assistant.src.modules.behavior_preferences import (
    BehaviorPreferenceChange,
    BehaviorPreferenceManager,
)
from apps.assistant.src.modules.conversation import ConversationManager
from apps.assistant.src.modules.orchestrator import ConversationOrchestrator


class Clock:
    def now(self):
        return datetime(2026, 8, 11, tzinfo=timezone.utc)


class BehaviorPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.conversation = ConversationManager(
            repository=InMemoryConversationRepository(),
            clock=Clock(),
            follow_up_timeout=timedelta(seconds=45),
        )
        self.orchestrator = ConversationOrchestrator(
            conversation=self.conversation,
            privacy_gateway=object(),
            llm_timeout_seconds=15,
        )
        self.manager = BehaviorPreferenceManager(
            conversation=self.conversation,
            orchestrator=self.orchestrator,
        )

    def test_typed_update_applies_persona_and_timeout(self):
        updated = self.manager.apply(
            (
                BehaviorPreferenceChange("character.humor", "high"),
                BehaviorPreferenceChange("character.verbosity", "concise"),
                BehaviorPreferenceChange("conversation.followup_timeout_sec", 30),
            )
        )

        self.assertEqual(updated.persona.humor, "high")
        self.assertEqual(updated.persona.verbosity, "concise")
        self.assertEqual(updated.followup_timeout_sec, 30)
        self.assertEqual(self.conversation.follow_up_timeout, timedelta(seconds=30))
        self.assertEqual(self.orchestrator.persona, updated.persona)

    def test_invalid_change_rejects_entire_update_without_partial_mutation(self):
        before = self.manager.snapshot()

        with self.assertRaises(ValueError):
            self.manager.apply(
                (
                    BehaviorPreferenceChange("character.humor", "high"),
                    BehaviorPreferenceChange("conversation.followup_timeout_sec", 121),
                )
            )

        self.assertEqual(self.manager.snapshot(), before)

    def test_hard_policy_and_security_paths_are_not_representable(self):
        for path in (
            "hard_policy.camera.stream",
            "node.trust",
            "tool.grant",
            "cloud.image",
            "provider.api_key",
        ):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    self.manager.apply((BehaviorPreferenceChange(path, "allow"),))

    def test_duplicate_path_is_rejected_atomically(self):
        before = self.manager.snapshot()
        with self.assertRaises(ValueError):
            self.manager.apply(
                (
                    BehaviorPreferenceChange("character.formality", "formal"),
                    BehaviorPreferenceChange("character.formality", "casual"),
                )
            )
        self.assertEqual(self.manager.snapshot(), before)

    def test_schema_bounds_are_enforced(self):
        self.assertEqual(
            self.manager.apply(
                (BehaviorPreferenceChange("conversation.followup_timeout_sec", 5),)
            ).followup_timeout_sec,
            5,
        )
        self.assertEqual(
            self.manager.apply(
                (BehaviorPreferenceChange("conversation.followup_timeout_sec", 120),)
            ).followup_timeout_sec,
            120,
        )
        with self.assertRaises(ValueError):
            self.manager.apply(
                (BehaviorPreferenceChange("conversation.followup_timeout_sec", True),)
            )


if __name__ == "__main__":
    unittest.main()
