from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from apps.assistant.src.modules.policy import (
    PolicyEvaluationContext,
    ToolPolicyEngine,
    UnconfiguredPolicyBoundary,
)
from apps.assistant.src.modules.tool_execution import GuardedToolExecutor
from apps.assistant.src.modules.tools import (
    ActorRole,
    AuditLevel,
    ConfirmationPolicy,
    ToolDefinition,
    ToolEffect,
    ToolProposal,
    ToolRegistry,
    ToolRequiredContext,
    ToolRiskLevel,
)
from apps.assistant.src.ports.llm import ProposedAction
from apps.assistant.src.ports.tools import ToolAdapterResult


NOW = datetime(2026, 8, 13, 0, 0, tzinfo=timezone.utc)
LIGHT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["device_id", "state"],
    "properties": {
        "device_id": {"type": "string", "minLength": 1, "maxLength": 128},
        "state": {"type": "string", "enum": ["on", "off"]},
    },
}


def light_definition(
    *,
    risk: ToolRiskLevel = ToolRiskLevel.LOW,
    confirmation: ConfirmationPolicy = ConfirmationPolicy.CONTEXTUAL,
) -> ToolDefinition:
    return ToolDefinition(
        name="home.light.set",
        description="Set an approved light on or off.",
        effect=ToolEffect.PHYSICAL_ACTION,
        risk_level=risk,
        required_context=ToolRequiredContext.EXPLICIT_USER_REQUEST,
        required_roles=frozenset({ActorRole.ADMINISTRATOR, ActorRole.HOUSEHOLD_MEMBER}),
        confirmation_policy=confirmation,
        audit_level=AuditLevel.SECURITY if risk is ToolRiskLevel.CRITICAL else AuditLevel.METADATA,
        arguments_schema=LIGHT_SCHEMA,
        allowed_capabilities=frozenset({"home.light.write"}),
        allowed_devices=frozenset({"living-room-light"}),
    )


def proposal(
    *,
    name: str = "home.light.set",
    arguments: dict[str, str] | None = None,
    explicit: bool = True,
    confirmation_id: str | None = None,
    actor_id: str = "owner",
) -> ToolProposal:
    return ToolProposal.from_llm_action(
        ProposedAction(
            name,
            arguments or {"device_id": "living-room-light", "state": "on"},
        ),
        request_id="request-1",
        session_id="conversation-1",
        node_id="phone-1",
        actor_id=actor_id,
        explicit_user_request=explicit,
        confirmation_id=confirmation_id,
        now=NOW,
    )


def context(
    *,
    explicit: bool = True,
    roles: frozenset[ActorRole] = frozenset({ActorRole.HOUSEHOLD_MEMBER}),
    trusted_devices: frozenset[str] = frozenset({"living-room-light"}),
    capabilities: frozenset[str] = frozenset({"home.light.write"}),
    confirmations: frozenset[str] = frozenset(),
    actor_id: str = "owner",
) -> PolicyEvaluationContext:
    return PolicyEvaluationContext(
        request_id="request-1",
        actor_id=actor_id,
        roles=roles,
        explicit_user_request=explicit,
        active_session=True,
        session_id="conversation-1",
        node_id="phone-1",
        granted_capabilities=capabilities,
        trusted_device_ids=trusted_devices,
        confirmed_confirmation_ids=confirmations,
    )


class RecordingLightAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, definition, candidate):
        self.calls += 1
        return ToolAdapterResult(True, "light_updated", {"state": candidate.arguments["state"]})


class ToolPolicyExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ToolRegistry()
        self.registry.register(light_definition())
        self.policy = ToolPolicyEngine(self.registry, clock=lambda: NOW)

    def test_default_unconfigured_policy_remains_deny_only(self):
        result = UnconfiguredPolicyBoundary().evaluate(proposal())
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, "policy_not_configured")
        self.assertFalse(result.is_complete_decision)

    def test_registry_rejects_duplicates_and_unsupported_schema_rules(self):
        with self.assertRaisesRegex(ValueError, "already registered"):
            self.registry.register(light_definition())
        with self.assertRaisesRegex(ValueError, "unsupported tool property schema keyword"):
            ToolDefinition(
                name="home.light.unsafe",
                description="Unsafe schema test.",
                effect=ToolEffect.EXTERNAL_WRITE,
                risk_level=ToolRiskLevel.LOW,
                required_context=ToolRequiredContext.EXPLICIT_USER_REQUEST,
                required_roles=frozenset({ActorRole.ADMINISTRATOR}),
                confirmation_policy=ConfirmationPolicy.NONE,
                audit_level=AuditLevel.METADATA,
                arguments_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["command"],
                    "properties": {"command": {"type": "string", "default": "allow-all"}},
                },
            )

    def test_llm_proposal_remains_pending_and_cannot_supply_policy_metadata(self):
        candidate = proposal()
        self.assertEqual(candidate.authorization_status, "pending_policy")
        self.assertFalse(hasattr(candidate, "risk_level"))
        self.assertFalse(hasattr(candidate, "allowed"))
        with self.assertRaisesRegex(ValueError, "pending v1.0"):
            replace(candidate, authorization_status="allow")

    def test_unknown_tool_fails_closed_as_critical(self):
        decision = self.policy.evaluate(proposal(name="home.light.delete"), context())
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "tool_not_registered")
        self.assertEqual(decision.risk_level, ToolRiskLevel.CRITICAL)
        self.assertEqual(decision.confirmation_policy, ConfirmationPolicy.EXPLICIT)

    def test_policy_denies_invalid_arguments_role_capability_and_device(self):
        invalid_arguments = self.policy.evaluate(
            proposal(arguments={"device_id": "living-room-light", "state": "on", "shell": "rm"}),
            context(),
        )
        self.assertEqual(invalid_arguments.reason_code, "arguments_invalid")

        wrong_role = self.policy.evaluate(
            proposal(),
            context(roles=frozenset({ActorRole.GUEST})),
        )
        self.assertEqual(wrong_role.reason_code, "role_not_authorized")

        missing_capability = self.policy.evaluate(proposal(), context(capabilities=frozenset()))
        self.assertEqual(missing_capability.reason_code, "capability_not_granted")

        untrusted_device = self.policy.evaluate(proposal(), context(trusted_devices=frozenset()))
        self.assertEqual(untrusted_device.reason_code, "device_untrusted")

    def test_contextual_confirmation_requires_same_explicit_user_turn(self):
        decision = self.policy.evaluate(proposal(explicit=False), context(explicit=False))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "explicit_user_request_required")

        allowed = self.policy.evaluate(proposal(explicit=True), context(explicit=True))
        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.confirmation_policy, ConfirmationPolicy.CONTEXTUAL)

    def test_high_risk_runtime_floor_requires_explicit_confirmation(self):
        registry = ToolRegistry()
        registry.register(
            light_definition(
                risk=ToolRiskLevel.HIGH,
                confirmation=ConfirmationPolicy.CONTEXTUAL,
            )
        )
        policy = ToolPolicyEngine(registry, clock=lambda: NOW)
        missing = policy.evaluate(proposal(), context())
        self.assertFalse(missing.allowed)
        self.assertEqual(missing.reason_code, "explicit_confirmation_required")
        self.assertEqual(missing.confirmation_policy, ConfirmationPolicy.EXPLICIT)

        confirmed = policy.evaluate(
            proposal(confirmation_id="confirm-1"),
            context(confirmations=frozenset({"confirm-1"})),
        )
        self.assertTrue(confirmed.allowed)
        self.assertEqual(confirmed.confirmation_id, "confirm-1")

    def test_policy_context_is_bound_to_actor_and_request(self):
        actor_mismatch = self.policy.evaluate(proposal(actor_id="owner"), context(actor_id="other"))
        self.assertEqual(actor_mismatch.reason_code, "actor_context_mismatch")
        request_mismatch = self.policy.evaluate(
            proposal(),
            replace(context(), request_id="request-2"),
        )
        self.assertEqual(request_mismatch.reason_code, "request_context_mismatch")

    def test_executor_calls_adapter_only_for_fresh_matching_allow_once(self):
        adapter = RecordingLightAdapter()
        executor = GuardedToolExecutor(
            self.registry,
            {"home.light.set": adapter},
            policy_version=self.policy.policy_version,
            clock=lambda: NOW,
        )
        candidate = proposal()
        decision = self.policy.evaluate(candidate, context())
        first = executor.execute(candidate, decision)
        self.assertTrue(first.executed)
        self.assertEqual(first.reason_code, "light_updated")
        self.assertEqual(adapter.calls, 1)

        replay = executor.execute(candidate, decision)
        self.assertFalse(replay.executed)
        self.assertEqual(replay.reason_code, "policy_decision_replayed")
        self.assertEqual(adapter.calls, 1)

    def test_executor_rejects_cross_proposal_stale_and_downgraded_decisions(self):
        adapter = RecordingLightAdapter()
        candidate = proposal()
        decision = self.policy.evaluate(candidate, context())

        mismatch_executor = GuardedToolExecutor(
            self.registry,
            {"home.light.set": adapter},
            policy_version=self.policy.policy_version,
            clock=lambda: NOW,
        )
        mismatch = mismatch_executor.execute(proposal(), decision)
        self.assertEqual(mismatch.reason_code, "policy_proposal_mismatch")

        stale_executor = GuardedToolExecutor(
            self.registry,
            {"home.light.set": adapter},
            policy_version=self.policy.policy_version,
            clock=lambda: NOW + timedelta(seconds=31),
        )
        stale = stale_executor.execute(candidate, decision)
        self.assertEqual(stale.reason_code, "policy_decision_stale")

        downgraded = replace(decision, confirmation_policy=ConfirmationPolicy.NONE)
        downgrade_executor = GuardedToolExecutor(
            self.registry,
            {"home.light.set": adapter},
            policy_version=self.policy.policy_version,
            clock=lambda: NOW,
        )
        downgrade = downgrade_executor.execute(candidate, downgraded)
        self.assertEqual(downgrade.reason_code, "policy_confirmation_downgrade")
        self.assertEqual(adapter.calls, 0)

    def test_policy_deny_never_calls_adapter(self):
        adapter = RecordingLightAdapter()
        executor = GuardedToolExecutor(
            self.registry,
            {"home.light.set": adapter},
            policy_version=self.policy.policy_version,
            clock=lambda: NOW,
        )
        candidate = proposal(explicit=False)
        denied = self.policy.evaluate(candidate, context(explicit=False))
        result = executor.execute(candidate, denied)
        self.assertFalse(result.executed)
        self.assertEqual(result.reason_code, "policy_denied")
        self.assertEqual(adapter.calls, 0)


if __name__ == "__main__":
    unittest.main()
