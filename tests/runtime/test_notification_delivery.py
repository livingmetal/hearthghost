from __future__ import annotations

import unittest
from datetime import datetime, timezone

from apps.assistant.src.modules.node_security import (
    CapabilityAdvertisement,
    NodeRecord,
    NodeTrustState,
)
from apps.assistant.src.modules.notification_delivery import (
    NOTIFICATION_CAPABILITY,
    NotificationAdapterRequest,
    NotificationAdapterResult,
    NotificationDeliveryIntent,
    NotificationDeliveryService,
)
from apps.assistant.src.modules.policy import PolicyEvaluationResult, UnconfiguredPolicyBoundary


NOW = datetime(2026, 8, 11, tzinfo=timezone.utc)
REMINDER_ID = "22222222-2222-2222-2222-222222222222"
NODE_ID = "android-personal-01"


class Nodes:
    def __init__(self, record=None):
        self.record = record

    def get(self, node_id):
        return self.record if self.record is not None and self.record.node_id == node_id else None


class AllowPolicy:
    def __init__(self):
        self.proposals = []

    def evaluate(self, proposal):
        self.proposals.append(proposal)
        return PolicyEvaluationResult(True, "notification_allowed", "test-policy-v1")


class SpyDelivery:
    def __init__(self, result=None):
        self.requests = []
        self.result = result or NotificationAdapterResult(
            True,
            "delivered",
            local_authorization_confirmed=True,
        )

    def deliver(self, request):
        self.requests.append(request)
        return self.result


class ExplodingDelivery:
    def deliver(self, request):
        raise AssertionError("delivery adapter must not be called")


def node(*, trusted=True, advertised=True, granted=True, local_auth=True):
    advertisements = (
        (CapabilityAdvertisement(NOTIFICATION_CAPABILITY, local_auth),)
        if advertised
        else ()
    )
    grants = frozenset({NOTIFICATION_CAPABILITY}) if granted else frozenset()
    return NodeRecord(
        node_id=NODE_ID,
        trust_state=NodeTrustState.TRUSTED if trusted else NodeTrustState.UNTRUSTED,
        advertised_capabilities=advertisements,
        granted_capabilities=grants,
    )


def intent():
    return NotificationDeliveryIntent(REMINDER_ID, NODE_ID, NOW)


class NotificationDeliveryTests(unittest.TestCase):
    def test_unconfigured_policy_prevents_adapter_call(self):
        service = NotificationDeliveryService(
            policy=UnconfiguredPolicyBoundary(),
            nodes=Nodes(node()),
            delivery=ExplodingDelivery(),
        )
        result = service.deliver(intent())
        self.assertFalse(result.delivered)
        self.assertEqual(result.reason, "policy_not_configured")

    def test_node_must_be_trusted_advertised_granted_and_locally_gated(self):
        cases = (
            (node(trusted=False), "notification_node_not_trusted"),
            (node(advertised=False), "notification_capability_not_advertised"),
            (node(granted=False), "notification_capability_not_granted"),
            (node(local_auth=False), "notification_local_authorization_not_required"),
        )
        for record, reason in cases:
            with self.subTest(reason=reason):
                service = NotificationDeliveryService(
                    policy=AllowPolicy(), nodes=Nodes(record), delivery=ExplodingDelivery()
                )
                result = service.deliver(intent())
                self.assertFalse(result.delivered)
                self.assertEqual(result.reason, reason)

    def test_authorized_attempt_sends_redacted_payload_only(self):
        policy = AllowPolicy()
        delivery = SpyDelivery()
        service = NotificationDeliveryService(policy=policy, nodes=Nodes(node()), delivery=delivery)
        result = service.deliver(intent())
        self.assertTrue(result.delivered)
        self.assertEqual(result.reason, "delivered")
        self.assertEqual(len(delivery.requests), 1)
        request = delivery.requests[0]
        self.assertIsInstance(request, NotificationAdapterRequest)
        self.assertEqual(request.title, "HearthGhost")
        self.assertEqual(request.body, "Reminder")
        self.assertEqual(request.content_mode, "redacted")
        self.assertTrue(request.local_authorization_required)
        self.assertEqual(request.fire_at, NOW)
        self.assertFalse(hasattr(request, "todo_text"))
        proposal = policy.proposals[0]
        self.assertEqual(proposal.name, NOTIFICATION_CAPABILITY)
        self.assertEqual(proposal.arguments["content_mode"], "redacted")
        self.assertEqual(proposal.arguments["fire_at"], NOW.isoformat())

    def test_delivered_adapter_result_cannot_omit_local_authorization_confirmation(self):
        with self.assertRaisesRegex(ValueError, "confirmed local authorization"):
            NotificationAdapterResult(True, "delivered")

    def test_adapter_request_cannot_weaken_redaction_or_local_gate(self):
        with self.assertRaises(ValueError):
            NotificationAdapterRequest(
                REMINDER_ID,
                NODE_ID,
                NOW,
                title="Private todo text",
            )
        with self.assertRaises(ValueError):
            NotificationAdapterRequest(
                REMINDER_ID,
                NODE_ID,
                NOW,
                local_authorization_required=False,
            )

    def test_invalid_adapter_result_fails_closed(self):
        class InvalidDelivery:
            def deliver(self, request):
                return True

        service = NotificationDeliveryService(
            policy=AllowPolicy(), nodes=Nodes(node()), delivery=InvalidDelivery()
        )
        result = service.deliver(intent())
        self.assertFalse(result.delivered)
        self.assertEqual(result.reason, "delivery_adapter_invalid_result")

    def test_unknown_node_and_adapter_failure_fail_closed(self):
        service = NotificationDeliveryService(
            policy=AllowPolicy(), nodes=Nodes(), delivery=ExplodingDelivery()
        )
        self.assertEqual(service.deliver(intent()).reason, "notification_node_unknown")

        class BrokenDelivery:
            def deliver(self, request):
                raise RuntimeError("offline")

        service = NotificationDeliveryService(
            policy=AllowPolicy(), nodes=Nodes(node()), delivery=BrokenDelivery()
        )
        self.assertEqual(service.deliver(intent()).reason, "delivery_adapter_unavailable")


if __name__ == "__main__":
    unittest.main()
