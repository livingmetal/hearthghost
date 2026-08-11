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
        name_match = re.fullmatch(
            r"\s*(?:이름(?:을|은)?|name)\s*(?:[:：]|을|은|로|is|to)?\s*([\w가-힣 .'-]{1,80})\s*(?:로\s*)?(?:해|해줘|바꿔|바꿔줘|please)?\s*[.!]?\s*",
            original,
            flags=re.IGNORECASE,
        )
        if name_match is not None:
            candidate = name_match.group(1).strip()
            if candidate:
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


class UnavailableLLMAdapter:
    """Default adapter; it never silently selects fake or network behavior."""

    def generate(self, request: LLMRequest, *, timeout_seconds: float) -> LLMCompletion:
        raise LLMUnavailableError(
            "No LLM adapter selected; choose fake explicitly or configure a server provider"
        )
