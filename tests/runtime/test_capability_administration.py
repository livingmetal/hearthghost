from __future__ import annotations

import unittest
from datetime import datetime, timezone

from apps.assistant.src.modules.capability_administration import (
    AdvertisementAdministrationRequest,
    CapabilityAdvertisementAdministration,
)
from apps.assistant.src.modules.node_administration import NodeAdministrationRecord
from apps.assistant.src.modules.node_security import (
    CapabilityAdvertisement,
    NodeTrustState,
)


NOW = datetime(2026, 8, 11, 13, tzinfo=timezone.utc)


class Clock:
    def now(self):
        return NOW


class Store:
    def __init__(self, record=None, applied=True):
        self.record = record
        self.applied = applied
        self.calls = []

    def get_node(self, node_id):
        self.calls.append(("get", node_id))
        return self.record

    def replace_advertisements_audited(self, **kwargs):
        self.calls.append(("replace", kwargs))
        return self.applied


def record(*, state=NodeTrustState.UNTRUSTED, revision=1):
    return NodeAdministrationRecord(
        node_id="android-development-01",
        trust_state=state,
        granted_capabilities=frozenset(),
        revision=revision,
        enrolled_at=NOW,
        updated_at=NOW,
    )


class CapabilityAdvertisementAdministrationTests(unittest.TestCase):
    def service(self, store, context=None):
        context = context if context is not None else object()
        return (
            CapabilityAdvertisementAdministration(
                authorized_context=context,
                actor_id="local-admin-api",
                store=store,
                clock=Clock(),
            ),
            context,
        )

    def request(self, advertisements, *, revision=1):
        return AdvertisementAdministrationRequest(
            correlation_id="admin-correlation",
            node_id="android-development-01",
            expected_node_revision=revision,
            advertisements=tuple(advertisements),
        )

    def test_authorized_replace_is_audited_and_does_not_grant(self):
        store = Store(record())
        service, context = self.service(store)
        ads = (
            CapabilityAdvertisement("conversation.text", False),
            CapabilityAdvertisement("notification.local", True),
        )
        result = service.replace(context, self.request(ads))
        self.assertTrue(result.succeeded)
        self.assertEqual(result.reason, "advertisements_replaced")
        replace_call = next(value for name, value in store.calls if name == "replace")
        self.assertEqual(replace_call["actor_id"], "local-admin-api")
        self.assertEqual(replace_call["correlation_id"], "admin-correlation")
        self.assertEqual(replace_call["expected_node_revision"], 1)
        self.assertEqual(replace_call["advertisements"], ads)
        self.assertEqual(store.record.granted_capabilities, frozenset())

    def test_wrong_process_context_is_denied_before_state_lookup(self):
        store = Store(record())
        service, _ = self.service(store)
        result = service.replace(
            object(),
            self.request((CapabilityAdvertisement("conversation.text", False),)),
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.reason, "administration_denied")
        self.assertEqual(store.calls, [])

    def test_notification_local_must_require_node_local_authorization(self):
        store = Store(record())
        service, context = self.service(store)
        result = service.replace(
            context,
            self.request((CapabilityAdvertisement("notification.local", False),)),
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.reason, "malformed_request")
        self.assertEqual(store.calls, [])

    def test_duplicate_capabilities_fail_closed(self):
        store = Store(record())
        service, context = self.service(store)
        result = service.replace(
            context,
            self.request(
                (
                    CapabilityAdvertisement("conversation.text", False),
                    CapabilityAdvertisement("conversation.text", False),
                )
            ),
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.reason, "malformed_request")

    def test_revoked_or_stale_node_cannot_change_advertisements(self):
        for store, expected in (
            (Store(record(state=NodeTrustState.REVOKED)), "node_revoked"),
            (Store(record(revision=2)), "revision_conflict"),
        ):
            with self.subTest(expected=expected):
                service, context = self.service(store)
                result = service.replace(
                    context,
                    self.request((CapabilityAdvertisement("conversation.text", False),), revision=1),
                )
                self.assertFalse(result.succeeded)
                self.assertEqual(result.reason, expected)
                self.assertFalse(any(name == "replace" for name, _ in store.calls))

    def test_store_cas_loss_is_reported_as_revision_conflict(self):
        store = Store(record(), applied=False)
        service, context = self.service(store)
        result = service.replace(
            context,
            self.request((CapabilityAdvertisement("conversation.text", False),)),
        )
        self.assertFalse(result.succeeded)
        self.assertEqual(result.reason, "revision_conflict")


if __name__ == "__main__":
    unittest.main()
