"""Local handling of explicit memory commands before any LLM call."""

from __future__ import annotations

from dataclasses import dataclass

from apps.assistant.src.modules.conversation_principal import (
    ConversationPrincipalResolver,
)
from apps.assistant.src.modules.explicit_memory import ExplicitMemoryParser
from apps.assistant.src.modules.memory import (
    MemoryCandidate,
    MemoryManager,
    MemoryRecord,
    MemorySource,
)


@dataclass(frozen=True)
class MemoryCommandResult:
    recognized: bool
    stored: bool
    reason: str
    record: MemoryRecord | None = None


class MemoryCommandService:
    """Recognize deterministic memory syntax and store only within resolved scope."""

    def __init__(
        self,
        *,
        parser: ExplicitMemoryParser,
        memory: MemoryManager,
        principals: ConversationPrincipalResolver,
    ) -> None:
        self._parser = parser
        self._memory = memory
        self._principals = principals

    def handle(
        self,
        *,
        node_id: str,
        text: str,
        conversation_session_id: str,
    ) -> MemoryCommandResult:
        request = self._parser.parse(text)
        if request is None:
            return MemoryCommandResult(False, False, "not_explicit_memory_request")

        try:
            principal = self._principals.resolve(node_id)
        except Exception:
            return MemoryCommandResult(True, False, "principal_resolution_failed")
        if principal is None:
            return MemoryCommandResult(True, False, "principal_unresolved")

        try:
            record = self._memory.remember(
                MemoryCandidate(
                    scope=principal.scope,
                    scope_id=principal.scope_id,
                    kind=request.kind,
                    text=request.text,
                    source=MemorySource.ADDRESSED_TEXT,
                    source_conversation_session_id=conversation_session_id,
                    explicit_user_request=True,
                )
            )
        except (TypeError, ValueError, RuntimeError):
            return MemoryCommandResult(True, False, "memory_rejected")
        return MemoryCommandResult(True, True, "memory_stored", record)
