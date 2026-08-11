"""Deterministic explicit-memory syntax with caller-supplied authorized scope."""

from __future__ import annotations

import re
from dataclasses import dataclass

from apps.assistant.src.modules.memory import (
    MemoryCandidate,
    MemoryKind,
    MemoryManager,
    MemoryRecord,
    MemoryScope,
    MemorySource,
)


PREFIX_PATTERNS = (
    re.compile(r"^\s*기억해\s*[:：]\s*(?P<text>.+?)\s*$", re.DOTALL),
    re.compile(r"^\s*기억해줘\s*[:：]\s*(?P<text>.+?)\s*$", re.DOTALL),
    re.compile(r"^\s*remember(?:\s+this)?\s*[:：]\s*(?P<text>.+?)\s*$", re.IGNORECASE | re.DOTALL),
)
SUFFIX_PATTERNS = (
    re.compile(r"^\s*(?P<text>.+?)\s*[,.]?\s*기억해(?:줘)?\s*[.!]?\s*$", re.DOTALL),
    re.compile(r"^\s*(?P<text>.+?)\s*[,.]?\s*remember\s+this\s*[.!]?\s*$", re.IGNORECASE | re.DOTALL),
)


@dataclass(frozen=True)
class ExplicitMemoryRequest:
    text: str
    kind: MemoryKind = MemoryKind.SEMANTIC


class ExplicitMemoryParser:
    """Recognize only unambiguous user phrases that explicitly request memory."""

    def parse(self, text: object) -> ExplicitMemoryRequest | None:
        if not isinstance(text, str) or not text.strip() or "\x00" in text:
            return None
        for pattern in PREFIX_PATTERNS + SUFFIX_PATTERNS:
            match = pattern.fullmatch(text)
            if match is None:
                continue
            remembered = match.group("text").strip()
            if not remembered or len(remembered) > 2_000:
                return None
            return ExplicitMemoryRequest(remembered)
        return None


@dataclass(frozen=True)
class ExplicitMemoryResult:
    recognized: bool
    stored: bool
    reason: str
    record: MemoryRecord | None = None


class ExplicitMemoryService:
    """Store explicit text only after a trusted caller supplies the scope."""

    def __init__(self, *, parser: ExplicitMemoryParser, memory: MemoryManager) -> None:
        self._parser = parser
        self._memory = memory

    def remember_if_explicit(
        self,
        text: str,
        *,
        authorized_scope: MemoryScope,
        authorized_scope_id: str,
        conversation_session_id: str,
    ) -> ExplicitMemoryResult:
        request = self._parser.parse(text)
        if request is None:
            return ExplicitMemoryResult(False, False, "not_explicit_memory_request")
        try:
            record = self._memory.remember(
                MemoryCandidate(
                    scope=authorized_scope,
                    scope_id=authorized_scope_id,
                    kind=request.kind,
                    text=request.text,
                    source=MemorySource.ADDRESSED_TEXT,
                    source_conversation_session_id=conversation_session_id,
                    explicit_user_request=True,
                )
            )
        except (TypeError, ValueError, RuntimeError):
            return ExplicitMemoryResult(True, False, "memory_rejected")
        return ExplicitMemoryResult(True, True, "memory_stored", record)
