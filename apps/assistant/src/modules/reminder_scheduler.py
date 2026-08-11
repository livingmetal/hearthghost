"""Bounded reminder scheduler using atomic leases and existing delivery authority.

The scheduler does not create reminder authority, infer a target Node, or bypass
Policy/local authorization. It only claims already-scheduled due work, resolves
an explicit principal-to-Node route, and asks NotificationDeliveryService to
attempt the redacted delivery.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from apps.assistant.src.modules.notification_delivery import (
    NotificationDeliveryIntent,
    NotificationDeliveryService,
)
from apps.assistant.src.modules.reminder import ReminderRecord, ReminderState
from apps.assistant.src.ports.node_gateway import Clock
from apps.assistant.src.ports.notification_target import NotificationTargetResolver
from apps.assistant.src.ports.reminder_scheduler import ReminderClaimRepository


DEFAULT_LEASE = timedelta(seconds=30)
MAX_LEASE = timedelta(minutes=5)
MAX_ATTEMPTS = 8
BASE_RETRY = timedelta(minutes=1)
MAX_RETRY = timedelta(hours=1)


@dataclass(frozen=True)
class ReminderDeliveryClaim:
    reminder: ReminderRecord
    claim_token: str
    claim_owner: str
    claim_until: datetime
    attempt_count: int
    claimed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.reminder, ReminderRecord) or self.reminder.state is not ReminderState.SCHEDULED:
            raise ValueError("claim requires a scheduled reminder")
        _require_uuid(self.claim_token, "claim_token")
        _require_identifier(self.claim_owner, "claim_owner")
        if not _aware(self.claim_until) or not _aware(self.claimed_at):
            raise ValueError("claim timestamps must be timezone-aware")
        if self.claim_until <= self.claimed_at:
            raise ValueError("claim lease must end after claim time")
        if not isinstance(self.attempt_count, int) or isinstance(self.attempt_count, bool) or self.attempt_count <= 0:
            raise ValueError("claim attempt_count must be positive")


@dataclass(frozen=True)
class SchedulerRunResult:
    processed: bool
    delivered: bool
    reason: str
    reminder_id: str | None = None
    attempt_count: int = 0


class ReminderScheduler:
    def __init__(
        self,
        *,
        claims: ReminderClaimRepository,
        targets: NotificationTargetResolver,
        delivery: NotificationDeliveryService,
        clock: Clock,
        claim_owner: str,
        lease: timedelta = DEFAULT_LEASE,
    ) -> None:
        _require_identifier(claim_owner, "claim_owner")
        if not isinstance(lease, timedelta) or lease <= timedelta(0) or lease > MAX_LEASE:
            raise ValueError("reminder scheduler lease must be > 0 and <= 5 minutes")
        self._claims = claims
        self._targets = targets
        self._delivery = delivery
        self._clock = clock
        self._claim_owner = claim_owner
        self._lease = lease

    def run_once(self) -> SchedulerRunResult:
        now = self._now()
        try:
            claim = self._claims.claim_due(
                now=now,
                claim_owner=self._claim_owner,
                claim_until=now + self._lease,
            )
        except Exception:
            return SchedulerRunResult(False, False, "claim_repository_unavailable")
        if claim is None:
            return SchedulerRunResult(False, False, "no_due_reminder")
        if not isinstance(claim, ReminderDeliveryClaim):
            return SchedulerRunResult(False, False, "claim_repository_invalid_result")

        reminder = claim.reminder
        if reminder.fire_at > now:
            return SchedulerRunResult(True, False, "claim_not_due", reminder.reminder_id, claim.attempt_count)
        try:
            current = self._claims.claim_is_current(claim)
        except Exception:
            return SchedulerRunResult(True, False, "claim_validation_unavailable", reminder.reminder_id, claim.attempt_count)
        if current is not True:
            return SchedulerRunResult(True, False, "claim_invalidated", reminder.reminder_id, claim.attempt_count)

        try:
            target = self._targets.resolve(reminder.scope.value, reminder.scope_id)
        except Exception:
            return self._retry_or_exhaust(claim, now=now, reason="notification_target_unavailable")
        if target is None:
            return self._retry_or_exhaust(claim, now=now, reason="notification_target_unresolved")

        result = self._delivery.deliver(
            NotificationDeliveryIntent(
                reminder_id=reminder.reminder_id,
                target_node_id=target,
                fire_at=reminder.fire_at,
            )
        )
        if result.delivered:
            try:
                committed = self._claims.mark_delivered(
                    claim,
                    delivered_at=self._now(),
                    reason=result.reason,
                )
            except Exception:
                committed = False
            return SchedulerRunResult(
                True,
                committed,
                result.reason if committed else "delivery_commit_lost",
                reminder.reminder_id,
                claim.attempt_count,
            )
        return self._retry_or_exhaust(claim, now=self._now(), reason=result.reason)

    def _retry_or_exhaust(
        self,
        claim: ReminderDeliveryClaim,
        *,
        now: datetime,
        reason: str,
    ) -> SchedulerRunResult:
        reason = _require_reason(reason)
        reminder_id = claim.reminder.reminder_id
        if claim.attempt_count >= MAX_ATTEMPTS:
            try:
                committed = self._claims.mark_exhausted(claim, reason=reason)
            except Exception:
                committed = False
            return SchedulerRunResult(
                True,
                False,
                "delivery_exhausted" if committed else "claim_commit_lost",
                reminder_id,
                claim.attempt_count,
            )

        retry_at = now + _retry_delay(claim.attempt_count)
        try:
            committed = self._claims.mark_retry(
                claim,
                next_attempt_at=retry_at,
                reason=reason,
            )
        except Exception:
            committed = False
        return SchedulerRunResult(
            True,
            False,
            reason if committed else "claim_commit_lost",
            reminder_id,
            claim.attempt_count,
        )

    def _now(self) -> datetime:
        try:
            now = self._clock.now()
        except Exception as error:
            raise RuntimeError("reminder scheduler clock unavailable") from error
        if not _aware(now):
            raise RuntimeError("reminder scheduler clock returned naive time")
        return now


def _retry_delay(attempt_count: int) -> timedelta:
    multiplier = 2 ** max(0, min(attempt_count - 1, 16))
    delay = BASE_RETRY * multiplier
    return min(delay, MAX_RETRY)


def _require_uuid(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} is invalid")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ValueError(f"{name} is invalid") from error
    if str(parsed) != value:
        raise ValueError(f"{name} is invalid")
    return value


def _require_identifier(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 128
        or "\x00" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(f"{name} is invalid")
    return value


def _require_reason(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 128 or "\x00" in value:
        return "delivery_failed"
    return value


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
