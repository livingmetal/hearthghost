"""Application port for fail-closed Policy evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from apps.assistant.src.modules.policy import PolicyEvaluationResult


class PolicyBoundary(Protocol):
    """Evaluates a proposal without executing it or mutating Hard Policy."""

    def evaluate(self, proposal: object) -> PolicyEvaluationResult:
        """Return an explicit allow/deny result; missing results are never allow."""
