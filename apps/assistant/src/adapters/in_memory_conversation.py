"""Ephemeral conversation repository for development and tests."""

from __future__ import annotations

from threading import RLock

from apps.assistant.src.modules.conversation import ConversationSession


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, ConversationSession] = {}
        self._lock = RLock()

    def get(self, session_id: str) -> ConversationSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def put(self, session: ConversationSession) -> None:
        with self._lock:
            self._sessions[session.session_id] = session
