"""Explicit deterministic adapter for offline development and regression tests."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum

from apps.assistant.src.ports.llm import (
    LLMCompletion,
    LLMProviderError,
    LLMRequest,
    LLMTimeoutError,
    LLMUnavailableError,
    ProposedAction,
)


class FakeLLMOutcome(str, Enum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    FAILURE = "failure"


@dataclass
class FakeLLMAdapter:
    outcome: FakeLLMOutcome = FakeLLMOutcome.SUCCESS
    requests: list[LLMRequest] = field(default_factory=list)

    def generate(self, request: LLMRequest, *, timeout_seconds: float) -> LLMCompletion:
        self.requests.append(request)
        if self.outcome is FakeLLMOutcome.TIMEOUT:
            raise LLMTimeoutError("fake provider timed out")
        if self.outcome is FakeLLMOutcome.UNAVAILABLE:
            raise LLMUnavailableError("fake provider unavailable")
        if self.outcome is FakeLLMOutcome.FAILURE:
            raise LLMProviderError("fake provider failed")

        lowered = request.input_text.casefold()
        if "BEHAVIOR_PREFERENCE_INTERPRETER_V1" in request.instructions:
            return self._preference_completion(request.input_text, lowered)
        if "ignore policy" in lowered or "reveal secret" in lowered:
            return LLMCompletion(
                "I cannot change security policy, reveal secrets, or execute tools.",
            )
        if "turn off" in lowered or "불 꺼" in lowered or "불꺼" in lowered:
            return LLMCompletion(
                "I can only propose turning off the living-room light; no device is connected.",
                proposed_actions=(
                    ProposedAction(
                        name="home.light.off",
                        arguments={"area": "living_room"},
                    ),
                ),
            )
        return LLMCompletion(f"Fake HearthGhost response: {request.input_text}")

    @staticmethod
    def _preference_completion(original: str, lowered: str) -> LLMCompletion:
        changes: list[dict[str, object]] = []
        candidate = _fake_name_candidate(original)
        if candidate is not None:
            changes.append({"path": "character.name", "value": candidate})
        if "짧게" in lowered or "concise" in lowered:
            changes.append({"path": "character.verbosity", "value": "concise"})
        if "농담" in lowered and ("많" in lowered or "more" in lowered):
            changes.append({"path": "character.humor", "value": "high"})
        if "30초" in lowered or "30 seconds" in lowered:
            changes.append({"path": "conversation.followup_timeout_sec", "value": 30})
        if "카메라" in lowered or "camera" in lowered or "policy" in lowered:
            changes = []
        payload = {
            "intent": "behavior_preference_update" if changes else "not_preference",
            "changes": changes,
        }
        return LLMCompletion(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


_KOREAN_NAME_PATTERN = re.compile(
    r"^\s*이름(?:을|은)?\s*(?:[:：]\s*)?(?P<name>[\w가-힣 .'-]{1,80}?)\s*"
    r"(?:으?로\s*)?(?:바꿔줘|바꿔|해줘|해)\s*[.!]?\s*$",
    re.IGNORECASE,
)
_ENGLISH_NAME_PATTERN = re.compile(
    r"^\s*(?:name|call\s+yourself)\s*(?:[:：]|is|to)?\s*"
    r"(?P<name>[\w .'-]{1,80}?)\s*(?:please\s*)?$",
    re.IGNORECASE,
)


def _fake_name_candidate(value: str) -> str | None:
    for pattern in (_KOREAN_NAME_PATTERN, _ENGLISH_NAME_PATTERN):
        match = pattern.fullmatch(value)
        if match is None:
            continue
        candidate = match.group("name").strip()
        return candidate or None
    return None


class UnavailableLLMAdapter:
    """Default adapter; it never silently selects fake or network behavior."""

    def generate(self, request: LLMRequest, *, timeout_seconds: float) -> LLMCompletion:
        raise LLMUnavailableError(
            "No LLM adapter selected; choose fake explicitly or configure a server provider"
        )
