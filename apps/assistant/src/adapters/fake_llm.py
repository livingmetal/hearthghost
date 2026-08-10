"""Explicit deterministic adapter for offline development and regression tests."""

from __future__ import annotations

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


class UnavailableLLMAdapter:
    """Default adapter; it never silently selects fake or network behavior."""

    def generate(self, request: LLMRequest, *, timeout_seconds: float) -> LLMCompletion:
        raise LLMUnavailableError(
            "No LLM adapter selected; choose fake explicitly or configure a server provider"
        )
