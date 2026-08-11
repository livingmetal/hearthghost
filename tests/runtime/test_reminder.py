from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from apps.assistant.src.adapters.in_memory_reminder import InMemoryReminderRepository
from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.reminder import ReminderManager, ReminderState
from apps.assistant.src.modules.todo import TodoRecord, TodoState


NOW = datetime(2026, 8, 11, tzinfo=timezone.utc)


class Clock:
    def now(self):
        return NOW


class ReminderTests(unittest.TestCase):
    def build(self):
        repository = InMemoryReminderRepository()
        return ReminderManager(repository=repository, clock=Clock()), repository

    def todo(self, *, due_at=NOW + timedelta(hours=2), scope=MemoryScope.USER, scope_id="owner"):
        return TodoRecord(
            todo_id="11111111-1111-1111-1111-111111111111",
            scope=scope,
            scope_id=scope_id,
            text="DB 백업 확인",
            state=TodoState.OPEN,
            created_at=NOW,
            due_at=due_at,
        )

    def test_explicit_future_todo_due_can_be_scheduled_idempotently(self):
        manager, repository = self.build()
        todo = self.todo()
        first = manager.schedule_for_todo(
            todo,
            created_by_node_id="android-personal-01",
            explicit_user_request=True,
        )
        second = manager.schedule_for_todo(
            todo,
            created_by_node_id="android-personal-01",
            explicit_user_request=True,
        )
        self.assertEqual(first.reminder_id, second.reminder_id)
        self.assertEqual(first.fire_at, todo.due_at)
        self.assertEqual(first.state, ReminderState.SCHEDULED)
        self.assertEqual(len(repository.list_scope("user", "owner", limit=10)), 1)

    def test_implicit_past_missing_due_completed_and_far_future_requests_are_rejected(self):
        manager, _ = self.build()
        with self.assertRaisesRegex(ValueError, "explicit"):
            manager.schedule_for_todo(
                self.todo(), created_by_node_id="android-personal-01", explicit_user_request=False
            )
        for todo in (
            self.todo(due_at=None),
            self.todo(due_at=NOW - timedelta(seconds=1)),
            self.todo(due_at=NOW + timedelta(days=367)),
            TodoRecord(
                todo_id="11111111-1111-1111-1111-111111111111",
                scope=MemoryScope.USER,
                scope_id="owner",
                text="이미 완료",
                state=TodoState.COMPLETED,
                created_at=NOW,
                due_at=NOW + timedelta(hours=1),
                completed_at=NOW,
            ),
        ):
            with self.subTest(todo=todo), self.assertRaises(ValueError):
                manager.schedule_for_todo(
                    todo, created_by_node_id="android-personal-01", explicit_user_request=True
                )

    def test_due_change_reschedules_existing_reminder_without_creating_another(self):
        manager, repository = self.build()
        todo = self.todo()
        scheduled = manager.schedule_for_todo(
            todo, created_by_node_id="android-personal-01", explicit_user_request=True
        )
        changed = replace(todo, due_at=NOW + timedelta(hours=5))
        synced = manager.synchronize_for_todo(changed)
        self.assertEqual(synced.reminder_id, scheduled.reminder_id)
        self.assertEqual(synced.fire_at, changed.due_at)
        self.assertEqual(len(repository.list_scope("user", "owner", limit=10)), 1)

    def test_due_clear_completion_past_or_out_of_horizon_cancels_existing_reminder(self):
        variants = (
            self.todo(due_at=None),
            self.todo(due_at=NOW - timedelta(seconds=1)),
            self.todo(due_at=NOW + timedelta(days=367)),
            TodoRecord(
                todo_id="11111111-1111-1111-1111-111111111111",
                scope=MemoryScope.USER,
                scope_id="owner",
                text="완료됨",
                state=TodoState.COMPLETED,
                created_at=NOW,
                due_at=NOW + timedelta(hours=3),
                completed_at=NOW,
            ),
        )
        for changed in variants:
            with self.subTest(changed=changed):
                manager, _ = self.build()
                manager.schedule_for_todo(
                    self.todo(), created_by_node_id="android-personal-01", explicit_user_request=True
                )
                synced = manager.synchronize_for_todo(changed)
                self.assertEqual(synced.state, ReminderState.CANCELLED)
                self.assertEqual(synced.cancelled_at, NOW)

    def test_cancel_is_scope_bound_and_idempotent(self):
        manager, _ = self.build()
        scheduled = manager.schedule_for_todo(
            self.todo(), created_by_node_id="android-personal-01", explicit_user_request=True
        )
        self.assertIsNone(
            manager.cancel(
                scheduled.reminder_id,
                scope=MemoryScope.HOUSEHOLD,
                scope_id="home",
            )
        )
        cancelled = manager.cancel(
            scheduled.reminder_id,
            scope=MemoryScope.USER,
            scope_id="owner",
        )
        self.assertEqual(cancelled.state, ReminderState.CANCELLED)
        self.assertEqual(cancelled.cancelled_at, NOW)
        repeated = manager.cancel(
            scheduled.reminder_id,
            scope=MemoryScope.USER,
            scope_id="owner",
        )
        self.assertEqual(repeated, cancelled)

    def test_scope_list_never_returns_another_principal(self):
        manager, _ = self.build()
        manager.schedule_for_todo(
            self.todo(scope=MemoryScope.USER, scope_id="owner"),
            created_by_node_id="android-personal-01",
            explicit_user_request=True,
        )
        self.assertEqual(len(manager.list_scope(MemoryScope.USER, "owner")), 1)
        self.assertEqual(manager.list_scope(MemoryScope.USER, "other"), ())


if __name__ == "__main__":
    unittest.main()
