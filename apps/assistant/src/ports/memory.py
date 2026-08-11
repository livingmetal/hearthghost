"""Storage port for explicitly approved long-term memories."""

from __future__ import annotations

from typing import Protocol


class MemoryRepository(Protocol):
    def put(self, record: object) -> None:
        """Persist one validated memory record."""

    def get(self, memory_id: str) -> object | None:
        """Return one record by identifier."""

    def list_scope(self, scope: str, scope_id: str, *, limit: int) -> tuple[object, ...]:
        """Return newest records visible only inside the exact scope."""

    def delete(self, memory_id: str) -> bool:
        """Delete one record and report whether it existed."""
