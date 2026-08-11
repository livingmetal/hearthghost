"""Explicit, scoped todo domain boundary.

Todos are deliberate user/household records. A due time is metadata only: it
never grants reminder, notification, calendar, or automation authority.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from apps.assistant.src.modules.memory import MemoryScope
from apps.assistant.src.ports.node_gateway import Clock
from apps.assistant.src.ports.todo import TodoRepository


MAX_TODO_TEXT_LENGTH = 1_000
MAX_TODO_RETRIEVAL = 100


class TodoState(str, Enum):
    OPEN = "open"
    COMPLETED = "completed"


@dataclass(frozen=True)
class TodoRecord:
    todo_id: str
    scope: MemoryScope
    scope_id: str
    text: str
    state: TodoState
    created_at: datetime
    due_at: datetime | None = None
    completed_at: datetime | None = None


class TodoManager:
    def __init__(self, *, repository: TodoRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def create(
        self,
        *,
        scope: MemoryScope,
        scope_id: str,
        text: str,
        due_at: datetime | None = None,
    ) -> TodoRecord:
        _validate_scope(scope, scope_id)
        normalized = _validate_text(text)
        _validate_optional_due_at(due_at)
        record = TodoRecord(
            todo_id=str(uuid4()),
            scope=scope,
            scope_id=scope_id,
            text=normalized,
            state=TodoState.OPEN,
            created_at=self._now(),
            due_at=due_at,
        )
        try:
            self._repository.put(record)
        except Exception as error:
            raise RuntimeError("todo repository unavailable") from error
        return record

    def list_scope(self, scope: MemoryScope, scope_id: str, *, limit: int = 50) -> tuple[TodoRecord, ...]:
        _validate_scope(scope, scope_id)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_TODO_RETRIEVAL:
            raise ValueError("todo retrieval limit must be 1 to 100")
        try:
            records = self._repository.list_scope(scope.value, scope_id, limit=limit)
        except Exception as error:
            raise RuntimeError("todo repository unavailable") from error
        if any(not _valid_scoped_record(record, scope, scope_id) for record in records):
            raise RuntimeError("todo repository returned invalid scope data")
        return records

    def complete(self, todo_id: str, *, scope: MemoryScope, scope_id: str) -> TodoRecord | None:
        _validate_scope(scope, scope_id)
        _validate_todo_id(todo_id)
        try:
            current = self._repository.get(todo_id)
        except Exception as error:
            raise RuntimeError("todo repository unavailable") from error
        if current is None:
            return None
        if not _valid_scoped_record(current, scope, scope_id):
            return None
        if current.state is TodoState.COMPLETED:
            return current
        completed = replace(current, state=TodoState.COMPLETED, completed_at=self._now())
        try:
            self._repository.replace(completed)
        except Exception as error:
            raise RuntimeError("todo repository unavailable") from error
        return completed

    def delete(self, todo_id: str, *, scope: MemoryScope, scope_id: str) -> bool:
        _validate_scope(scope, scope_id)
        _validate_todo_id(todo_id)
        try:
            current = self._repository.get(todo_id)
        except Exception as error:
            raise RuntimeError("todo repository unavailable") from error
        if current is None or not _valid_scoped_record(current, scope, scope_id):
            return False
        try:
            return self._repository.delete(todo_id)
        except Exception as error:
            raise RuntimeError("todo repository unavailable") from error

    def _now(self) -> datetime:
        try:
            now = self._clock.now()
        except Exception as error:
            raise RuntimeError("todo clock unavailable") from error
        if not _is_aware_datetime(now):
            raise RuntimeError("todo clock returned naive time")
        return now


def _valid_scoped_record(record: object, scope: MemoryScope, scope_id: str) -> bool:
    if not isinstance(record, TodoRecord) or record.scope is not scope or record.scope_id != scope_id:
        return False
    if not _is_aware_datetime(record.created_at):
        return False
    if record.due_at is not None and not _is_aware_datetime(record.due_at):
        return False
    if record.completed_at is not None and not _is_aware_datetime(record.completed_at):
        return False
    return (record.state is TodoState.OPEN) == (record.completed_at is None)


def _validate_scope(scope: object, scope_id: object) -> None:
    if not isinstance(scope, MemoryScope):
        raise ValueError("todo scope is invalid")
    if not isinstance(scope_id, str) or not scope_id or len(scope_id) > 128:
        raise ValueError("todo scope_id is invalid")


def _validate_text(text: object) -> str:
    if (
        not isinstance(text, str)
        or not text.strip()
        or len(text) > MAX_TODO_TEXT_LENGTH
        or "\x00" in text
        or any(ord(ch) < 32 and ch not in "\n\t" for ch in text)
    ):
        raise ValueError("todo text is invalid")
    return text.strip()


def _validate_optional_due_at(due_at: object) -> None:
    if due_at is not None and not _is_aware_datetime(due_at):
        raise ValueError("todo due_at must include a timezone")


def _is_aware_datetime(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _validate_todo_id(todo_id: object) -> None:
    if not isinstance(todo_id, str):
        raise ValueError("todo_id is invalid")
    try:
        parsed = UUID(todo_id)
    except ValueError as error:
        raise ValueError("todo_id is invalid") from error
    if str(parsed) != todo_id:
        raise ValueError("todo_id is invalid")
