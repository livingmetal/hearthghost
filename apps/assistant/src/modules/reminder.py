"""Explicit reminder scheduling domain.

A reminder record represents an authorized request to remember a future instant.
It is not permission to display a notification. Delivery remains behind a
separate ReminderDeliveryPort and Node/local authorization boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4

from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.modules.todo import TodoRecord, TodoState
from apps.assistant.src.ports.node_gateway import Clock
from apps.assistant.src.ports.reminder import ReminderRepository


MAX_REMINDER_RETRIEVAL = 100
MAX_REMINDER_HORIZON = timedelta(days=366)


class ReminderState(str, Enum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


class ReminderSource(str, Enum):
    TODO_DUE = "todo_due"


@dataclass(frozen=True)
class ReminderRecord:
    reminder_id: str
    scope: MemoryScope
    scope_id: str
    todo_id: str
    fire_at: datetime
    source: ReminderSource
    created_by_node_id: str
    created_at: datetime
    state: ReminderState = ReminderState.SCHEDULED
    cancelled_at: datetime | None = None


class ReminderManager:
    def __init__(self, *, repository: ReminderRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def schedule_for_todo(
        self,
        todo: TodoRecord,
        *,
        created_by_node_id: str,
        explicit_user_request: bool,
    ) -> ReminderRecord:
        if not explicit_user_request:
            raise ValueError("reminders require an explicit user request")
        _validate_schedulable_todo(todo, now=self._now())
        if not isinstance(created_by_node_id, str) or not created_by_node_id or len(created_by_node_id) > 128:
            raise ValueError("reminder origin node is invalid")

        existing = self._find_active(todo)
        if existing is not None:
            if existing.fire_at != todo.due_at:
                existing = replace(existing, fire_at=todo.due_at)
                self._replace(existing)
            return existing

        record = ReminderRecord(
            reminder_id=str(uuid4()),
            scope=todo.scope,
            scope_id=todo.scope_id,
            todo_id=todo.todo_id,
            fire_at=todo.due_at,
            source=ReminderSource.TODO_DUE,
            created_by_node_id=created_by_node_id,
            created_at=self._now(),
        )
        try:
            self._repository.put(record)
        except Exception as error:
            raise RuntimeError("reminder repository unavailable") from error
        return record

    def synchronize_for_todo(self, todo: TodoRecord) -> ReminderRecord | None:
        """Keep an existing TODO-due reminder aligned with the TODO lifecycle.

        No new reminder is created here. If the TODO becomes unschedulable, the
        existing reminder is cancelled rather than left at a stale timestamp.
        """
        if not isinstance(todo, TodoRecord):
            raise TypeError("todo is invalid")
        existing = self._find_active(todo)
        if existing is None:
            return None
        now = self._now()
        if (
            todo.state is not TodoState.OPEN
            or todo.due_at is None
            or todo.due_at <= now
            or todo.due_at - now > MAX_REMINDER_HORIZON
        ):
            return self.cancel(existing.reminder_id, scope=todo.scope, scope_id=todo.scope_id)
        if existing.fire_at == todo.due_at:
            return existing
        updated = replace(existing, fire_at=todo.due_at)
        self._replace(updated)
        return updated

    def cancel_for_todo(self, todo: TodoRecord) -> ReminderRecord | None:
        if not isinstance(todo, TodoRecord):
            raise TypeError("todo is invalid")
        existing = self._find_active(todo)
        if existing is None:
            return None
        return self.cancel(existing.reminder_id, scope=todo.scope, scope_id=todo.scope_id)

    def get(self, reminder_id: str, *, scope: MemoryScope, scope_id: str) -> ReminderRecord | None:
        _validate_scope(scope, scope_id)
        _validate_uuid(reminder_id, "reminder_id")
        try:
            record = self._repository.get(reminder_id)
        except Exception as error:
            raise RuntimeError("reminder repository unavailable") from error
        if record is None or not _valid_scoped_record(record, scope, scope_id):
            return None
        return record

    def list_scope(self, scope: MemoryScope, scope_id: str, *, limit: int = 50) -> tuple[ReminderRecord, ...]:
        _validate_scope(scope, scope_id)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_REMINDER_RETRIEVAL:
            raise ValueError("reminder retrieval limit must be 1 to 100")
        try:
            records = self._repository.list_scope(scope.value, scope_id, limit=limit)
        except Exception as error:
            raise RuntimeError("reminder repository unavailable") from error
        if any(not _valid_scoped_record(record, scope, scope_id) for record in records):
            raise RuntimeError("reminder repository returned invalid scope data")
        return records

    def cancel(self, reminder_id: str, *, scope: MemoryScope, scope_id: str) -> ReminderRecord | None:
        current = self.get(reminder_id, scope=scope, scope_id=scope_id)
        if current is None:
            return None
        if current.state is ReminderState.CANCELLED:
            return current
        cancelled = replace(current, state=ReminderState.CANCELLED, cancelled_at=self._now())
        self._replace(cancelled)
        return cancelled

    def _find_active(self, todo: TodoRecord) -> ReminderRecord | None:
        try:
            record = self._repository.find_active_for_todo(todo.scope.value, todo.scope_id, todo.todo_id)
        except Exception as error:
            raise RuntimeError("reminder repository unavailable") from error
        if record is not None and not _valid_scoped_record(record, todo.scope, todo.scope_id):
            raise RuntimeError("reminder repository returned invalid scope data")
        return record

    def _replace(self, record: ReminderRecord) -> None:
        try:
            self._repository.replace(record)
        except Exception as error:
            raise RuntimeError("reminder repository unavailable") from error

    def _now(self) -> datetime:
        try:
            now = self._clock.now()
        except Exception as error:
            raise RuntimeError("reminder clock unavailable") from error
        if not _aware(now):
            raise RuntimeError("reminder clock returned naive time")
        return now


def _validate_schedulable_todo(todo: object, *, now: datetime) -> None:
    if not isinstance(todo, TodoRecord) or todo.state is not TodoState.OPEN or todo.due_at is None:
        raise ValueError("reminder requires an open todo with due_at")
    if todo.due_at <= now:
        raise ValueError("reminder fire_at must be in the future")
    if todo.due_at - now > MAX_REMINDER_HORIZON:
        raise ValueError("reminder fire_at exceeds the scheduling horizon")


def _valid_scoped_record(record: object, scope: MemoryScope, scope_id: str) -> bool:
    if not isinstance(record, ReminderRecord) or record.scope is not scope or record.scope_id != scope_id:
        return False
    try:
        _validate_uuid(record.reminder_id, "reminder_id")
        _validate_uuid(record.todo_id, "todo_id")
    except ValueError:
        return False
    if not _aware(record.fire_at) or not _aware(record.created_at):
        return False
    if record.cancelled_at is not None and not _aware(record.cancelled_at):
        return False
    return (record.state is ReminderState.SCHEDULED) == (record.cancelled_at is None)


def _validate_scope(scope: object, scope_id: object) -> None:
    if not isinstance(scope, MemoryScope):
        raise ValueError("reminder scope is invalid")
    if not isinstance(scope_id, str) or not scope_id or len(scope_id) > 128:
        raise ValueError("reminder scope_id is invalid")


def _validate_uuid(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{name} is invalid")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ValueError(f"{name} is invalid") from error
    if str(parsed) != value:
        raise ValueError(f"{name} is invalid")


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
