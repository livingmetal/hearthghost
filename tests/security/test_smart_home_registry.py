from __future__ import annotations

from datetime import datetime, timezone
import unittest
from uuid import uuid4

from apps.assistant.src.modules.policy import ToolPolicyEngine
from apps.assistant.src.modules.smart_home_registry import (
    AuthorizedToolRequestContext,
    CapabilityDefinition,
    CapabilityRegistry,
    DeviceAdministrationAction,
    DeviceAdministrationReason,
    DeviceAdministrationRequest,
    DeviceObservation,
    DeviceTrustState,
    SmartHomeDeviceRegistry,
    SmartHomePolicyContextResolver,
    VerifiedDeviceAdministrator,
)
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


NOW = datetime(2026, 8, 13, 1, 0, tzinfo=timezone.utc)


class AllowingDeviceAdministrator:
    def authorize(self, context, action, device_id):
        if context != "trusted-device-admin":
            return None
        return VerifiedDeviceAdministrator("owner", action, device_id)


def capability_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register(
        CapabilityDefinition(
            "home.light.write",
            "Set an approved light state.",
            ToolEffect.PHYSICAL_ACTION,
        )
    )
    registry.register(
        CapabilityDefinition(
            "home.light.read",
            "Read an approved light state.",
            ToolEffect.EXTERNAL_READ,
        )
    )
    return registry


def observation(*capabilities: str) -> DeviceObservation:
    return DeviceObservation(
        adapter_id="homeassistant",
        external_id="light.living_room",
        display_name="Living Room Light",
        area_id="living-room",
        advertised_capabilities=frozenset(capabilities),
    )


def request(action, device_id, revision, capability=None, operation_id=None):
    return DeviceAdministrationRequest(
        operation_id=operation_id or str(uuid4()),
        action=action,
        device_id=device_id,
        expected_revision=revision,
        capability=capability,
    )


class SmartHomeRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.capabilities = capability_registry()
        self.devices = SmartHomeDeviceRegistry(
            self.capabilities,
            authorizer=AllowingDeviceAdministrator(),
            clock=lambda: NOW,
        )
        self.first = self.devices.observe(
            observation("home.light.write", "home.light.read", "vendor.experimental")
        )

    def test_discovery_is_untrusted_and_grants_nothing(self):
        self.assertEqual(self.first.trust_state, DeviceTrustState.UNTRUSTED)
        self.assertEqual(self.first.approved_capabilities, frozenset())
        self.assertIn("vendor.experimental", self.first.advertised_capabilities)
        facts = self.devices.policy_facts(self.first.device_id)
        self.assertFalse(facts.trusted)
        self.assertEqual(facts.approved_capabilities, frozenset())

    def test_administration_requires_action_bound_authority(self):
        denied = self.devices.administer(
            "not-admin",
            request(DeviceAdministrationAction.TRUST_DEVICE, self.first.device_id, 1),
        )
        self.assertFalse(denied.succeeded)
        self.assertEqual(denied.reason, DeviceAdministrationReason.ADMINISTRATION_DENIED)
        self.assertEqual(self.devices.get(self.first.device_id).trust_state, DeviceTrustState.UNTRUSTED)

    def test_trust_does_not_auto_grant_advertised_capabilities(self):
        trusted = self.devices.administer(
            "trusted-device-admin",
            request(DeviceAdministrationAction.TRUST_DEVICE, self.first.device_id, 1),
        )
        self.assertTrue(trusted.succeeded)
        self.assertEqual(trusted.record.trust_state, DeviceTrustState.TRUSTED)
        self.assertEqual(trusted.record.approved_capabilities, frozenset())
        facts = self.devices.policy_facts(self.first.device_id)
        self.assertTrue(facts.trusted)
        self.assertEqual(facts.approved_capabilities, frozenset())

    def test_only_reviewed_advertised_capabilities_can_be_granted(self):
        trusted = self.devices.administer(
            "trusted-device-admin",
            request(DeviceAdministrationAction.TRUST_DEVICE, self.first.device_id, 1),
        ).record
        unknown = self.devices.administer(
            "trusted-device-admin",
            request(
                DeviceAdministrationAction.GRANT_CAPABILITY,
                self.first.device_id,
                trusted.revision,
                "vendor.experimental",
            ),
        )
        self.assertFalse(unknown.succeeded)
        self.assertEqual(unknown.reason, DeviceAdministrationReason.CAPABILITY_NOT_REVIEWED)

        granted = self.devices.administer(
            "trusted-device-admin",
            request(
                DeviceAdministrationAction.GRANT_CAPABILITY,
                self.first.device_id,
                trusted.revision,
                "home.light.write",
            ),
        )
        self.assertTrue(granted.succeeded)
        self.assertEqual(granted.record.approved_capabilities, frozenset({"home.light.write"}))

    def test_rediscovery_never_auto_grants_new_capability_and_removes_vanished_grant(self):
        trusted = self.devices.administer(
            "trusted-device-admin",
            request(DeviceAdministrationAction.TRUST_DEVICE, self.first.device_id, 1),
        ).record
        granted = self.devices.administer(
            "trusted-device-admin",
            request(
                DeviceAdministrationAction.GRANT_CAPABILITY,
                self.first.device_id,
                trusted.revision,
                "home.light.write",
            ),
        ).record
        observed_again = self.devices.observe(
            observation("home.light.write", "home.light.read", "home.light.color")
        )
        self.assertEqual(observed_again.trust_state, DeviceTrustState.TRUSTED)
        self.assertEqual(observed_again.approved_capabilities, frozenset({"home.light.write"}))
        self.assertNotIn("home.light.color", observed_again.approved_capabilities)
        self.assertGreater(observed_again.revision, granted.revision)

        lost_capability = self.devices.observe(observation("home.light.read"))
        self.assertEqual(lost_capability.approved_capabilities, frozenset())

    def test_revoke_is_sticky_across_rediscovery(self):
        trusted = self.devices.administer(
            "trusted-device-admin",
            request(DeviceAdministrationAction.TRUST_DEVICE, self.first.device_id, 1),
        ).record
        revoked = self.devices.administer(
            "trusted-device-admin",
            request(DeviceAdministrationAction.REVOKE_DEVICE, self.first.device_id, trusted.revision),
        )
        self.assertEqual(revoked.record.trust_state, DeviceTrustState.REVOKED)
        rediscovered = self.devices.observe(observation("home.light.write"))
        self.assertEqual(rediscovered.trust_state, DeviceTrustState.REVOKED)
        self.assertEqual(rediscovered.approved_capabilities, frozenset())

        retrust = self.devices.administer(
            "trusted-device-admin",
            request(DeviceAdministrationAction.TRUST_DEVICE, self.first.device_id, rediscovered.revision),
        )
        self.assertFalse(retrust.succeeded)
        self.assertEqual(retrust.reason, DeviceAdministrationReason.DEVICE_REVOKED)

    def test_revision_and_idempotency_guards_prevent_ambiguous_admin_mutation(self):
        operation_id = str(uuid4())
        mutation = request(
            DeviceAdministrationAction.TRUST_DEVICE,
            self.first.device_id,
            1,
            operation_id=operation_id,
        )
        first = self.devices.administer("trusted-device-admin", mutation)
        replay = self.devices.administer("trusted-device-admin", mutation)
        self.assertTrue(first.changed)
        self.assertTrue(replay.succeeded)
        self.assertFalse(replay.changed)
        self.assertEqual(replay.reason, DeviceAdministrationReason.IDEMPOTENT_REPLAY)

        conflict = self.devices.administer(
            "trusted-device-admin",
            request(
                DeviceAdministrationAction.REVOKE_DEVICE,
                self.first.device_id,
                1,
                operation_id=operation_id,
            ),
        )
        self.assertEqual(conflict.reason, DeviceAdministrationReason.IDEMPOTENCY_CONFLICT)

        stale_revision = self.devices.administer(
            "trusted-device-admin",
            request(DeviceAdministrationAction.REVOKE_DEVICE, self.first.device_id, 1),
        )
        self.assertEqual(stale_revision.reason, DeviceAdministrationReason.REVISION_CONFLICT)

    def test_registry_facts_gate_hg053_tool_policy_end_to_end(self):
        tool_registry = ToolRegistry()
        tool_registry.register(
            ToolDefinition(
                name="home.light.set",
                description="Set a reviewed living-room light.",
                effect=ToolEffect.PHYSICAL_ACTION,
                risk_level=ToolRiskLevel.LOW,
                required_context=ToolRequiredContext.EXPLICIT_USER_REQUEST,
                required_roles=frozenset({ActorRole.HOUSEHOLD_MEMBER}),
                confirmation_policy=ConfirmationPolicy.CONTEXTUAL,
                audit_level=AuditLevel.METADATA,
                arguments_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["device_id", "state"],
                    "properties": {
                        "device_id": {"type": "string"},
                        "state": {"type": "string", "enum": ["on", "off"]},
                    },
                },
                allowed_capabilities=frozenset({"home.light.write"}),
                allowed_devices=frozenset({self.first.device_id}),
            )
        )
        policy = ToolPolicyEngine(tool_registry, clock=lambda: NOW)
        resolver = SmartHomePolicyContextResolver(self.devices)
        proposal = ToolProposal.from_llm_action(
            ProposedAction(
                "home.light.set",
                {"device_id": self.first.device_id, "state": "on"},
            ),
            request_id="req-1",
            session_id="session-1",
            node_id="phone-1",
            actor_id="owner",
            explicit_user_request=True,
            now=NOW,
        )
        authorized = AuthorizedToolRequestContext(
            request_id="req-1",
            actor_id="owner",
            roles=frozenset({ActorRole.HOUSEHOLD_MEMBER}),
            explicit_user_request=True,
            active_session=True,
            session_id="session-1",
            node_id="phone-1",
        )

        discovered_context = resolver.resolve(proposal, authorized)
        self.assertFalse(policy.evaluate(proposal, discovered_context).allowed)

        trusted = self.devices.administer(
            "trusted-device-admin",
            request(DeviceAdministrationAction.TRUST_DEVICE, self.first.device_id, 1),
        ).record
        trusted_context = resolver.resolve(proposal, authorized)
        self.assertFalse(policy.evaluate(proposal, trusted_context).allowed)

        granted = self.devices.administer(
            "trusted-device-admin",
            request(
                DeviceAdministrationAction.GRANT_CAPABILITY,
                self.first.device_id,
                trusted.revision,
                "home.light.write",
            ),
        ).record
        allowed_context = resolver.resolve(proposal, authorized)
        allowed = policy.evaluate(proposal, allowed_context)
        self.assertTrue(allowed.allowed)

        revoked = self.devices.administer(
            "trusted-device-admin",
            request(DeviceAdministrationAction.REVOKE_DEVICE, self.first.device_id, granted.revision),
        )
        self.assertTrue(revoked.succeeded)
        revoked_context = resolver.resolve(proposal, authorized)
        self.assertFalse(policy.evaluate(proposal, revoked_context).allowed)


if __name__ == "__main__":
    unittest.main()
