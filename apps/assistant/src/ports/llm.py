"""Provider-neutral text generation port and bounded domain DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass(frozen=True)
class ProposedAction:
    """Non-authoritative action idea that still requires Policy and execution."""

    name: str
    arguments: Mapping[str, str]
    authorization_status: str = "pending_policy"

    def __post_init__(self) -> None:
        if self.authorization_status != "pending_policy":
            raise ValueError("LLM action proposals must remain pending_policy")
        if not self.name or not isinstance(self.arguments, Mapping):
            raise ValueError("LLM action proposal is malformed")


@dataclass(frozen=True)
class LLMRequest:
    request_id: str
    conversation_session_id: str
    instructions: str
    input_text: str


@dataclass(frozen=True)
class LLMCompletion:
    text: str
    proposed_actions: tuple[ProposedAction, ...] = ()


class LLMError(RuntimeError):
    """Base error whose message must never include provider credentials."""


class LLMTimeoutError(LLMError):
    pass


class LLMUnavailableError(LLMError):
    pass


class LLMProviderError(LLMError):
    pass


class LLMPort(Protocol):
    def generate(self, request: LLMRequest, *, timeout_seconds: float) -> LLMCompletion:
        """Generate text/proposals only; this port exposes no executor."""
