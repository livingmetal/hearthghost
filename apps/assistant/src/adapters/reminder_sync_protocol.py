"""Redacted reminder schedule sync over an authenticated notification-capable Node channel."""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from apps.assistant.src.adapters.node_gateway_protocol import (
    CONTRACT_VERSION,
    MAX_SEQUENCE,
    NodeProtocolError,
    read_frame,
    write_frame,
)
from apps.assistant.src.modules.conversation_principal import ConversationPrincipalResolver
from apps.assistant.src.modules.notification_delivery import NOTIFICATION_CAPABILITY
from apps.assistant.src.modules.reminder import ReminderManager, ReminderState
from apps.assistant.src.modules.node_security import IDENTIFIER_PATTERN, CapabilityRequest
from apps.assistant.src.ports.node_gateway import Clock, NodeGatewaySecurityBoundary
from apps.assistant.src.ports.notification_target import NotificationTargetResolver


MAX_SYNC_REMINDERS = 100


@dataclass(frozen=True)
class ReminderSyncCommand:
    request_id: str
    node_session_id: str
    sequence: int


@dataclass(frozen=True)
class ReminderSyncResult:
    request_id: str
    accepted: bool
    reason_code: str
    node_session_id: str | None = None
    schedules: tuple[dict[str, str], ...] = ()

    def to_document(self) -> dict[str, object]:
        document: dict[str, object] = {
            "contract_version": CONTRACT_VERSION,
            "message_type": "reminder.sync.result",
            "request_id": self.request_id,
            "outcome": "accepted" if self.accepted else "denied",
            "reason_code": self.reason_code,
        }
        if self.node_session_id is not None:
            document["node_session_id"] = self.node_session_id
        if self.accepted:
            document["schedules"] = list(self.schedules)
        return document


class ReminderSyncProtocol:
    def __init__(
        self,
        *,
        gateway: NodeGatewaySecurityBoundary,
        reminders: ReminderManager,
        principals: ConversationPrincipalResolver,
        targets: NotificationTargetResolver,
        clock: Clock,
    ) -> None:
        self._gateway = gateway
        self._reminders = reminders
        self._principals = principals
        self._targets = targets
        self._clock = clock

    def handle_document(self, channel: ssl.SSLSocket, document: object) -> ReminderSyncResult:
        if not isinstance(channel, ssl.SSLSocket):
            raise NodeProtocolError("Reminder sync requires an authenticated TLS channel")
        command = parse_reminder_sync_command(document)
        admission = self._gateway.admit_request(
            channel,
            CapabilityRequest(
                request_id=command.request_id,
                session_id=command.node_session_id,
                sequence=command.sequence,
                capability=NOTIFICATION_CAPABILITY,
            ),
        )
        if not admission.admitted or admission.node_id is None:
            result = ReminderSyncResult(command.request_id, False, admission.reason.value)
        else:
            result = self._sync(admission.node_id, command)
        write_frame(channel, result.to_document())
        return result

    def _sync(self, node_id: str, command: ReminderSyncCommand) -> ReminderSyncResult:
        try:
            principal = self._principals.resolve(node_id)
        except Exception:
            return ReminderSyncResult(command.request_id, False, "principal_resolution_failed")
        if principal is None:
            return ReminderSyncResult(command.request_id, False, "principal_unresolved")
        try:
            target = self._targets.resolve(principal.scope.value, principal.scope_id)
        except Exception:
            return ReminderSyncResult(command.request_id, False, "notification_target_unavailable")
        if target != node_id:
            return ReminderSyncResult(command.request_id, False, "notification_target_mismatch")
        try:
            now = self._clock.now()
        except Exception:
            return ReminderSyncResult(command.request_id, False, "clock_unavailable")
        if not _aware(now):
            return ReminderSyncResult(command.request_id, False, "clock_invalid")
        try:
            records = self._reminders.list_scope(
                principal.scope,
                principal.scope_id,
                limit=MAX_SYNC_REMINDERS,
            )
        except Exception:
            return ReminderSyncResult(command.request_id, False, "reminder_repository_unavailable")
        schedules = tuple(
            {
                "reminder_id": record.reminder_id,
                "fire_at": record.fire_at.isoformat(),
            }
            for record in records
            if record.state is ReminderState.SCHEDULED and record.fire_at > now
        )
        return ReminderSyncResult(
            command.request_id,
            True,
            "reminder_sync_ready",
            node_session_id=command.node_session_id,
            schedules=schedules,
        )


def parse_reminder_sync_command(document: object) -> ReminderSyncCommand:
    if not isinstance(document, dict) or set(document) != {
        "contract_version",
        "message_type",
        "request_id",
        "node_session_id",
        "sequence",
    }:
        raise NodeProtocolError("Reminder sync fields are invalid")
    request_id = document.get("request_id")
    node_session_id = document.get("node_session_id")
    sequence = document.get("sequence")
    if (
        document.get("contract_version") != CONTRACT_VERSION
        or document.get("message_type") != "reminder.sync"
        or not _valid_uuid(request_id)
        or not isinstance(node_session_id, str)
        or IDENTIFIER_PATTERN.fullmatch(node_session_id) is None
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not 1 <= sequence <= MAX_SEQUENCE
    ):
        raise NodeProtocolError("Reminder sync command is invalid")
    return ReminderSyncCommand(request_id, node_session_id, sequence)


def _valid_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
