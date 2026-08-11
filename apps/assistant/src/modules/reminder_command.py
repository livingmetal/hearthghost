"""Deterministic reminder commands that never delegate scheduling intent to the LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass

from apps.assistant.src.modules.conversation_principal import ConversationPrincipalResolver
from apps.assistant.src.modules.reminder import ReminderManager, ReminderState
from apps.assistant.src.modules.todo import TodoManager, TodoRecord


_TODO_REF = r"(?P<todo_ref>(?:[0-9a-fA-F]{8}|[0-9a-fA-F-]{36}))"
_SCHEDULE_PATTERNS = (
    re.compile(rf"^\s*할\s*일\s*알림\s*[:：]\s*{_TODO_REF}\s*$"),
    re.compile(rf"^\s*todo\s+reminder\s*[:：]\s*{_TODO_REF}\s*$", re.IGNORECASE),
)
_CANCEL_PATTERNS = (
    re.compile(rf"^\s*할\s*일\s*알림\s*취소\s*[:：]\s*{_TODO_REF}\s*$"),
    re.compile(rf"^\s*todo\s+reminder\s+cancel\s*[:：]\s*{_TODO_REF}\s*$", re.IGNORECASE),
)
_LIST_PATTERNS = (
    re.compile(r"^\s*알림\s*목록\s*[.!?]?\s*$"),
    re.compile(r"^\s*reminder\s+list\s*[.!?]?\s*$", re.IGNORECASE),
)


@dataclass(frozen=True)
class ReminderCommandResult:
    recognized: bool
    succeeded: bool
    reason: str
    response_text: str | None = None


class ReminderCommandService:
    def __init__(
        self,
        *,
        reminders: ReminderManager,
        todos: TodoManager,
        principals: ConversationPrincipalResolver,
    ) -> None:
        self._reminders = reminders
        self._todos = todos
        self._principals = principals

    def handle(self, *, node_id: str, text: str) -> ReminderCommandResult:
        parsed = _parse(text)
        if parsed is None:
            return ReminderCommandResult(False, False, "not_reminder_command")
        kind, reference = parsed
        try:
            principal = self._principals.resolve(node_id)
        except Exception:
            return _denied("principal_resolution_failed")
        if principal is None:
            return _denied("principal_unresolved")

        try:
            if kind == "list":
                records = [
                    record
                    for record in self._reminders.list_scope(principal.scope, principal.scope_id, limit=100)
                    if record.state is ReminderState.SCHEDULED
                ][:10]
                if not records:
                    return ReminderCommandResult(True, True, "reminder_list_empty", "예약된 알림이 없어요.")
                lines = ["예약된 알림이에요."]
                lines.extend(
                    f"{index}. [{record.reminder_id[:8]}] TODO[{record.todo_id[:8]}] {record.fire_at.isoformat()}"
                    for index, record in enumerate(records, start=1)
                )
                return ReminderCommandResult(True, True, "reminder_listed", "\n".join(lines))

            resolved = _resolve_todo_ref(
                self._todos,
                reference,
                scope=principal.scope,
                scope_id=principal.scope_id,
            )
            if resolved is _AMBIGUOUS:
                return ReminderCommandResult(
                    True,
                    False,
                    "todo_reference_ambiguous",
                    "짧은 할 일 ID가 겹쳐 알림을 처리하지 않았어요. 전체 ID를 사용해 주세요.",
                )
            if resolved is None:
                return ReminderCommandResult(
                    True,
                    False,
                    "todo_not_found_in_scope",
                    "이 범위에서 해당 할 일을 찾지 못했어요.",
                )

            if kind == "cancel":
                cancelled = self._reminders.cancel_for_todo(resolved)
                if cancelled is None:
                    return ReminderCommandResult(True, True, "reminder_not_scheduled", "취소할 활성 알림이 없어요.")
                return ReminderCommandResult(True, True, "reminder_cancelled", "할 일 알림 예약을 취소했어요.")

            reminder = self._reminders.schedule_for_todo(
                resolved,
                created_by_node_id=node_id,
                explicit_user_request=True,
            )
            return ReminderCommandResult(
                True,
                True,
                "reminder_scheduled",
                f"알림 예약을 저장했어요. [{reminder.reminder_id[:8]}] {reminder.fire_at.isoformat()} 기기 전달은 별도 권한에 따라 처리돼요.",
            )
        except ValueError as error:
            return ReminderCommandResult(True, False, "reminder_rejected", _safe_rejection_text(error))
        except (TypeError, RuntimeError):
            return ReminderCommandResult(
                True,
                False,
                "reminder_rejected",
                "알림 요청을 안전하게 저장하거나 변경할 수 없었어요.",
            )


def _parse(text: object) -> tuple[str, str] | None:
    if not isinstance(text, str) or not text.strip() or "\x00" in text:
        return None
    for pattern in _LIST_PATTERNS:
        if pattern.fullmatch(text) is not None:
            return "list", ""
    for kind, patterns in (("cancel", _CANCEL_PATTERNS), ("schedule", _SCHEDULE_PATTERNS)):
        for pattern in patterns:
            match = pattern.fullmatch(text)
            if match is not None:
                return kind, match.group("todo_ref").lower()
    return None


def _resolve_todo_ref(todos: TodoManager, reference: str, *, scope, scope_id) -> TodoRecord | object | None:
    if len(reference) == 36:
        return todos.get(reference, scope=scope, scope_id=scope_id)
    matches = [
        record
        for record in todos.list_scope(scope, scope_id, limit=100)
        if record.todo_id.startswith(reference)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return _AMBIGUOUS
    return None


def _safe_rejection_text(error: ValueError) -> str:
    message = str(error)
    if "due_at" in message or "future" in message or "horizon" in message:
        return "알림을 예약하려면 열린 할 일에 현재보다 미래의 유효한 기한이 필요해요."
    if "explicit" in message:
        return "알림은 명시적으로 요청한 경우에만 예약할 수 있어요."
    return "알림 요청을 안전하게 처리할 수 없었어요."


_AMBIGUOUS = object()


def _denied(reason: str) -> ReminderCommandResult:
    return ReminderCommandResult(
        True,
        False,
        reason,
        "이 Node의 저장 범위를 안전하게 확인할 수 없어 알림을 처리하지 않았어요.",
    )
