"""In-memory ReminderRepository for tests and non-persistent development."""

from __future__ import annotations

from apps.assistant.src.modules.reminder import ReminderRecord, ReminderState


class InMemoryReminderRepository:
    def __init__(self) -> None:
        self._records: dict[str, ReminderRecord] = {}

    def put(self, record: object) -> None:
        if not isinstance(record, ReminderRecord):
            raise TypeError("reminder repository accepts ReminderRecord only")
        if record.reminder_id in self._records:
            raise ValueError("reminder already exists")
        self._records[record.reminder_id] = record

    def get(self, reminder_id: str) -> ReminderRecord | None:
        return self._records.get(reminder_id)

    def find_active_for_todo(self, scope: str, scope_id: str, todo_id: str) -> ReminderRecord | None:
        matches = [
            record
            for record in self._records.values()
            if record.scope.value == scope
            and record.scope_id == scope_id
            and record.todo_id == todo_id
            and record.state is ReminderState.SCHEDULED
        ]
        if len(matches) > 1:
            raise RuntimeError("multiple active reminders exist for one todo")
        return matches[0] if matches else None

    def list_scope(self, scope: str, scope_id: str, *, limit: int) -> tuple[ReminderRecord, ...]:
        records = [
            record
            for record in self._records.values()
            if record.scope.value == scope and record.scope_id == scope_id
        ]
        records.sort(key=lambda record: (record.created_at, record.reminder_id), reverse=True)
        return tuple(records[:limit])

    def replace(self, record: object) -> None:
        if not isinstance(record, ReminderRecord):
            raise TypeError("reminder repository accepts ReminderRecord only")
        if record.reminder_id not in self._records:
            raise KeyError("reminder does not exist")
        self._records[record.reminder_id] = record

    def delete(self, reminder_id: str) -> bool:
        return self._records.pop(reminder_id, None) is not None
