from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from apps.assistant.src.adapters.node_gateway_protocol import NodeProtocolError
from apps.assistant.src.adapters.reminder_sync_protocol import (
    ReminderSyncCommand,
    ReminderSyncProtocol,
    parse_reminder_sync_command,
)
from apps.assistant.src.modules.conversation_principal import (
    ConversationPrincipal,
    DenyingConversationPrincipalResolver,
    PrincipalAssurance,
    StaticConversationPrincipalResolver,
)
from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.reminder import ReminderRecord, ReminderSource, ReminderState
from apps.assistant.src.modules.notification_target import StaticNotificationTargetResolver


NOW = datetime(2026, 8, 11, 13, tzinfo=timezone.utc)
NODE_ID = "android-personal-01"


class Clock:
    def now(self):
        return NOW


class Reminders:
    def __init__(self, records=()):
        self.records = tuple(records)
        self.calls = []

    def list_scope(self, scope, scope_id, *, limit):
        self.calls.append((scope, scope_id, limit))
        return self.records


class ReminderSyncProtocolTests(unittest.TestCase):
    def principal_resolver(self):
        principal = ConversationPrincipal(
            scope=MemoryScope.USER,
            scope_id="owner",
            assurance=PrincipalAssurance.PERSONAL_NODE_BINDING,
            source_node_id=NODE_ID,
        )
        return StaticConversationPrincipalResolver({NODE_ID: principal})

    def record(self, reminder_id, *, fire_at, state=ReminderState.SCHEDULED):
        return ReminderRecord(
            reminder_id=reminder_id,
            scope=MemoryScope.USER,
            scope_id="owner",
            todo_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            fire_at=fire_at,
            source=ReminderSource.TODO_DUE,
            created_by_node_id="creator-node",
            created_at=NOW - timedelta(days=1),
            state=state,
            cancelled_at=NOW if state is ReminderState.CANCELLED else None,
        )

    def protocol(self, reminders, *, principals=None, targets=None):
        return ReminderSyncProtocol(
            gateway=object(),
            reminders=reminders,
            principals=principals or self.principal_resolver(),
            targets=targets or StaticNotificationTargetResolver({(MemoryScope.USER, "owner"): NODE_ID}),
            clock=Clock(),
        )

    def test_parser_requires_exact_bounded_notification_sync_shape(self):
        command = parse_reminder_sync_command(
            {
                "contract_version": "1.0",
                "message_type": "reminder.sync",
                "request_id": "11111111-1111-4111-8111-111111111111",
                "node_session_id": "node-session-1",
                "sequence": 2,
            }
        )
        self.assertEqual(command.node_session_id, "node-session-1")
        self.assertEqual(command.sequence, 2)
        with self.assertRaises(NodeProtocolError):
            parse_reminder_sync_command(
                {
                    "contract_version": "1.0",
                    "message_type": "reminder.sync",
                    "request_id": "11111111-1111-4111-8111-111111111111",
                    "node_session_id": "node-session-1",
                    "sequence": 2,
                    "todo_text": "must never cross",
                }
            )

    def test_sync_returns_only_future_scheduled_redacted_identity(self):
        future = self.record(
            "22222222-2222-4222-8222-222222222222",
            fire_at=NOW + timedelta(hours=1),
        )
        past = self.record(
            "33333333-3333-4333-8333-333333333333",
            fire_at=NOW - timedelta(seconds=1),
        )
        cancelled = self.record(
            "44444444-4444-4444-8444-444444444444",
            fire_at=NOW + timedelta(hours=2),
            state=ReminderState.CANCELLED,
        )
        reminders = Reminders((future, past, cancelled))
        result = self.protocol(reminders)._sync(
            NODE_ID,
            ReminderSyncCommand("55555555-5555-4555-8555-555555555555", "node-session-1", 2),
        )
        self.assertTrue(result.accepted)
        self.assertEqual(
            result.schedules,
            ({"reminder_id": future.reminder_id, "fire_at": future.fire_at.isoformat()},),
        )
        self.assertEqual(set(result.schedules[0]), {"reminder_id", "fire_at"})
        self.assertNotIn("todo", result.to_document()["schedules"][0])
        self.assertEqual(reminders.calls, [(MemoryScope.USER, "owner", 100)])

    def test_unbound_node_is_denied_before_reminder_repository(self):
        reminders = Reminders()
        result = self.protocol(
            reminders,
            principals=DenyingConversationPrincipalResolver(),
        )._sync(
            NODE_ID,
            ReminderSyncCommand("55555555-5555-4555-8555-555555555555", "node-session-1", 2),
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason_code, "principal_unresolved")
        self.assertEqual(reminders.calls, [])

    def test_route_must_point_back_to_requesting_authenticated_node(self):
        reminders = Reminders()
        wrong = StaticNotificationTargetResolver({(MemoryScope.USER, "owner"): "android-other-01"})
        result = self.protocol(reminders, targets=wrong)._sync(
            NODE_ID,
            ReminderSyncCommand("55555555-5555-4555-8555-555555555555", "node-session-1", 2),
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason_code, "notification_target_mismatch")
        self.assertEqual(reminders.calls, [])


if __name__ == "__main__":
    unittest.main()
