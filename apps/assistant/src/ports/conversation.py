"""Ports for bounded text conversation session persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from apps.assistant.src.modules.conversation import ConversationSession


class ConversationRepository(Protocol):
    """Stores conversation state independently from Node technical sessions."""

    def get(self, session_id: str) -> ConversationSession | None: ...

    def put(self, session: ConversationSession) -> None: ...
