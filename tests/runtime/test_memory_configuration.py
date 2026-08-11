from __future__ import annotations

import unittest

from apps.assistant.src.modules.conversation_principal import PrincipalAssurance
from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.runtime.memory_configuration import parse_memory_principal_bindings


class MemoryConfigurationTests(unittest.TestCase):
    def test_parses_personal_and_household_bindings(self):
        resolver = parse_memory_principal_bindings(
            [
                "android-personal-01=user:owner",
                "kitchen-display=household:home",
            ]
        )

        personal = resolver.resolve("android-personal-01")
        household = resolver.resolve("kitchen-display")
        self.assertEqual(personal.scope, MemoryScope.USER)
        self.assertEqual(personal.scope_id, "owner")
        self.assertEqual(personal.assurance, PrincipalAssurance.PERSONAL_NODE_BINDING)
        self.assertEqual(household.scope, MemoryScope.HOUSEHOLD)
        self.assertEqual(household.scope_id, "home")
        self.assertEqual(household.assurance, PrincipalAssurance.HOUSEHOLD_NODE_BINDING)

    def test_duplicate_node_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate Node"):
            parse_memory_principal_bindings(
                ["android=user:owner", "android=household:home"]
            )

    def test_unknown_scope_and_malformed_values_are_rejected(self):
        for value in (
            "android=admin:owner",
            "android=user",
            "=user:owner",
            "android=:owner",
            "android=user:",
            "android",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_memory_principal_bindings([value])

    def test_empty_configuration_resolves_nothing(self):
        resolver = parse_memory_principal_bindings([])
        self.assertIsNone(resolver.resolve("android"))


if __name__ == "__main__":
    unittest.main()
