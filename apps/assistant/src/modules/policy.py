"""Fail-closed Hard Policy evaluation for inert Tool proposals.

The default Core composition still uses :class:`UnconfiguredPolicyBoundary`.
`ToolPolicyEngine` is an opt-in reviewed boundary for registered tools and never
executes an adapter itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from apps.assistant.src.modules.tools import (
    ActorRole,
    ConfirmationPolicy,
    ToolDefinition,
    ToolEffect,
    ToolProposal,
    ToolRegistry,
    ToolRequiredContext,
    ToolRiskLevel,
)


@dataclass(frozen=True)
class PolicyEvaluationResult:
    allowed: bool
    reason_code: str
    policy_version: str | None = None
    decision_id: str | None = None
    proposal_id: str | None = None
    risk_level: ToolRiskLevel | None = None
    confirmation_policy: ConfirmationPolicy | None = None
    confirmation_id: str | None = None
    decided_at: datetime | None = None
    contract_version: str = "1.0"

    @property
    def is_complete_decision(self) -> bool:
        return (
            self.decision_id is not None
            and self.proposal_id is not None
            and self.risk_level is not None
            and self.confirmation_policy is not None
            and self.policy_version is not None
            and self.decided_at is not None
        )


@dataclass(frozen=True)
class PolicyEvaluationContext:
    """Trusted server-side facts that an LLM Tool proposal cannot grant itself."""

    request_id: str
    actor_id: str
    roles: frozenset[ActorRole]
    explicit_user_request: bool
    active_session: bool
    session_id: str | None = None
    node_id: str | None = None
    administrator_action: bool = False
    granted_capabilities: frozenset[str] = frozenset()
    trusted_device_ids: frozenset[str] = frozenset()
    confirmed_confirmation_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id or len(self.request_id) > 128:
            raise ValueError("policy request_id is invalid")
        if not isinstance(self.actor_id, str) or not self.actor_id or len(self.actor_id) > 128:
            raise ValueError("policy actor_id is invalid")
        if not self.roles or not all(isinstance(role, ActorRole) for role in self.roles):
            raise ValueError("policy context requires at least one valid actor role")
        if not isinstance(self.explicit_user_request, bool) or not isinstance(self.active_session, bool):
            raise ValueError("policy context booleans are invalid")
        if not isinstance(self.administrator_action, bool):
            raise ValueError("administrator_action must be boolean")
        for value in self.granted_capabilities:
            if not isinstance(value, str) or not value:
                raise ValueError("policy capability grant is invalid")
        for values, label in (
            (self.trusted_device_ids, "trusted device id"),
            (self.confirmed_confirmation_ids, "confirmation id"),
        ):
            if any(not isinstance(value, str) or not value or len(value) > 128 for value in values):
                raise ValueError(f"policy {label} is invalid")


_CONFIRMATION_RANK = {
    ConfirmationPolicy.NONE: 0,
    ConfirmationPolicy.CONTEXTUAL: 1,
    ConfirmationPolicy.EXPLICIT: 2,
}


def required_confirmation_for(definition: ToolDefinition) -> ConfirmationPolicy:
    """Apply runtime floors even if a reviewed definition is accidentally weaker."""

    required = definition.confirmation_policy
    floor = ConfirmationPolicy.NONE
    if definition.risk_level is ToolRiskLevel.MEDIUM:
        floor = ConfirmationPolicy.CONTEXTUAL
    elif definition.risk_level in {ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL}:
        floor = ConfirmationPolicy.EXPLICIT
    if definition.effect is ToolEffect.PHYSICAL_ACTION:
        floor = max(
            (floor, ConfirmationPolicy.CONTEXTUAL),
            key=lambda value: _CONFIRMATION_RANK[value],
        )
    return max((required, floor), key=lambda value: _CONFIRMATION_RANK[value])


class UnconfiguredPolicyBoundary:
    """Deny-only boundary used until reviewed policy rules are configured."""

    def evaluate(
        self,
        proposal: object,
        context: object | None = None,
    ) -> PolicyEvaluationResult:
        return PolicyEvaluationResult(
            allowed=False,
            reason_code="policy_not_configured",
        )


class ToolPolicyEngine:
    """Evaluate registered tools against trusted context without executing them."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        policy_version: str = "tool-hard-policy-v1",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(registry, ToolRegistry):
            raise TypeError("registry must be a ToolRegistry")
        if not isinstance(policy_version, str) or not policy_version or len(policy_version) > 64:
            raise ValueError("policy_version is invalid")
        self._registry = registry
        self._policy_version = policy_version
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def policy_version(self) -> str:
        return self._policy_version

    def evaluate(
        self,
        proposal: object,
        context: object | None = None,
    ) -> PolicyEvaluationResult:
        if not isinstance(proposal, ToolProposal):
            return PolicyEvaluationResult(False, "proposal_invalid", self._policy_version)
        definition = self._registry.resolve(proposal.tool_name)
        if definition is None:
            return self._decision(
                proposal,
                allowed=False,
                reason="tool_not_registered",
                risk=ToolRiskLevel.CRITICAL,
                confirmation=ConfirmationPolicy.EXPLICIT,
            )
        required_confirmation = required_confirmation_for(definition)
        if not isinstance(context, PolicyEvaluationContext):
            return self._decision_for_definition(
                proposal, definition, required_confirmation, False, "trusted_context_missing"
            )
        reason = self._denial_reason(proposal, definition, context, required_confirmation)
        if reason is not None:
            return self._decision_for_definition(
                proposal, definition, required_confirmation, False, reason
            )
        confirmation_id = (
            proposal.context.confirmation_id
            if required_confirmation is ConfirmationPolicy.EXPLICIT
            else None
        )
        return self._decision(
            proposal,
            allowed=True,
            reason="policy_allow",
            risk=definition.risk_level,
            confirmation=required_confirmation,
            confirmation_id=confirmation_id,
        )

    def _denial_reason(
        self,
        proposal: ToolProposal,
        definition: ToolDefinition,
        context: PolicyEvaluationContext,
        confirmation: ConfirmationPolicy,
    ) -> str | None:
        if proposal.context.request_id != context.request_id:
            return "request_context_mismatch"
        if proposal.context.actor_id is None or proposal.context.actor_id != context.actor_id:
            return "actor_context_mismatch"
        if proposal.context.session_id is not None and proposal.context.session_id != context.session_id:
            return "session_context_mismatch"
        if proposal.context.node_id is not None and proposal.context.node_id != context.node_id:
            return "node_context_mismatch"
        if not definition.required_roles.intersection(context.roles):
            return "role_not_authorized"
        if not definition.arguments_are_valid(proposal.arguments):
            return "arguments_invalid"
        if not definition.allowed_capabilities.issubset(context.granted_capabilities):
            return "capability_not_granted"

        required_context = definition.required_context
        if required_context is ToolRequiredContext.ACTIVE_SESSION:
            if not context.active_session or proposal.context.session_id is None:
                return "active_session_required"
        elif required_context is ToolRequiredContext.EXPLICIT_USER_REQUEST:
            if not proposal.context.explicit_user_request or not context.explicit_user_request:
                return "explicit_user_request_required"
        elif required_context is ToolRequiredContext.ADMINISTRATOR_ACTION:
            if (
                not context.administrator_action
                or ActorRole.ADMINISTRATOR not in context.roles
            ):
                return "administrator_action_required"

        device_id = proposal.arguments.get("device_id")
        if definition.allowed_devices:
            if not isinstance(device_id, str):
                return "device_id_required"
            if device_id not in definition.allowed_devices:
                return "device_not_allowed"
        if device_id is not None and definition.effect in {
            ToolEffect.EXTERNAL_READ,
            ToolEffect.EXTERNAL_WRITE,
            ToolEffect.PHYSICAL_ACTION,
        }:
            if not isinstance(device_id, str) or device_id not in context.trusted_device_ids:
                return "device_untrusted"

        contextual_confirmation = (
            proposal.context.explicit_user_request
            and context.explicit_user_request
            and proposal.context.request_id == context.request_id
        )
        if confirmation is ConfirmationPolicy.CONTEXTUAL and not contextual_confirmation:
            return "contextual_confirmation_required"
        if confirmation is ConfirmationPolicy.EXPLICIT:
            confirmation_id = proposal.context.confirmation_id
            if not contextual_confirmation:
                return "explicit_user_request_required"
            if (
                confirmation_id is None
                or confirmation_id not in context.confirmed_confirmation_ids
            ):
                return "explicit_confirmation_required"
        return None

    def _decision_for_definition(
        self,
        proposal: ToolProposal,
        definition: ToolDefinition,
        confirmation: ConfirmationPolicy,
        allowed: bool,
        reason: str,
    ) -> PolicyEvaluationResult:
        return self._decision(
            proposal,
            allowed=allowed,
            reason=reason,
            risk=definition.risk_level,
            confirmation=confirmation,
        )

    def _decision(
        self,
        proposal: ToolProposal,
        *,
        allowed: bool,
        reason: str,
        risk: ToolRiskLevel,
        confirmation: ConfirmationPolicy,
        confirmation_id: str | None = None,
    ) -> PolicyEvaluationResult:
        decided_at = self._clock()
        if not isinstance(decided_at, datetime) or decided_at.tzinfo is None:
            raise RuntimeError("Policy clock must return a timezone-aware datetime")
        return PolicyEvaluationResult(
            allowed=allowed,
            reason_code=reason,
            policy_version=self._policy_version,
            decision_id=str(uuid4()),
            proposal_id=proposal.proposal_id,
            risk_level=risk,
            confirmation_policy=confirmation,
            confirmation_id=confirmation_id,
            decided_at=decided_at,
        )
