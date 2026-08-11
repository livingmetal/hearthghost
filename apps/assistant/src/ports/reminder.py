"""Reminder persistence and notification-delivery ports.

A persisted reminder is not notification authority. Delivery is a separate port
so Core can retain due work without assuming that any Node may display, vibrate,
or otherwise interrupt a user.
"""

from __future__ import annotations

from typing import Protocol


class ReminderRepository(Protocol):
    def put(self, record: object) -> None: ...

    def get(self, reminder_id: str) -> object | None: ...

    def find_active_for_todo(self, scope: str, scope_id: str, todo_id: str) -> object | None: ...

    def list_scope(self, scope: str, scope_id: str, *, limit: int) -> tuple[object, ...]: ...

    def replace(self, record: object) -> None: ...

    def delete(self, reminder_id: str) -> bool: ...


class ReminderDeliveryPort(Protocol):
    def deliver(self, request: object) -> object:
        """Attempt an already-authorized delivery; implementations must not infer authority."""
        ...
