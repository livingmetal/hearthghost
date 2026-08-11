from __future__ import annotations

import unittest
from datetime import datetime, timezone

from apps.assistant.src.adapters.in_memory_behavior_preferences import InMemoryBehaviorPreferenceRepository
from apps.assistant.src.modules.behavior_preferences import (
    BehaviorPreferenceChange,
    BehaviorPreferenceManager,
)
from apps.assistant.src.modules.persona import PersonaProfile


class Clock:
    def now(self):
        return datetime(2026, 8, 11, tzinfo=timezone.utc)


class BehaviorPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryBehaviorPreferenceRepository()
        self.manager = BehaviorPreferenceManager(
            repository=self.repository,
            clock=Clock(),
        )

    def snapshot(self, scope_id="owner"):
        return self.manager.snapshot(scope="user", scope_id=scope_id)

    def apply(self, *changes, scope_id="owner", node_id="android-personal-01"):
        return self.manager.apply(
            changes,
            scope="user",
            scope_id=scope_id,
            updated_by_node_id=node_id,
        )

    def test_typed_update_applies_only_exact_principal_scope(self):
        updated = self.apply(
            BehaviorPreferenceChange("character.humor", "high"),
            BehaviorPreferenceChange("character.verbosity", "concise"),
            BehaviorPreferenceChange("conversation.followup_timeout_sec", 30),
        )

        self.assertEqual(updated.persona.humor, "high")
        self.assertEqual(updated.persona.verbosity, "concise")
        self.assertEqual(updated.followup_timeout_sec, 30)
        self.assertEqual(self.snapshot().followup_timeout_sec, 30)
        self.assertEqual(self.snapshot("spouse").followup_timeout_sec, 45)
        self.assertEqual(self.snapshot("spouse").persona.humor, "moderate")

    def test_named_profiles_have_distinct_strong_style_anchors(self):
        younghee = PersonaProfile(name="영희").conversation_instructions()
        cheolsu = PersonaProfile(name="철수").conversation_instructions()

        self.assertIn("AvatarSample_A", younghee)
        self.assertIn("bright, quick, personable Korean cadence", younghee)
        self.assertIn("AvatarSample_C", cheolsu)
        self.assertIn("calm, grounded, economical Korean cadence", cheolsu)
        self.assertIn("strong non-security behavior anchor", younghee)
        self.assertIn("strong non-security behavior anchor", cheolsu)
        self.assertNotEqual(younghee, cheolsu)

    def test_invalid_change_rejects_entire_update_without_partial_mutation(self):
        before = self.snapshot()

        with self.assertRaises(ValueError):
            self.apply(
                BehaviorPreferenceChange("character.humor", "high"),
                BehaviorPreferenceChange("conversation.followup_timeout_sec", 121),
            )

        self.assertEqual(self.snapshot(), before)

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
                    self.apply(BehaviorPreferenceChange(path, "allow"))

    def test_duplicate_path_is_rejected_atomically(self):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.apply(
                BehaviorPreferenceChange("character.formality", "formal"),
                BehaviorPreferenceChange("character.formality", "casual"),
            )
        self.assertEqual(self.snapshot(), before)

    def test_schema_bounds_are_enforced(self):
        self.assertEqual(
            self.apply(BehaviorPreferenceChange("conversation.followup_timeout_sec", 5)).followup_timeout_sec,
            5,
        )
        self.assertEqual(
            self.apply(BehaviorPreferenceChange("conversation.followup_timeout_sec", 120)).followup_timeout_sec,
            120,
        )
        with self.assertRaises(ValueError):
            self.apply(BehaviorPreferenceChange("conversation.followup_timeout_sec", True))

    def test_revision_increments_and_audit_node_is_stored(self):
        self.apply(BehaviorPreferenceChange("character.name", "Luna"))
        first = self.repository.get("user", "owner")
        self.apply(BehaviorPreferenceChange("character.humor", "high"), node_id="android-personal-02")
        second = self.repository.get("user", "owner")

        self.assertEqual(first.revision, 1)
        self.assertEqual(second.revision, 2)
        self.assertEqual(second.updated_by_node_id, "android-personal-02")

    def test_user_and_household_are_distinct_even_with_same_scope_id(self):
        self.apply(BehaviorPreferenceChange("character.name", "Private"))
        household = self.manager.snapshot(scope="household", scope_id="owner")
        self.assertEqual(household.persona.name, "HearthGhost")


if __name__ == "__main__":
    unittest.main()
