from __future__ import annotations

import unittest

from apps.assistant.src.modules.conversation_principal import (
    ConversationPrincipal,
    DenyingConversationPrincipalResolver,
    PrincipalAssurance,
    StaticConversationPrincipalResolver,
)
from apps.assistant.src.modules.memory import MemoryScope


class ConversationPrincipalTests(unittest.TestCase):
    def test_default_resolver_denies_every_node(self):
        resolver = DenyingConversationPrincipalResolver()
        self.assertIsNone(resolver.resolve("android-personal-01"))

    def test_personal_node_can_be_explicitly_bound_to_user_scope(self):
        principal = ConversationPrincipal(
            scope=MemoryScope.USER,
            scope_id="owner",
            assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
            source_node_id="android-personal-01",
        )
        resolver = StaticConversationPrincipalResolver(
            {"android-personal-01": principal}
        )

        self.assertEqual(resolver.resolve("android-personal-01"), principal)
        self.assertIsNone(resolver.resolve("unknown-node"))

    def test_node_id_never_becomes_user_id_implicitly(self):
        resolver = StaticConversationPrincipalResolver({})
        self.assertIsNone(resolver.resolve("owner"))

    def test_user_scope_rejects_household_assurance(self):
        with self.assertRaisesRegex(ValueError, "personal Node binding"):
            StaticConversationPrincipalResolver(
                {
                    "shared-tablet": ConversationPrincipal(
                        scope=MemoryScope.USER,
                        scope_id="owner",
                        assurance=PrincipalAssurance.HOUSEHOLD_NODE_BINDING,
                        source_node_id="shared-tablet",
                    )
                }
            )

    def test_household_scope_rejects_personal_assurance(self):
        with self.assertRaisesRegex(ValueError, "household Node binding"):
            StaticConversationPrincipalResolver(
                {
                    "android-personal-01": ConversationPrincipal(
                        scope=MemoryScope.HOUSEHOLD,
                        scope_id="home",
                        assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
                        source_node_id="android-personal-01",
                    )
                }
            )

    def test_binding_key_must_match_evidence_source_node(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            StaticConversationPrincipalResolver(
                {
                    "android-a": ConversationPrincipal(
                        scope=MemoryScope.USER,
                        scope_id="owner",
                        assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
                        source_node_id="android-b",
                    )
                }
            )


if __name__ == "__main__":
    unittest.main()
