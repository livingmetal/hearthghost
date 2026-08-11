"""Deterministic local note/todo commands with principal-scoped persistence."""

from __future__ import annotations

import re
from dataclasses import dataclass

from apps.assistant.src.modules.conversation_principal import ConversationPrincipalResolver
from apps.assistant.src.modules.memory import MemoryCandidate, MemoryKind, MemoryManager, MemorySource
from apps.assistant.src.modules.todo import TodoManager, TodoRecord, TodoState


_NOTE_PATTERNS = (
    re.compile(r"^\s*메모해\s*[:：]\s*(?P<text>.+?)\s*$", re.DOTALL),
    re.compile(r"^\s*노트\s*[:：]\s*(?P<text>.+?)\s*$", re.DOTALL),
    re.compile(r"^\s*note\s*[:：]\s*(?P<text>.+?)\s*$", re.IGNORECASE | re.DOTALL),
)
_NOTE_LIST_PATTERNS = (
    re.compile(r"^\s*(?:메모|노트)\s*목록\s*[.!?]?\s*$"),
    re.compile(r"^\s*note\s+list\s*[.!?]?\s*$", re.IGNORECASE),
)
_ITEM_REF = r"(?P<item_ref>(?:[0-9a-fA-F]{8}|[0-9a-fA-F-]{36}))"
_NOTE_DELETE_PATTERNS = (
    re.compile(rf"^\s*(?:메모|노트)\s*삭제\s*[:：]\s*{_ITEM_REF}\s*$"),
    re.compile(rf"^\s*note\s+delete\s*[:：]\s*{_ITEM_REF}\s*$", re.IGNORECASE),
)
_TODO_PATTERNS = (
    re.compile(r"^\s*할\s*일\s*[:：]\s*(?P<text>.+?)\s*$", re.DOTALL),
    re.compile(r"^\s*todo\s*[:：]\s*(?P<text>.+?)\s*$", re.IGNORECASE | re.DOTALL),
)
_TODO_REF = r"(?P<todo_ref>(?:[0-9a-fA-F]{8}|[0-9a-fA-F-]{36}))"
_COMPLETE_PATTERNS = (
    re.compile(rf"^\s*할\s*일\s*완료\s*[:：]\s*{_TODO_REF}\s*$"),
    re.compile(rf"^\s*todo\s+done\s*[:：]\s*{_TODO_REF}\s*$", re.IGNORECASE),
)
_DELETE_PATTERNS = (
    re.compile(rf"^\s*할\s*일\s*삭제\s*[:：]\s*{_TODO_REF}\s*$"),
    re.compile(rf"^\s*todo\s+delete\s*[:：]\s*{_TODO_REF}\s*$", re.IGNORECASE),
)
_LIST_PATTERNS = (
    re.compile(r"^\s*할\s*일\s*목록\s*[.!?]?\s*$"),
    re.compile(r"^\s*todo\s+list\s*[.!?]?\s*$", re.IGNORECASE),
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
                record = self._memory.remember(
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
                return ProductivityCommandResult(
                    True,
                    True,
                    "note_stored",
                    f"메모했어요. [{_short_ref(record.memory_id)}]",
                )

            if kind == "note_list":
                records = [
                    record
                    for record in self._memory.list_scope(principal.scope, principal.scope_id, limit=50)
                    if record.kind is MemoryKind.NOTE
                ][:10]
                if not records:
                    return ProductivityCommandResult(True, True, "note_list_empty", "저장된 메모가 없어요.")
                lines = ["최근 메모예요."]
                lines.extend(
                    f"{index}. [{_short_ref(record.memory_id)}] {record.text}"
                    for index, record in enumerate(records, start=1)
                )
                return ProductivityCommandResult(True, True, "note_listed", "\n".join(lines))

            if kind == "note_delete":
                resolved = _resolve_note_ref(
                    self._memory,
                    value,
                    scope=principal.scope,
                    scope_id=principal.scope_id,
                )
                if resolved is None:
                    return ProductivityCommandResult(
                        True, False, "note_not_found_in_scope", "이 범위에서 해당 메모를 찾지 못했어요."
                    )
                if resolved is _AMBIGUOUS:
                    return ProductivityCommandResult(
                        True,
                        False,
                        "note_reference_ambiguous",
                        "짧은 메모 ID가 겹쳐 처리하지 않았어요. 전체 ID를 사용해 주세요.",
                    )
                deleted = self._memory.forget(
                    resolved,
                    scope=principal.scope,
                    scope_id=principal.scope_id,
                )
                return ProductivityCommandResult(
                    True,
                    deleted,
                    "note_deleted" if deleted else "note_not_found_in_scope",
                    "메모를 삭제했어요." if deleted else "이 범위에서 해당 메모를 찾지 못했어요.",
                )

            if kind == "todo":
                todo = self._todos.create(scope=principal.scope, scope_id=principal.scope_id, text=value)
                return ProductivityCommandResult(
                    True,
                    True,
                    "todo_created",
                    f"할 일로 추가했어요. [{_short_ref(todo.todo_id)}]",
                    todo,
                )

            if kind == "list":
                records = self._todos.list_scope(principal.scope, principal.scope_id, limit=100)
                open_records = [record for record in records if record.state is TodoState.OPEN][:10]
                if not open_records:
                    return ProductivityCommandResult(True, True, "todo_list_empty", "열린 할 일이 없어요.")
                lines = ["열린 할 일이에요."]
                lines.extend(
                    f"{index}. [{_short_ref(record.todo_id)}] {record.text}"
                    for index, record in enumerate(open_records, start=1)
                )
                return ProductivityCommandResult(True, True, "todo_listed", "\n".join(lines))

            resolved = _resolve_todo_ref(
                self._todos,
                value,
                scope=principal.scope,
                scope_id=principal.scope_id,
            )
            if resolved is None:
                return ProductivityCommandResult(
                    True,
                    False,
                    "todo_not_found_in_scope",
                    "이 범위에서 해당 할 일을 찾지 못했어요.",
                )
            if resolved is _AMBIGUOUS:
                return ProductivityCommandResult(
                    True,
                    False,
                    "todo_reference_ambiguous",
                    "짧은 할 일 ID가 겹쳐 처리하지 않았어요. 전체 ID를 사용해 주세요.",
                )

            if kind == "delete":
                deleted = self._todos.delete(
                    resolved,
                    scope=principal.scope,
                    scope_id=principal.scope_id,
                )
                return ProductivityCommandResult(
                    True,
                    deleted,
                    "todo_deleted" if deleted else "todo_not_found_in_scope",
                    "할 일을 삭제했어요." if deleted else "이 범위에서 해당 할 일을 찾지 못했어요.",
                )

            completed = self._todos.complete(
                resolved,
                scope=principal.scope,
                scope_id=principal.scope_id,
            )
            if completed is None:
                return ProductivityCommandResult(
                    True,
                    False,
                    "todo_not_found_in_scope",
                    "이 범위에서 해당 할 일을 찾지 못했어요.",
                )
            return ProductivityCommandResult(True, True, "todo_completed", "할 일을 완료 처리했어요.", completed)
        except (TypeError, ValueError, RuntimeError):
            return ProductivityCommandResult(
                True,
                False,
                "productivity_rejected",
                "요청을 안전하게 저장하거나 변경할 수 없었어요.",
            )


def _parse(text: object) -> tuple[str, str] | None:
    if not isinstance(text, str) or not text.strip() or "\x00" in text:
        return None
    for pattern in _NOTE_LIST_PATTERNS:
        if pattern.fullmatch(text) is not None:
            return "note_list", ""
    for pattern in _LIST_PATTERNS:
        if pattern.fullmatch(text) is not None:
            return "list", ""
    for kind, patterns in (
        ("note", _NOTE_PATTERNS),
        ("note_delete", _NOTE_DELETE_PATTERNS),
        ("todo", _TODO_PATTERNS),
        ("complete", _COMPLETE_PATTERNS),
        ("delete", _DELETE_PATTERNS),
    ):
        for pattern in patterns:
            match = pattern.fullmatch(text)
            if match is None:
                continue
            if kind == "note_delete":
                group = "item_ref"
            elif kind in {"complete", "delete"}:
                group = "todo_ref"
            else:
                group = "text"
            value = match.group(group).strip()
            if not value or len(value) > 2_000:
                return None
            return kind, value.lower() if kind in {"note_delete", "complete", "delete"} else value
    return None


def _short_ref(item_id: str) -> str:
    return item_id[:8]


_AMBIGUOUS = object()


def _resolve_todo_ref(todos: TodoManager, reference: str, *, scope, scope_id):
    if len(reference) == 36:
        return reference
    matches = [
        record.todo_id
        for record in todos.list_scope(scope, scope_id, limit=100)
        if record.todo_id.startswith(reference)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return _AMBIGUOUS
    return None


def _resolve_note_ref(memory: MemoryManager, reference: str, *, scope, scope_id):
    notes = [
        record
        for record in memory.list_scope(scope, scope_id, limit=50)
        if record.kind is MemoryKind.NOTE
    ]
    if len(reference) == 36:
        return reference if any(record.memory_id == reference for record in notes) else None
    matches = [record.memory_id for record in notes if record.memory_id.startswith(reference)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return _AMBIGUOUS
    return None


def _denied(reason: str) -> ProductivityCommandResult:
    return ProductivityCommandResult(
        True,
        False,
        reason,
        "이 Node의 저장 범위를 안전하게 확인할 수 없어 처리하지 않았어요.",
    )
