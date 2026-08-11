from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.notification_delivery import NotificationDeliveryResult
from apps.assistant.src.modules.reminder import ReminderRecord, ReminderSource
from apps.assistant.src.modules.reminder_scheduler import (
    MAX_ATTEMPTS,
    ReminderDeliveryClaim,
    ReminderScheduler,
)


NOW = datetime(2026, 8, 11, 13, tzinfo=timezone.utc)
REMINDER_ID = "22222222-2222-2222-2222-222222222222"
TODO_ID = "11111111-1111-1111-1111-111111111111"
CLAIM_TOKEN = "33333333-3333-3333-3333-333333333333"


class Clock:
    def __init__(self, now=NOW):
        self.current = now

    def now(self):
        return self.current


class Claims:
    def __init__(self, claim=None, *, current=True):
        self.claim = claim
        self.current = current
        self.calls = []

    def claim_due(self, **kwargs):
        self.calls.append(("claim_due", kwargs))
        return self.claim

    def claim_is_current(self, claim):
        self.calls.append(("claim_is_current", claim))
        return self.current

    def mark_delivered(self, claim, **kwargs):
        self.calls.append(("mark_delivered", kwargs))
        return True

    def mark_retry(self, claim, **kwargs):
        self.calls.append(("mark_retry", kwargs))
        return True

    def mark_exhausted(self, claim, **kwargs):
        self.calls.append(("mark_exhausted", kwargs))
        return True


class Targets:
    def __init__(self, target="android-personal-01"):
        self.target = target
        self.calls = []

    def resolve(self, scope, scope_id):
        self.calls.append((scope, scope_id))
        return self.target


class Delivery:
    def __init__(self, result=NotificationDeliveryResult(True, "delivered")):
        self.result = result
        self.intents = []

    def deliver(self, intent):
        self.intents.append(intent)
        return self.result


def reminder():
    return ReminderRecord(
        reminder_id=REMINDER_ID,
        scope=MemoryScope.USER,
        scope_id="owner",
        todo_id=TODO_ID,
        fire_at=NOW - timedelta(seconds=1),
        source=ReminderSource.TODO_DUE,
        created_by_node_id="creator-node-must-not-be-target",
        created_at=NOW - timedelta(days=1),
    )


def claim(*, attempts=1):
    return ReminderDeliveryClaim(
        reminder=reminder(),
        claim_token=CLAIM_TOKEN,
        claim_owner="core-home-01",
        claim_until=NOW + timedelta(seconds=30),
        attempt_count=attempts,
        claimed_at=NOW,
    )


class ReminderSchedulerTests(unittest.TestCase):
    def scheduler(self, claims, targets=None, delivery=None):
        return ReminderScheduler(
            claims=claims,
            targets=targets or Targets(),
            delivery=delivery or Delivery(),
            clock=Clock(),
            claim_owner="core-home-01",
        )

    def test_idle_when_no_due_claim_exists(self):
        result = self.scheduler(Claims()).run_once()
        self.assertFalse(result.processed)
        self.assertEqual(result.reason, "no_due_reminder")

    def test_success_uses_explicit_principal_route_and_commits_delivery(self):
        claims = Claims(claim())
        targets = Targets("android-notification-01")
        delivery = Delivery()
        result = self.scheduler(claims, targets, delivery).run_once()
        self.assertTrue(result.processed)
        self.assertTrue(result.delivered)
        self.assertEqual(targets.calls, [("user", "owner")])
        self.assertEqual(delivery.intents[0].target_node_id, "android-notification-01")
        self.assertNotEqual(delivery.intents[0].target_node_id, reminder().created_by_node_id)
        self.assertEqual(delivery.intents[0].reminder_id, REMINDER_ID)
        self.assertEqual([name for name, _ in claims.calls], ["claim_due", "claim_is_current", "mark_delivered"])

    def test_invalidated_claim_never_reaches_delivery_or_target_resolution(self):
        claims = Claims(claim(), current=False)
        targets = Targets()
        delivery = Delivery()
        result = self.scheduler(claims, targets, delivery).run_once()
        self.assertEqual(result.reason, "claim_invalidated")
        self.assertEqual(targets.calls, [])
        self.assertEqual(delivery.intents, [])

    def test_unresolved_target_is_retried_with_bounded_backoff(self):
        claims = Claims(claim(attempts=2))
        result = self.scheduler(claims, Targets(None), Delivery()).run_once()
        self.assertFalse(result.delivered)
        self.assertEqual(result.reason, "notification_target_unresolved")
        retry = next(kwargs for name, kwargs in claims.calls if name == "mark_retry")
        self.assertEqual(retry["next_attempt_at"], NOW + timedelta(minutes=2))
        self.assertEqual(retry["reason"], "notification_target_unresolved")

    def test_delivery_denial_retries_without_bypassing_authority(self):
        claims = Claims(claim(attempts=1))
        delivery = Delivery(NotificationDeliveryResult(False, "notification_capability_not_granted"))
        result = self.scheduler(claims, Targets(), delivery).run_once()
        self.assertFalse(result.delivered)
        self.assertEqual(result.reason, "notification_capability_not_granted")
        self.assertTrue(any(name == "mark_retry" for name, _ in claims.calls))

    def test_max_attempts_marks_exhausted_instead_of_hot_looping(self):
        claims = Claims(claim(attempts=MAX_ATTEMPTS))
        delivery = Delivery(NotificationDeliveryResult(False, "delivery_adapter_unavailable"))
        result = self.scheduler(claims, Targets(), delivery).run_once()
        self.assertFalse(result.delivered)
        self.assertEqual(result.reason, "delivery_exhausted")
        self.assertTrue(any(name == "mark_exhausted" for name, _ in claims.calls))
        self.assertFalse(any(name == "mark_retry" for name, _ in claims.calls))

    def test_claim_not_due_is_not_delivered_even_if_repository_is_wrong(self):
        bad = replace(claim(), reminder=replace(reminder(), fire_at=NOW + timedelta(minutes=5)))
        claims = Claims(bad)
        delivery = Delivery()
        result = self.scheduler(claims, Targets(), delivery).run_once()
        self.assertEqual(result.reason, "claim_not_due")
        self.assertEqual(delivery.intents, [])

    def test_lost_commit_after_external_success_is_reported_not_faked_as_success(self):
        claims = Claims(claim())
        claims.mark_delivered = lambda claim, **kwargs: False
        result = self.scheduler(claims, Targets(), Delivery()).run_once()
        self.assertFalse(result.delivered)
        self.assertEqual(result.reason, "delivery_commit_lost")


if __name__ == "__main__":
    unittest.main()
