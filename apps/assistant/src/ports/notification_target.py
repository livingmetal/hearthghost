"""Principal-to-Node routing port for reminder notification delivery."""

from __future__ import annotations

from typing import Protocol


class NotificationTargetResolver(Protocol):
    def resolve(self, scope: str, scope_id: str) -> str | None:
        """Return an explicitly configured target Node, never an inferred origin Node."""
        ...
