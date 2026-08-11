"""Fail-closed boundary for future local reminder notification delivery.

This module does not choose a target Node, poll the database, open a network
connection, or display an Android notification. It only proves that a future
delivery attempt must pass Policy plus authoritative Node capability state and
confirmed Node-local authorization before delivery may be reported successful.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from apps.assistant.src.modules.node_security import NodeRecord, NodeTrustState
from apps.assistant.src.ports.llm import ProposedAction
from apps.assistant.src.ports.node_gateway import NodeRepository
from apps.assistant.src.ports.policy import PolicyBoundary
from apps.assistant.src.ports.reminder import ReminderDeliveryPort


NOTIFICATION_CAPABILITY = "notification.local"
REDACTED_TITLE = "HearthGhost"
REDACTED_BODY = "Reminder"


@dataclass(frozen=True)
class NotificationDeliveryIntent:
    reminder_id: str
    target_node_id: str
    fire_at: datetime

    def __post_init__(self) -> None:
        _validate_uuid(self.reminder_id)
        if not isinstance(self.target_node_id, str) or not self.target_node_id or len(self.target_node_id) > 128:
            raise ValueError("notification target_node_id is invalid")
        if not _aware(self.fire_at):
            raise ValueError("notification fire_at must be timezone-aware")


@dataclass(frozen=True)
class NotificationAdapterRequest:
    reminder_id: str
    target_node_id: str
    fire_at: datetime
    title: str = REDACTED_TITLE
    body: str = REDACTED_BODY
    content_mode: str = "redacted"
    local_authorization_required: bool = True

    def __post_init__(self) -> None:
        _validate_uuid(self.reminder_id)
        if not isinstance(self.target_node_id, str) or not self.target_node_id or len(self.target_node_id) > 128:
            raise ValueError("notification target_node_id is invalid")
        if not _aware(self.fire_at):
            raise ValueError("notification fire_at must be timezone-aware")
        if self.content_mode != "redacted" or self.local_authorization_required is not True:
            raise ValueError("notification adapter request weakens privacy or local authorization")
        if self.title != REDACTED_TITLE or self.body != REDACTED_BODY:
            raise ValueError("notification adapter request must remain redacted")


@dataclass(frozen=True)
class NotificationAdapterResult:
    delivered: bool
    reason: str
    local_authorization_confirmed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.delivered, bool) or not isinstance(self.local_authorization_confirmed, bool):
            raise ValueError("notification adapter result is invalid")
        if not isinstance(self.reason, str) or not self.reason or len(self.reason) > 128:
            raise ValueError("notification adapter reason is invalid")
        if self.delivered and not self.local_authorization_confirmed:
            raise ValueError("delivered notification requires confirmed local authorization")


@dataclass(frozen=True)
class NotificationDeliveryResult:
    delivered: bool
    reason: str


class NotificationDeliveryService:
    """Require Policy and Node authority before invoking any delivery adapter."""

    def __init__(
        self,
        *,
        policy: PolicyBoundary,
        nodes: NodeRepository,
        delivery: ReminderDeliveryPort,
    ) -> None:
        self._policy = policy
        self._nodes = nodes
        self._delivery = delivery

    def deliver(self, intent: NotificationDeliveryIntent) -> NotificationDeliveryResult:
        if not isinstance(intent, NotificationDeliveryIntent):
            raise TypeError("notification intent is invalid")
        proposal = ProposedAction(
            NOTIFICATION_CAPABILITY,
            {
                "target_node_id": intent.target_node_id,
                "reminder_id": intent.reminder_id,
                "fire_at": intent.fire_at.isoformat(),
                "content_mode": "redacted",
            },
        )
        try:
            policy = self._policy.evaluate(proposal)
        except Exception:
            return NotificationDeliveryResult(False, "policy_unavailable")
        if not getattr(policy, "allowed", False):
            return NotificationDeliveryResult(False, getattr(policy, "reason_code", "policy_denied"))

        try:
            node = self._nodes.get(intent.target_node_id)
        except Exception:
            return NotificationDeliveryResult(False, "node_state_unavailable")
        node_reason = _node_authority_reason(node)
        if node_reason is not None:
            return NotificationDeliveryResult(False, node_reason)

        request = NotificationAdapterRequest(
            reminder_id=intent.reminder_id,
            target_node_id=intent.target_node_id,
            fire_at=intent.fire_at,
        )
        try:
            result = self._delivery.deliver(request)
        except Exception:
            return NotificationDeliveryResult(False, "delivery_adapter_unavailable")
        if not isinstance(result, NotificationAdapterResult):
            return NotificationDeliveryResult(False, "delivery_adapter_invalid_result")
        if result.delivered and not result.local_authorization_confirmed:
            return NotificationDeliveryResult(False, "local_authorization_not_confirmed")
        return NotificationDeliveryResult(result.delivered, result.reason)


def _node_authority_reason(node: object) -> str | None:
    if not isinstance(node, NodeRecord):
        return "notification_node_unknown"
    if node.trust_state is not NodeTrustState.TRUSTED:
        return "notification_node_not_trusted"
    advertisements = [item for item in node.advertised_capabilities if item.name == NOTIFICATION_CAPABILITY]
    if len(advertisements) != 1:
        return "notification_capability_not_advertised"
    if advertisements[0].local_authorization_required is not True:
        return "notification_local_authorization_not_required"
    if NOTIFICATION_CAPABILITY not in node.granted_capabilities:
        return "notification_capability_not_granted"
    return None


def _validate_uuid(value: object) -> None:
    if not isinstance(value, str):
        raise ValueError("notification reminder_id is invalid")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ValueError("notification reminder_id is invalid") from error
    if str(parsed) != value:
        raise ValueError("notification reminder_id is invalid")


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
