"""Scoped conversation entry point for natural-language behavior preferences.

The command layer uses a conservative local cue filter so ordinary conversation
does not invoke a second LLM classification request. A cue is not authority: the
text still passes through the strict BehaviorPreferenceInterpreter and typed
protocol before any preference is applied.

Two exact local character-selection commands are deliberately deterministic so
an Android selector can switch between the reviewed Younghee/Cheolsu profiles
without paying for or trusting an LLM classification round trip.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from apps.assistant.src.modules.behavior_preference_interpreter import BehaviorPreferenceService
from apps.assistant.src.modules.behavior_preferences import (
    BehaviorPreferenceChange,
    BehaviorPreferenceSnapshot,
)
from apps.assistant.src.modules.conversation_principal import ConversationPrincipalResolver
from apps.assistant.src.modules.persona import (
    CHEOLSU_NAME,
    YOUNGHEE_NAME,
    default_expression_style_for_name,
)


_PREFERENCE_CUES = re.compile(
    r"(?:"
    r"캐릭터|이름|불러|말투|격식|존댓말|반말|농담|유머|답(?:변)?\s*(?:을\s*)?(?:짧|길)|"
    r"기다려|대화\s*시간|응답\s*길이|"
    r"\bcharacter\b|\bname\b|\bcall you\b|\bverbosity\b|\bconcise\b|\bdetailed\b|"
    r"\bformal(?:ity)?\b|\bcasual\b|\bhumou?r\b|\bjoke|\binitiative\b|"
    r"\bfollow[- ]?up\b|\bproactive\b"
    r")",
    re.IGNORECASE,
)
_CHARACTER_SELECTION = re.compile(
    rf"^\s*(?:캐릭터|character)\s*[:=]\s*({YOUNGHEE_NAME}|{CHEOLSU_NAME})\s*$",
    re.IGNORECASE,
)
_PERSONA_PROFILE_V1_PREFIX = "페르소나:v1:"
_PERSONA_PROFILE_V2_PREFIX = "페르소나:v2:"
_PERSONA_PROFILE_V1_QUERY = "페르소나조회:v1"
_PERSONA_PROFILE_V2_QUERY = "페르소나조회:v2"
_PERSONA_PROFILE_V1_STATE_PREFIX = "페르소나상태:v1:"
_PERSONA_PROFILE_V2_STATE_PREFIX = "페르소나상태:v2:"
_PERSONA_PROFILE_V1_FIELDS = frozenset(
    {"name", "humor", "verbosity", "formality", "initiative"}
)
_PERSONA_PROFILE_V2_FIELDS = _PERSONA_PROFILE_V1_FIELDS | {"expressionStyle"}


@dataclass(frozen=True)
class BehaviorPreferenceCommandResult:
    recognized: bool
    applied: bool
    reason: str
    response_text: str | None = None
    snapshot: BehaviorPreferenceSnapshot | None = None


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
        selection = _parse_character_selection(text)
        persona_query_version = _persona_query_version(text)
        persona_query = persona_query_version is not None
        persona_profile = None
        if isinstance(text, str) and text.startswith(
            (_PERSONA_PROFILE_V1_PREFIX, _PERSONA_PROFILE_V2_PREFIX)
        ):
            try:
                persona_profile = _parse_persona_profile(text)
            except (TypeError, ValueError, json.JSONDecodeError):
                return BehaviorPreferenceCommandResult(
                    True,
                    False,
                    "persona_profile_invalid",
                    "페르소나 설정 형식이 올바르지 않아 변경하지 않았어요.",
                )
        if (
            selection is None
            and persona_profile is None
            and not persona_query
            and not _looks_like_preference(text)
        ):
            return BehaviorPreferenceCommandResult(False, False, "not_preference_command")
        try:
            principal = self._principals.resolve(node_id)
        except Exception:
            return _denied("principal_resolution_failed")
        if principal is None:
            return _denied("principal_unresolved")

        if persona_query:
            try:
                snapshot = self._preferences.snapshot(
                    scope=principal.scope.value,
                    scope_id=principal.scope_id,
                )
            except (TypeError, ValueError, RuntimeError):
                return BehaviorPreferenceCommandResult(
                    True,
                    False,
                    "persona_profile_read_failed",
                    "서버 페르소나 설정을 안전하게 읽지 못했어요.",
                )
            persona = snapshot.persona
            payload = {
                "name": persona.name,
                "humor": persona.humor,
                "verbosity": persona.verbosity,
                "formality": persona.formality,
                "initiative": persona.initiative,
            }
            state_prefix = _PERSONA_PROFILE_V1_STATE_PREFIX
            if persona_query_version == 2:
                payload["expressionStyle"] = persona.expression_style
                state_prefix = _PERSONA_PROFILE_V2_STATE_PREFIX
            return BehaviorPreferenceCommandResult(
                True,
                False,
                "persona_profile_read",
                state_prefix
                + json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                snapshot,
            )

        try:
            if persona_profile is not None:
                result = self._preferences.apply_explicit(
                        [
                        BehaviorPreferenceChange(f"character.{field}", persona_profile[field])
                        for field in (
                            "name",
                            "humor",
                            "verbosity",
                            "formality",
                            "initiative",
                            "expression_style",
                        )
                        if field in persona_profile
                    ],
                    scope=principal.scope.value,
                    scope_id=principal.scope_id,
                    updated_by_node_id=node_id,
                )
            elif selection is not None:
                result = self._preferences.apply_explicit(
                [
                    BehaviorPreferenceChange("character.name", selection),
                    BehaviorPreferenceChange(
                        "character.expression_style",
                        default_expression_style_for_name(selection),
                    ),
                ],
                    scope=principal.scope.value,
                    scope_id=principal.scope_id,
                    updated_by_node_id=node_id,
                )
            else:
                result = self._preferences.interpret_and_apply(
                    text,
                    scope=principal.scope.value,
                    scope_id=principal.scope_id,
                    updated_by_node_id=node_id,
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
            message = (
                f"{persona.name} 페르소나를 적용했어요."
                if persona_profile is not None
                else (
                    f"{persona.name} 캐릭터로 전환했어요."
                    if selection is not None
                    else f"캐릭터 설정을 반영했어요. 이름: {persona.name}"
                )
            )
            return BehaviorPreferenceCommandResult(
                True,
                True,
                (
                    "persona_profile_applied"
                    if persona_profile is not None
                    else "character_profile_selected" if selection is not None else "preference_applied"
                ),
                message,
                result.snapshot,
            )
        if result.reason == "not_preference":
            return BehaviorPreferenceCommandResult(False, False, "not_preference")
        return BehaviorPreferenceCommandResult(
            True,
            False,
            result.reason,
            "캐릭터 설정 요청으로 보이지만 안전하게 적용하지 못했어요.",
        )


def _parse_character_selection(text: object) -> str | None:
    if not isinstance(text, str) or len(text) > 100 or "\x00" in text:
        return None
    match = _CHARACTER_SELECTION.fullmatch(text)
    if match is None:
        return None
    selected = match.group(1)
    if selected == YOUNGHEE_NAME:
        return YOUNGHEE_NAME
    if selected == CHEOLSU_NAME:
        return CHEOLSU_NAME
    return None


def _persona_query_version(text: object) -> int | None:
    if text == _PERSONA_PROFILE_V1_QUERY:
        return 1
    if text == _PERSONA_PROFILE_V2_QUERY:
        return 2
    return None


def _parse_persona_profile(text: object) -> dict[str, str]:
    if not isinstance(text, str) or len(text) > 1_000 or "\x00" in text:
        raise ValueError("persona profile command is invalid")
    if text.startswith(_PERSONA_PROFILE_V2_PREFIX):
        payload = json.loads(text[len(_PERSONA_PROFILE_V2_PREFIX) :])
        expected = _PERSONA_PROFILE_V2_FIELDS
        version = 2
    elif text.startswith(_PERSONA_PROFILE_V1_PREFIX):
        payload = json.loads(text[len(_PERSONA_PROFILE_V1_PREFIX) :])
        expected = _PERSONA_PROFILE_V1_FIELDS
        version = 1
    else:
        raise ValueError("persona profile command is invalid")
    if (
        not isinstance(payload, dict)
        or set(payload) != expected
        or any(not isinstance(value, str) for value in payload.values())
    ):
        raise ValueError("persona profile fields are invalid")
    normalized = dict(payload)
    if version == 2:
        normalized["expression_style"] = normalized.pop("expressionStyle")
    return normalized


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
