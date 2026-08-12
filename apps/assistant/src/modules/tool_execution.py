"""Guarded execution boundary between Policy decisions and external adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Callable, Mapping

from apps.assistant.src.modules.policy import (
    PolicyEvaluationResult,
    required_confirmation_for,
)
from apps.assistant.src.modules.tools import (
    ConfirmationPolicy,
    ToolProposal,
    ToolRegistry,
)
from apps.assistant.src.ports.tools import (
    DecisionReplayProtector,
    ToolAdapter,
    ToolAdapterResult,
)


_CONFIRMATION_RANK = {
    ConfirmationPolicy.NONE: 0,
    ConfirmationPolicy.CONTEXTUAL: 1,
    ConfirmationPolicy.EXPLICIT: 2,
}


@dataclass(frozen=True)
class ToolExecutionResult:
    proposal_id: str | None
    executed: bool
    reason_code: str
    output: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.executed, bool):
            raise ValueError("tool execution result executed must be boolean")
        if not isinstance(self.reason_code, str) or not self.reason_code or len(self.reason_code) > 128:
            raise ValueError("tool execution result reason_code is invalid")
        if not isinstance(self.output, Mapping):
            raise ValueError("tool execution result output must be an object")
        object.__setattr__(self, "output", MappingProxyType(dict(self.output)))


class InMemoryDecisionReplayProtector:
    """Process-local replay protection for development and tests.

    Production external writes should use a durable implementation so a Core
    restart cannot make an old Policy decision reusable.
    """

    def __init__(self) -> None:
        self._consumed: set[str] = set()

    def consume(self, decision_id: str) -> bool:
        if not isinstance(decision_id, str) or not decision_id:
            return False
        if decision_id in self._consumed:
            return False
        self._consumed.add(decision_id)
        return True


class GuardedToolExecutor:
    """Execute only a fresh, matching, non-replayed Policy allow decision."""

    def __init__(
        self,
        registry: ToolRegistry,
        adapters: Mapping[str, ToolAdapter],
        *,
        policy_version: str,
        replay_protector: DecisionReplayProtector | None = None,
        max_decision_age: timedelta = timedelta(seconds=30),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(registry, ToolRegistry):
            raise TypeError("registry must be a ToolRegistry")
        if not isinstance(adapters, Mapping):
            raise TypeError("adapters must be a mapping")
        if not isinstance(policy_version, str) or not policy_version or len(policy_version) > 64:
            raise ValueError("executor policy_version is invalid")
        if not isinstance(max_decision_age, timedelta) or max_decision_age <= timedelta(0):
            raise ValueError("max_decision_age must be positive")
        reviewed: dict[str, ToolAdapter] = {}
        for name, adapter in adapters.items():
            if registry.resolve(name) is None:
                raise ValueError("adapter cannot be registered for an unknown tool")
            if not callable(getattr(adapter, "execute", None)):
                raise TypeError("tool adapter must expose execute")
            reviewed[name] = adapter
        self._registry = registry
        self._adapters = MappingProxyType(reviewed)
        self._policy_version = policy_version
        self._replay = replay_protector or InMemoryDecisionReplayProtector()
        self._max_decision_age = max_decision_age
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def execute(
        self,
        proposal: object,
        decision: object,
    ) -> ToolExecutionResult:
        proposal_id = proposal.proposal_id if isinstance(proposal, ToolProposal) else None
        if not isinstance(proposal, ToolProposal):
            return ToolExecutionResult(None, False, "proposal_invalid")
        if not isinstance(decision, PolicyEvaluationResult) or not decision.is_complete_decision:
            return ToolExecutionResult(proposal_id, False, "policy_decision_invalid")
        if not decision.allowed:
            return ToolExecutionResult(proposal_id, False, "policy_denied")
        if decision.proposal_id != proposal.proposal_id:
            return ToolExecutionResult(proposal_id, False, "policy_proposal_mismatch")
        if decision.policy_version != self._policy_version:
            return ToolExecutionResult(proposal_id, False, "policy_version_mismatch")
        definition = self._registry.resolve(proposal.tool_name)
        if definition is None:
            return ToolExecutionResult(proposal_id, False, "tool_not_registered")
        if decision.risk_level is not definition.risk_level:
            return ToolExecutionResult(proposal_id, False, "policy_risk_mismatch")
        minimum_confirmation = required_confirmation_for(definition)
        if (
            decision.confirmation_policy is None
            or _CONFIRMATION_RANK[decision.confirmation_policy]
            < _CONFIRMATION_RANK[minimum_confirmation]
        ):
            return ToolExecutionResult(proposal_id, False, "policy_confirmation_downgrade")
        if (
            decision.confirmation_policy is ConfirmationPolicy.EXPLICIT
            and not decision.confirmation_id
        ):
            return ToolExecutionResult(proposal_id, False, "policy_confirmation_missing")
        if not definition.arguments_are_valid(proposal.arguments):
            return ToolExecutionResult(proposal_id, False, "arguments_invalid")

        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            return ToolExecutionResult(proposal_id, False, "executor_clock_invalid")
        assert decision.decided_at is not None
        age = now - decision.decided_at
        if age < timedelta(0) or age > self._max_decision_age:
            return ToolExecutionResult(proposal_id, False, "policy_decision_stale")

        adapter = self._adapters.get(proposal.tool_name)
        if adapter is None:
            return ToolExecutionResult(proposal_id, False, "adapter_not_configured")
        assert decision.decision_id is not None
        try:
            consumed = self._replay.consume(decision.decision_id)
        except Exception:
            return ToolExecutionResult(proposal_id, False, "replay_protection_unavailable")
        if not consumed:
            return ToolExecutionResult(proposal_id, False, "policy_decision_replayed")

        try:
            adapter_result = adapter.execute(definition, proposal)
        except Exception:
            return ToolExecutionResult(proposal_id, False, "adapter_failure")
        if not isinstance(adapter_result, ToolAdapterResult):
            return ToolExecutionResult(proposal_id, False, "adapter_result_invalid")
        return ToolExecutionResult(
            proposal_id,
            adapter_result.succeeded,
            adapter_result.reason_code,
            adapter_result.output,
        )
