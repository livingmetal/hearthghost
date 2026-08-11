"""Explicit, scoped text-only long-term memory boundary.

The first memory milestone refuses passive capture. A caller must provide an
explicit user-request signal and addressed text. Raw audio, images, sensor
observations, and pre-attention material are not representable by these DTOs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import uuid4

from apps.assistant.src.ports.memory import MemoryRepository
from apps.assistant.src.ports.node_gateway import Clock


MAX_MEMORY_TEXT_LENGTH = 2_000
MAX_SCOPE_ID_LENGTH = 128
MAX_RETRIEVAL_LIMIT = 50
IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")


class MemoryScope(str, Enum):
    USER = "user"
    HOUSEHOLD = "household"


class MemoryKind(str, Enum):
    SEMANTIC = "semantic"
    USER_PREFERENCE = "user_preference"
    NOTE = "note"


class MemorySource(str, Enum):
    ADDRESSED_TEXT = "addressed_text"


@dataclass(frozen=True)
class MemoryCandidate:
    scope: MemoryScope
    scope_id: str
    kind: MemoryKind
    text: str
    source: MemorySource
    source_conversation_session_id: str
    explicit_user_request: bool


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    scope: MemoryScope
    scope_id: str
    kind: MemoryKind
    text: str
    source: MemorySource
    source_conversation_session_id: str
    created_at: datetime


class MemoryManager:
    """Store and retrieve only validated, explicitly requested text memories."""

    def __init__(self, *, repository: MemoryRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def remember(self, candidate: MemoryCandidate) -> MemoryRecord:
        validated = _validate_candidate(candidate)
        now = self._now()
        record = MemoryRecord(
            memory_id=str(uuid4()),
            scope=validated.scope,
            scope_id=validated.scope_id,
            kind=validated.kind,
            text=validated.text.strip(),
            source=validated.source,
            source_conversation_session_id=validated.source_conversation_session_id,
            created_at=now,
        )
        try:
            self._repository.put(record)
        except Exception as error:
            raise RuntimeError("memory repository unavailable") from error
        return record

    def list_scope(
        self,
        scope: MemoryScope,
        scope_id: str,
        *,
        limit: int = 20,
    ) -> tuple[MemoryRecord, ...]:
        _validate_scope(scope, scope_id)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_RETRIEVAL_LIMIT:
            raise ValueError("memory retrieval limit must be 1 to 50")
        try:
            records = self._repository.list_scope(scope.value, scope_id, limit=limit)
        except Exception as error:
            raise RuntimeError("memory repository unavailable") from error
        if any(
            not isinstance(record, MemoryRecord)
            or record.scope is not scope
            or record.scope_id != scope_id
            for record in records
        ):
            raise RuntimeError("memory repository returned invalid scope data")
        return records

    def forget(self, memory_id: str, *, scope: MemoryScope, scope_id: str) -> bool:
        _validate_scope(scope, scope_id)
        if not _valid_identifier(memory_id):
            raise ValueError("memory_id is invalid")
        try:
            record = self._repository.get(memory_id)
        except Exception as error:
            raise RuntimeError("memory repository unavailable") from error
        if record is None:
            return False
        if (
            not isinstance(record, MemoryRecord)
            or record.scope is not scope
            or record.scope_id != scope_id
        ):
            return False
        try:
            return self._repository.delete(memory_id)
        except Exception as error:
            raise RuntimeError("memory repository unavailable") from error

    def _now(self) -> datetime:
        try:
            now = self._clock.now()
        except Exception as error:
            raise RuntimeError("memory clock unavailable") from error
        if now.tzinfo is None or now.utcoffset() is None:
            raise RuntimeError("memory clock returned naive time")
        return now


def _validate_candidate(candidate: object) -> MemoryCandidate:
    if not isinstance(candidate, MemoryCandidate):
        raise TypeError("memory candidate is invalid")
    _validate_scope(candidate.scope, candidate.scope_id)
    if candidate.source is not MemorySource.ADDRESSED_TEXT:
        raise ValueError("only addressed text may become long-term memory")
    if candidate.explicit_user_request is not True:
        raise ValueError("long-term memory requires an explicit user request")
    if not isinstance(candidate.kind, MemoryKind):
        raise ValueError("memory kind is invalid")
    if (
        not isinstance(candidate.text, str)
        or not candidate.text.strip()
        or len(candidate.text) > MAX_MEMORY_TEXT_LENGTH
        or "\x00" in candidate.text
        or any(ord(ch) < 32 and ch not in "\n\t" for ch in candidate.text)
    ):
        raise ValueError("memory text is invalid")
    if not _valid_identifier(candidate.source_conversation_session_id):
        raise ValueError("source conversation session is invalid")
    return candidate


def _validate_scope(scope: object, scope_id: object) -> None:
    if not isinstance(scope, MemoryScope):
        raise ValueError("memory scope is invalid")
    if (
        not isinstance(scope_id, str)
        or not scope_id
        or len(scope_id) > MAX_SCOPE_ID_LENGTH
        or not _valid_identifier(scope_id)
    ):
        raise ValueError("memory scope_id is invalid")


def _valid_identifier(value: object) -> bool:
    return isinstance(value, str) and IDENTIFIER_PATTERN.fullmatch(value) is not None
