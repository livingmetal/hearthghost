from __future__ import annotations

import unittest

from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.notification_target import (
    DenyingNotificationTargetResolver,
    StaticNotificationTargetResolver,
)
from apps.assistant.src.runtime.notification_configuration import (
    parse_notification_target_bindings,
)


class NotificationTargetTests(unittest.TestCase):
    def test_default_resolver_denies_every_route(self):
        resolver = DenyingNotificationTargetResolver()
        self.assertIsNone(resolver.resolve("user", "owner"))
        self.assertIsNone(resolver.resolve("household", "home"))

    def test_static_resolver_requires_exact_principal_match(self):
        resolver = StaticNotificationTargetResolver(
            {
                (MemoryScope.USER, "owner"): "android-personal-01",
                (MemoryScope.HOUSEHOLD, "home"): "wall-panel-01",
            }
        )
        self.assertEqual(resolver.resolve("user", "owner"), "android-personal-01")
        self.assertEqual(resolver.resolve("household", "home"), "wall-panel-01")
        self.assertIsNone(resolver.resolve("user", "other"))
        self.assertIsNone(resolver.resolve("invalid", "owner"))
        self.assertIsNone(resolver.resolve("user", ""))

    def test_parser_accepts_explicit_one_to_one_routes(self):
        resolver = parse_notification_target_bindings(
            [
                "user:owner=android-personal-01",
                "household:home=wall-panel-01",
            ]
        )
        self.assertEqual(resolver.resolve("user", "owner"), "android-personal-01")
        self.assertEqual(resolver.resolve("household", "home"), "wall-panel-01")

    def test_parser_rejects_duplicate_principal_and_node_routes(self):
        with self.assertRaisesRegex(ValueError, "duplicate principal"):
            parse_notification_target_bindings(
                [
                    "user:owner=android-personal-01",
                    "user:owner=android-personal-02",
                ]
            )
        with self.assertRaisesRegex(ValueError, "only one principal"):
            parse_notification_target_bindings(
                [
                    "user:owner=android-personal-01",
                    "household:home=android-personal-01",
                ]
            )

    def test_parser_rejects_ambiguous_or_malformed_routes(self):
        invalid = (
            "owner=android-personal-01",
            "user:=android-personal-01",
            "user:owner=",
            "other:owner=android-personal-01",
            "user:owner=BAD NODE",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_notification_target_bindings([value])


if __name__ == "__main__":
    unittest.main()
