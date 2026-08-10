"""Minimal fail-closed Policy boundary for Core composition.

HG-005 does not implement policy rules or Tool execution. The initial boundary
therefore returns a typed denial for every proposal instead of treating the
absence of a configured Policy engine as permission.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyEvaluationResult:
    allowed: bool
    reason_code: str
    policy_version: str | None = None


class UnconfiguredPolicyBoundary:
    """Deny-only boundary used until reviewed policy rules are configured."""

    def evaluate(self, proposal: object) -> PolicyEvaluationResult:
        return PolicyEvaluationResult(
            allowed=False,
            reason_code="policy_not_configured",
        )
