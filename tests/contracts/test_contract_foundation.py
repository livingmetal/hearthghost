import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"

EXPECTED_SCHEMAS = {
    "events/v1/conversation-state.schema.json",
    "events/v1/character-state.schema.json",
    "events/v1/character-emotion.schema.json",
    "events/v1/audit-event.schema.json",
    "tools/v1/tool-definition.schema.json",
    "tools/v1/tool-proposal.schema.json",
    "policy/v1/policy-decision.schema.json",
    "policy/v1/behavior-preference-update.schema.json",
    "node/v1/node-identity.schema.json",
    "node/v1/node-capabilities.schema.json",
}


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=reject_duplicate_keys)


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


class ContractFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = sorted(CONTRACTS.glob("**/*.schema.json"))
        cls.schemas = {
            path.relative_to(CONTRACTS).as_posix(): load_json(path)
            for path in cls.paths
        }

    def test_required_contract_catalog_is_present(self):
        self.assertEqual(EXPECTED_SCHEMAS, set(self.schemas))

    def test_schema_identifiers_are_unique(self):
        identifiers = [schema["$id"] for schema in self.schemas.values()]
        self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_every_schema_is_versioned_and_closed_at_top_level(self):
        for relative_path, schema in self.schemas.items():
            with self.subTest(schema=relative_path):
                self.assertEqual(
                    "https://json-schema.org/draft/2020-12/schema",
                    schema.get("$schema"),
                )
                self.assertIn(":v1.0:", schema.get("$id", ""))
                self.assertEqual("object", schema.get("type"))
                self.assertIs(schema.get("additionalProperties"), False)
                self.assertIn("contract_version", schema.get("required", []))
                self.assertEqual(
                    "1.0",
                    schema.get("properties", {})
                    .get("contract_version", {})
                    .get("const"),
                )
                self.assertTrue(
                    set(schema.get("required", [])).issubset(
                        schema.get("properties", {})
                    )
                )

    def test_schema_regular_expressions_compile(self):
        for relative_path, schema in self.schemas.items():
            for item in walk(schema):
                if isinstance(item, dict) and "pattern" in item:
                    with self.subTest(schema=relative_path, pattern=item["pattern"]):
                        re.compile(item["pattern"])

    def test_generic_contracts_do_not_define_base64_media(self):
        forbidden = {"audio_data", "image_data", "video_data", "media_base64"}
        for relative_path, schema in self.schemas.items():
            for item in walk(schema):
                if isinstance(item, dict):
                    with self.subTest(schema=relative_path):
                        self.assertTrue(forbidden.isdisjoint(item.keys()))
                        self.assertNotEqual("base64", item.get("contentEncoding"))

    def test_tool_proposal_is_not_execution_authority(self):
        proposal = self.schemas["tools/v1/tool-proposal.schema.json"]
        self.assertEqual(
            "pending_policy",
            proposal["properties"]["authorization_status"]["const"],
        )
        self.assertIn("proposed_at", proposal["required"])
        self.assertEqual("date-time", proposal["properties"]["proposed_at"]["format"])

    def test_policy_decision_is_explicit_allow_or_deny(self):
        decision = self.schemas["policy/v1/policy-decision.schema.json"]
        self.assertEqual(
            {"allow", "deny"}, set(decision["properties"]["decision"]["enum"])
        )
        self.assertIn("confirmation_policy", decision["required"])
        self.assertIn("confirmation_id", decision["allOf"][1]["then"]["required"])
        self.assertEqual(
            {"none", "contextual", "explicit"},
            set(decision["properties"]["confirmation_policy"]["enum"]),
        )

    def test_sleeping_state_does_not_require_an_active_session(self):
        conversation = self.schemas["events/v1/conversation-state.schema.json"]
        self.assertNotIn("session_id", conversation["required"])
        self.assertIn("session_id", conversation["allOf"][0]["then"]["required"])

    def test_behavior_updates_cannot_name_hard_policy_paths(self):
        update = self.schemas["policy/v1/behavior-preference-update.schema.json"]
        alternatives = update["properties"]["changes"]["items"]["oneOf"]
        paths = {item["properties"]["path"]["const"] for item in alternatives}
        self.assertTrue(paths)
        self.assertTrue(all(not path.startswith("hard_policy.") for path in paths))
        self.assertNotIn("security", update["properties"]["scope"]["enum"])
        self.assertIn("proposed_at", update["required"])

    def test_node_identity_requires_independent_revocation(self):
        identity = self.schemas["node/v1/node-identity.schema.json"]
        identity_properties = identity["properties"]["identity"]
        self.assertIn("independently_revocable", identity_properties["required"])
        self.assertIn("credential_id", identity_properties["required"])
        self.assertNotIn("key_id", identity_properties["properties"])
        self.assertIs(
            identity_properties["properties"]["independently_revocable"]["const"],
            True,
        )
        revoked_states = identity["allOf"][0]["if"]["properties"]["identity"][
            "properties"
        ]["status"]["enum"]
        self.assertEqual({"revoked", "expired"}, set(revoked_states))
        self.assertEqual(
            "revoked",
            identity["allOf"][0]["then"]["properties"]["security_state"][
                "const"
            ],
        )

    def test_node_capability_names_support_documented_simple_and_namespaced_forms(self):
        capabilities = self.schemas["node/v1/node-capabilities.schema.json"]
        pattern = capabilities["properties"]["capabilities"]["items"]["properties"][
            "name"
        ]["pattern"]
        self.assertIsNotNone(re.fullmatch(pattern, "display"))
        self.assertIsNotNone(re.fullmatch(pattern, "camera.snapshot"))
        capability_properties = capabilities["properties"]["capabilities"]["items"][
            "properties"
        ]
        self.assertNotIn("risk_level", capability_properties)
        tool_properties = self.schemas["tools/v1/tool-definition.schema.json"][
            "properties"
        ]
        self.assertIn("risk_level", tool_properties)

    def test_untrusted_nodes_and_sensitive_media_capabilities_are_constrained(self):
        capabilities = self.schemas["node/v1/node-capabilities.schema.json"]
        capability_rule = capabilities["properties"]["capabilities"]["items"][
            "allOf"
        ][0]
        sensitive_names = set(
            capability_rule["if"]["properties"]["name"]["enum"]
        )
        self.assertTrue(
            {"camera.snapshot", "camera.stream", "microphone"}.issubset(
                sensitive_names
            )
        )
        self.assertIs(
            capability_rule["then"]["properties"][
                "local_authorization_required"
            ]["const"],
            True,
        )
        self.assertEqual(
            0,
            capabilities["allOf"][0]["then"]["properties"][
                "granted_permissions"
            ]["maxItems"],
        )

    def test_audit_metadata_is_allowlisted(self):
        audit = self.schemas["events/v1/audit-event.schema.json"]
        self.assertIn("correlation_id", audit["required"])
        metadata = audit["properties"]["metadata"]
        self.assertIs(metadata["additionalProperties"], False)
        self.assertTrue(
            {"audio", "image", "video", "transcript", "secret"}.isdisjoint(
                metadata["properties"]
            )
        )
        self.assertIn("reason_code", audit["allOf"][0]["then"]["required"])


if __name__ == "__main__":
    unittest.main()
