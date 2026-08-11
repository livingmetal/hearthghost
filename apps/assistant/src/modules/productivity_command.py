"""Deterministic local note/todo commands with principal-scoped persistence."""

from __future__ import annotations

import re
from dataclasses import dataclass

from apps.assistant.src.modules.conversation_principal import ConversationPrincipalResolver
from apps.assistant.src.modules.memory import MemoryCandidate, MemoryKind, MemoryManager, MemorySource
from apps.assistant.src.modules.todo import TodoManager, TodoRecord


_NOTE_PATTERNS = (
    re.compile(r"^\s*메모해\s*[:：]\s*(?P<text>.+?)\s*$", re.DOTALL),
    re.compile(r"^\s*노트\s*[:：]\s*(?P<text>.+?)\s*$", re.DOTALL),
    re.compile(r"^\s*note\s*[:：]\s*(?P<text>.+?)\s*$", re.IGNORECASE | re.DOTALL),
)
_TODO_PATTERNS = (
    re.compile(r"^\s*할\s*일\s*[:：]\s*(?P<text>.+?)\s*$", re.DOTALL),
    re.compile(r"^\s*todo\s*[:：]\s*(?P<text>.+?)\s*$", re.IGNORECASE | re.DOTALL),
)
_COMPLETE_PATTERNS = (
    re.compile(r"^\s*할\s*일\s*완료\s*[:：]\s*(?P<todo_id>[0-9a-fA-F-]{36})\s*$"),
    re.compile(r"^\s*todo\s+done\s*[:：]\s*(?P<todo_id>[0-9a-fA-F-]{36})\s*$", re.IGNORECASE),
)


@dataclass(frozen=True)
class ProductivityCommandResult:
    recognized: bool
    succeeded: bool
    reason: str
    response_text: str | None = None
    todo: TodoRecord | None = None


class ProductivityCommandService:
    def __init__(self, *, memory: MemoryManager, todos: TodoManager, principals: ConversationPrincipalResolver) -> None:
        self._memory = memory
        self._todos = todos
        self._principals = principals

    def handle(self, *, node_id: str, text: str, conversation_session_id: str) -> ProductivityCommandResult:
        parsed = _parse(text)
        if parsed is None:
            return ProductivityCommandResult(False, False, "not_productivity_command")
        kind, value = parsed
        try:
            principal = self._principals.resolve(node_id)
        except Exception:
            return _denied("principal_resolution_failed")
        if principal is None:
            return _denied("principal_unresolved")

        try:
            if kind == "note":
                self._memory.remember(
                    MemoryCandidate(
                        scope=principal.scope,
                        scope_id=principal.scope_id,
                        kind=MemoryKind.NOTE,
                        text=value,
                        source=MemorySource.ADDRESSED_TEXT,
                        source_conversation_session_id=conversation_session_id,
                        explicit_user_request=True,
                    )
                )
                return ProductivityCommandResult(True, True, "note_stored", "메모했어요.")
            if kind == "todo":
                todo = self._todos.create(scope=principal.scope, scope_id=principal.scope_id, text=value)
                return ProductivityCommandResult(
                    True, True, "todo_created", f"할 일로 추가했어요. ID: {todo.todo_id}", todo
                )
            completed = self._todos.complete(value, scope=principal.scope, scope_id=principal.scope_id)
            if completed is None:
                return ProductivityCommandResult(
                    True, False, "todo_not_found_in_scope", "이 범위에서 해당 할 일을 찾지 못했어요."
                )
            return ProductivityCommandResult(True, True, "todo_completed", "할 일을 완료 처리했어요.", completed)
        except (TypeError, ValueError, RuntimeError):
            return ProductivityCommandResult(
                True, False, "productivity_rejected", "요청을 안전하게 저장하거나 변경할 수 없었어요."
            )


def _parse(text: object) -> tuple[str, str] | None:
    if not isinstance(text, str) or not text.strip() or "\x00" in text:
        return None
    for kind, patterns in (("note", _NOTE_PATTERNS), ("todo", _TODO_PATTERNS), ("complete", _COMPLETE_PATTERNS)):
        for pattern in patterns:
            match = pattern.fullmatch(text)
            if match is None:
                continue
            group = "todo_id" if kind == "complete" else "text"
            value = match.group(group).strip()
            if not value or len(value) > 2_000:
                return None
            return kind, value.lower() if kind == "complete" else value
    return None


def _denied(reason: str) -> ProductivityCommandResult:
    return ProductivityCommandResult(
        True, False, reason, "이 Node의 저장 범위를 안전하게 확인할 수 없어 처리하지 않았어요."
    )
