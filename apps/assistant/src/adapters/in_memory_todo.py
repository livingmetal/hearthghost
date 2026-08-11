"""In-memory todo repository for tests and default fail-small composition."""

from __future__ import annotations

from apps.assistant.src.modules.todo import TodoRecord


class InMemoryTodoRepository:
    def __init__(self) -> None:
        self._records: dict[str, TodoRecord] = {}

    def put(self, record: object) -> None:
        if not isinstance(record, TodoRecord):
            raise TypeError("todo repository accepts TodoRecord only")
        if record.todo_id in self._records:
            raise ValueError("todo already exists")
        self._records[record.todo_id] = record

    def get(self, todo_id: str) -> TodoRecord | None:
        return self._records.get(todo_id)

    def list_scope(self, scope: str, scope_id: str, *, limit: int) -> tuple[TodoRecord, ...]:
        records = [
            record for record in self._records.values()
            if record.scope.value == scope and record.scope_id == scope_id
        ]
        records.sort(key=lambda item: (item.created_at, item.todo_id), reverse=True)
        return tuple(records[:limit])

    def replace(self, record: object) -> None:
        if not isinstance(record, TodoRecord):
            raise TypeError("todo repository accepts TodoRecord only")
        if record.todo_id not in self._records:
            raise ValueError("todo does not exist")
        self._records[record.todo_id] = record

    def delete(self, todo_id: str) -> bool:
        return self._records.pop(todo_id, None) is not None
