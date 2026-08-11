"""Scoped conversation entry point for natural-language behavior preferences.

The command layer uses a conservative local cue filter so ordinary conversation
does not invoke a second LLM classification request. A cue is not authority: the
text still passes through the strict BehaviorPreferenceInterpreter and typed
protocol before any preference is applied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from apps.assistant.src.modules.behavior_preference_interpreter import BehaviorPreferenceService
from apps.assistant.src.modules.conversation_principal import ConversationPrincipalResolver


_PREFERENCE_CUES = re.compile(
    r"(?:"
    r"이름|불러|말투|격식|존댓말|반말|농담|유머|답(?:변)?\s*(?:을\s*)?(?:짧|길)|"
    r"기다려|대화\s*시간|응답\s*길이|"
    r"\bname\b|\bcall you\b|\bverbosity\b|\bconcise\b|\bdetailed\b|"
    r"\bformal(?:ity)?\b|\bcasual\b|\bhumou?r\b|\bjoke|\binitiative\b|"
    r"\bfollow[- ]?up\b|\bproactive\b"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BehaviorPreferenceCommandResult:
    recognized: bool
    applied: bool
    reason: str
    response_text: str | None = None


class BehaviorPreferenceCommandService:
    def __init__(
        self,
        *,
        preferences: BehaviorPreferenceService,
        principals: ConversationPrincipalResolver,
    ) -> None:
        self._preferences = preferences
        self._principals = principals

    def handle(self, *, node_id: str, text: str) -> BehaviorPreferenceCommandResult:
        if not _looks_like_preference(text):
            return BehaviorPreferenceCommandResult(False, False, "not_preference_command")
        try:
            principal = self._principals.resolve(node_id)
        except Exception:
            return _denied("principal_resolution_failed")
        if principal is None:
            return _denied("principal_unresolved")

        try:
            result = self._preferences.interpret_and_apply(
                text,
                scope=principal.scope.value,
                scope_id=principal.scope_id,
            )
        except (TypeError, ValueError, RuntimeError):
            return BehaviorPreferenceCommandResult(
                True,
                False,
                "preference_interpreter_failed",
                "캐릭터 설정 요청을 안전하게 해석할 수 없어 변경하지 않았어요.",
            )

        if result.applied and result.snapshot is not None:
            persona = result.snapshot.persona
            return BehaviorPreferenceCommandResult(
                True,
                True,
                "preference_applied",
                f"캐릭터 설정을 반영했어요. 이름: {persona.name}",
            )
        if result.reason == "not_preference":
            return BehaviorPreferenceCommandResult(False, False, "not_preference")
        return BehaviorPreferenceCommandResult(
            True,
            False,
            result.reason,
            "캐릭터 설정 요청으로 보이지만 안전하게 적용하지 못했어요.",
        )


def _looks_like_preference(text: object) -> bool:
    return (
        isinstance(text, str)
        and 1 <= len(text) <= 1_000
        and "\x00" not in text
        and _PREFERENCE_CUES.search(text) is not None
    )


def _denied(reason: str) -> BehaviorPreferenceCommandResult:
    return BehaviorPreferenceCommandResult(
        True,
        False,
        reason,
        "이 Node의 사용자 범위를 안전하게 확인할 수 없어 캐릭터 설정을 변경하지 않았어요.",
    )
