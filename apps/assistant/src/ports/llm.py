"""Provider-neutral text generation port and bounded domain DTOs."""

from __future__ import annotations

from dataclasses import dataclass
import re
from types import MappingProxyType
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
        if (
            not isinstance(self.name, str)
            or re.fullmatch(
                r"[a-z][a-z0-9_-]{0,63}(\.[a-z][a-z0-9_-]{0,63})+",
                self.name,
            )
            is None
            or not isinstance(self.arguments, Mapping)
            or len(self.arguments) > 16
            or any(
                not isinstance(key, str)
                or not isinstance(value, str)
                or not key
                or len(key) > 128
                or len(value) > 256
                for key, value in self.arguments.items()
            )
        ):
            raise ValueError("LLM action proposal is malformed")
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


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
