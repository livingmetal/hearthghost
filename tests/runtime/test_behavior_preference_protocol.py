from __future__ import annotations

import unittest

from apps.assistant.src.adapters.behavior_preference_protocol import (
    parse_behavior_preference_update,
)


class BehaviorPreferenceProtocolTests(unittest.TestCase):
    def payload(self):
        return {
            "contract_version": "1.0",
            "proposal_id": "11111111-1111-4111-8111-111111111111",
            "proposed_at": "2026-08-11T08:00:00Z",
            "scope": "user",
            "scope_id": "owner",
            "origin": "llm_proposal",
            "status": "proposed",
            "changes": [
                {"path": "character.verbosity", "value": "concise"},
                {"path": "conversation.followup_timeout_sec", "value": 30},
            ],
        }

    def test_valid_contract_payload_becomes_typed_proposal(self):
        proposal = parse_behavior_preference_update(self.payload())

        self.assertEqual(proposal.proposal_id, "11111111-1111-4111-8111-111111111111")
        self.assertEqual(proposal.scope, "user")
        self.assertEqual(proposal.origin, "llm_proposal")
        self.assertEqual(proposal.changes[0].path, "character.verbosity")
        self.assertEqual(proposal.changes[0].value, "concise")
        self.assertEqual(proposal.changes[1].value, 30)
        self.assertIsNotNone(proposal.proposed_at.utcoffset())

    def test_unknown_top_level_field_is_rejected(self):
        payload = self.payload()
        payload["hard_policy"] = {"camera": "allow"}
        with self.assertRaises(ValueError):
            parse_behavior_preference_update(payload)

    def test_unknown_or_hard_policy_path_is_rejected(self):
        payload = self.payload()
        payload["changes"] = [{"path": "hard_policy.camera.stream", "value": "allow"}]
        with self.assertRaises(ValueError):
            parse_behavior_preference_update(payload)

    def test_schema_values_are_enforced_before_runtime_application(self):
        for path, value in (
            ("character.verbosity", "short"),
            ("character.initiative", "autonomous"),
            ("conversation.followup_timeout_sec", 121),
            ("conversation.followup_timeout_sec", True),
            ("proactive.frequency", "high"),
        ):
            with self.subTest(path=path, value=value):
                payload = self.payload()
                payload["changes"] = [{"path": path, "value": value}]
                with self.assertRaises(ValueError):
                    parse_behavior_preference_update(payload)

    def test_duplicate_paths_and_naive_timestamp_are_rejected(self):
        payload = self.payload()
        payload["changes"] = [
            {"path": "character.humor", "value": "low"},
            {"path": "character.humor", "value": "high"},
        ]
        with self.assertRaises(ValueError):
            parse_behavior_preference_update(payload)

        payload = self.payload()
        payload["proposed_at"] = "2026-08-11T08:00:00"
        with self.assertRaises(ValueError):
            parse_behavior_preference_update(payload)


if __name__ == "__main__":
    unittest.main()
