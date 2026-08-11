"""Deterministic in-memory repository for memory tests and development."""

from __future__ import annotations

from threading import RLock

from apps.assistant.src.modules.memory import MemoryRecord


class InMemoryMemoryRepository:
    def __init__(self) -> None:
        self._records: dict[str, MemoryRecord] = {}
        self._lock = RLock()

    def put(self, record: object) -> None:
        if not isinstance(record, MemoryRecord):
            raise TypeError("memory repository accepts MemoryRecord only")
        with self._lock:
            if record.memory_id in self._records:
                raise ValueError("memory_id already exists")
            self._records[record.memory_id] = record

    def get(self, memory_id: str) -> MemoryRecord | None:
        with self._lock:
            return self._records.get(memory_id)

    def list_scope(self, scope: str, scope_id: str, *, limit: int) -> tuple[MemoryRecord, ...]:
        with self._lock:
            matching = [
                record
                for record in self._records.values()
                if record.scope.value == scope and record.scope_id == scope_id
            ]
        matching.sort(key=lambda record: (record.created_at, record.memory_id), reverse=True)
        return tuple(matching[:limit])

    def delete(self, memory_id: str) -> bool:
        with self._lock:
            return self._records.pop(memory_id, None) is not None
