"""Narrow read-only transport port for Home Assistant state access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class HomeAssistantHttpResponse:
    status_code: int
    content_type: str
    body: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.status_code, int) or isinstance(self.status_code, bool):
            raise ValueError("Home Assistant status_code is invalid")
        if not isinstance(self.content_type, str) or len(self.content_type) > 256:
            raise ValueError("Home Assistant content_type is invalid")
        if not isinstance(self.body, bytes):
            raise ValueError("Home Assistant response body must be bytes")


class HomeAssistantReadTransport(Protocol):
    """GET-only transport whose implementation owns the Home Assistant credential."""

    def get(self, path: str) -> HomeAssistantHttpResponse:
        """Fetch one allow-listed read-only API path."""
