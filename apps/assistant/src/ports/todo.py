"""Persistence port for scoped todo records."""

from __future__ import annotations

from typing import Protocol


class TodoRepository(Protocol):
    def put(self, record: object) -> None: ...

    def get(self, todo_id: str) -> object | None: ...

    def list_scope(self, scope: str, scope_id: str, *, limit: int) -> tuple[object, ...]: ...

    def replace(self, record: object) -> None: ...

    def delete(self, todo_id: str) -> bool: ...
