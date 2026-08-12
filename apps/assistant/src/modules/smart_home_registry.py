"""Fail-closed Smart Home Device and Capability Registry foundation.

Discovery is observation, never trust.  Administrator approval and capability
selection are separate mutations, and Policy receives only the resulting
trusted facts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import re
from threading import RLock
from typing import Protocol
from uuid import UUID

from apps.assistant.src.modules.policy import PolicyEvaluationContext
from apps.assistant.src.modules.tools import ActorRole, ToolEffect, ToolProposal


_COMPONENT = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
_EXTERNAL_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,95}")
_CAPABILITY = re.compile(r"[a-z][a-z0-9_-]{0,63}(?:\.[a-z][a-z0-9_-]{0,63})*")
_AREA = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


class DeviceTrustState(str, Enum):
    UNTRUSTED = "untrusted"
    TRUSTED = "trusted"
    REVOKED = "revoked"


class DeviceAdministrationAction(str, Enum):
    TRUST_DEVICE = "device.trust"
    GRANT_CAPABILITY = "device.capability.grant"
    REVOKE_CAPABILITY = "device.capability.revoke"
    REVOKE_DEVICE = "device.revoke"


class DeviceAdministrationReason(str, Enum):
    APPLIED = "applied"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    NO_CHANGE = "no_change"
    MALFORMED_REQUEST = "malformed_request"
    ADMINISTRATION_DENIED = "administration_denied"
    AMBIGUOUS_AUTHORIZATION = "ambiguous_authorization"
    DEVICE_NOT_FOUND = "device_not_found"
    DEVICE_REVOKED = "device_revoked"
    CAPABILITY_NOT_ADVERTISED = "capability_not_advertised"
    CAPABILITY_NOT_REVIEWED = "capability_not_reviewed"
    DEVICE_NOT_TRUSTED = "device_not_trusted"
    REVISION_CONFLICT = "revision_conflict"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"


@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    description: str
    effect: ToolEffect

    def __post_init__(self) -> None:
        if _CAPABILITY.fullmatch(self.name) is None:
            raise ValueError("capability name is invalid")
        if not isinstance(self.description, str) or not self.description or len(self.description) > 512:
            raise ValueError("capability description is invalid")
        if not isinstance(self.effect, ToolEffect):
            raise ValueError("capability effect is invalid")


class CapabilityRegistry:
    """Reviewed capability catalog, distinct from device advertisements."""

    def __init__(self) -> None:
        self._definitions: dict[str, CapabilityDefinition] = {}

    def register(self, definition: CapabilityDefinition) -> None:
        if not isinstance(definition, CapabilityDefinition):
            raise TypeError("only CapabilityDefinition values can be registered")
        if definition.name in self._definitions:
            raise ValueError("capability is already registered")
        self._definitions[definition.name] = definition

    def resolve(self, name: str) -> CapabilityDefinition | None:
        return self._definitions.get(name)

    def snapshot(self) -> tuple[CapabilityDefinition, ...]:
        return tuple(self._definitions[name] for name in sorted(self._definitions))


@dataclass(frozen=True)
class DeviceObservation:
    adapter_id: str
    external_id: str
    display_name: str
    advertised_capabilities: frozenset[str]
    area_id: str | None = None

    def __post_init__(self) -> None:
        if _COMPONENT.fullmatch(self.adapter_id) is None:
            raise ValueError("adapter_id is invalid")
        if _EXTERNAL_ID.fullmatch(self.external_id) is None:
            raise ValueError("external_id is invalid")
        if not isinstance(self.display_name, str) or not self.display_name.strip() or len(self.display_name) > 128:
            raise ValueError("display_name is invalid")
        if self.area_id is not None and _AREA.fullmatch(self.area_id) is None:
            raise ValueError("area_id is invalid")
        if len(self.advertised_capabilities) > 64 or any(
            _CAPABILITY.fullmatch(value) is None for value in self.advertised_capabilities
        ):
            raise ValueError("advertised capability set is invalid")
        object.__setattr__(self, "advertised_capabilities", frozenset(self.advertised_capabilities))

    @property
    def device_id(self) -> str:
        value = f"{self.adapter_id}.{self.external_id}"
        if len(value) > 128:
            raise ValueError("derived device_id exceeds the supported bound")
        return value


@dataclass(frozen=True)
class SmartHomeDeviceRecord:
    device_id: str
    adapter_id: str
    external_id: str
    display_name: str
    area_id: str | None
    trust_state: DeviceTrustState
    advertised_capabilities: frozenset[str]
    approved_capabilities: frozenset[str]
    revision: int
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True)
class DevicePolicyFacts:
    device_id: str
    trusted: bool
    approved_capabilities: frozenset[str]
    revision: int


@dataclass(frozen=True)
class VerifiedDeviceAdministrator:
    actor_id: str
    action: DeviceAdministrationAction
    device_id: str


class DeviceAdministratorAuthorizer(Protocol):
    def authorize(
        self,
        context: object,
        action: DeviceAdministrationAction,
        device_id: str,
    ) -> VerifiedDeviceAdministrator | None:
        """Return action-bound administrator evidence or None."""


class DenyingDeviceAdministratorAuthorizer:
    def authorize(
        self,
        context: object,
        action: DeviceAdministrationAction,
        device_id: str,
    ) -> VerifiedDeviceAdministrator | None:
        return None


@dataclass(frozen=True)
class DeviceAdministrationRequest:
    operation_id: str
    action: DeviceAdministrationAction
    device_id: str
    expected_revision: int
    capability: str | None = None

    def __post_init__(self) -> None:
        try:
            UUID(self.operation_id)
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError("operation_id must be a UUID") from error
        if not isinstance(self.action, DeviceAdministrationAction):
            raise ValueError("device administration action is invalid")
        if not isinstance(self.device_id, str) or not self.device_id or len(self.device_id) > 128:
            raise ValueError("device_id is invalid")
        if not isinstance(self.expected_revision, int) or isinstance(self.expected_revision, bool) or self.expected_revision < 0:
            raise ValueError("expected_revision is invalid")
        if self.capability is not None and _CAPABILITY.fullmatch(self.capability) is None:
            raise ValueError("capability is invalid")


@dataclass(frozen=True)
class DeviceAdministrationResult:
    succeeded: bool
    changed: bool
    reason: DeviceAdministrationReason
    record: SmartHomeDeviceRecord | None = None


@dataclass(frozen=True)
class _AppliedOperation:
    request: DeviceAdministrationRequest
    record: SmartHomeDeviceRecord


class SmartHomeDeviceRegistry:
    """In-memory registry foundation with explicit administrator mutation boundary."""

    def __init__(
        self,
        capabilities: CapabilityRegistry,
        *,
        authorizer: DeviceAdministratorAuthorizer | None = None,
        clock=None,
    ) -> None:
        if not isinstance(capabilities, CapabilityRegistry):
            raise TypeError("capabilities must be a CapabilityRegistry")
        self._capabilities = capabilities
        self._authorizer = authorizer or DenyingDeviceAdministratorAuthorizer()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._records: dict[str, SmartHomeDeviceRecord] = {}
        self._operations: dict[str, _AppliedOperation] = {}
        self._lock = RLock()

    def observe(self, observation: DeviceObservation) -> SmartHomeDeviceRecord:
        if not isinstance(observation, DeviceObservation):
            raise TypeError("observation must be a DeviceObservation")
        now = self._trusted_now()
        device_id = observation.device_id
        with self._lock:
            prior = self._records.get(device_id)
            if prior is None:
                record = SmartHomeDeviceRecord(
                    device_id=device_id,
                    adapter_id=observation.adapter_id,
                    external_id=observation.external_id,
                    display_name=observation.display_name.strip(),
                    area_id=observation.area_id,
                    trust_state=DeviceTrustState.UNTRUSTED,
                    advertised_capabilities=observation.advertised_capabilities,
                    approved_capabilities=frozenset(),
                    revision=1,
                    first_seen_at=now,
                    last_seen_at=now,
                )
            else:
                # Discovery can safely remove an approval when a capability vanishes,
                # but it can never add trust or grants.
                still_advertised = prior.approved_capabilities.intersection(
                    observation.advertised_capabilities
                )
                record = replace(
                    prior,
                    display_name=observation.display_name.strip(),
                    area_id=observation.area_id,
                    advertised_capabilities=observation.advertised_capabilities,
                    approved_capabilities=frozenset(still_advertised),
                    revision=prior.revision + 1,
                    last_seen_at=now,
                )
            self._records[device_id] = record
            return record

    def get(self, device_id: str) -> SmartHomeDeviceRecord | None:
        with self._lock:
            return self._records.get(device_id)

    def snapshot(self) -> tuple[SmartHomeDeviceRecord, ...]:
        with self._lock:
            return tuple(self._records[key] for key in sorted(self._records))

    def policy_facts(self, device_id: str) -> DevicePolicyFacts:
        with self._lock:
            record = self._records.get(device_id)
            if record is None:
                return DevicePolicyFacts(device_id, False, frozenset(), 0)
            trusted = record.trust_state is DeviceTrustState.TRUSTED
            return DevicePolicyFacts(
                device_id,
                trusted,
                record.approved_capabilities if trusted else frozenset(),
                record.revision,
            )

    def administer(
        self,
        context: object,
        request: DeviceAdministrationRequest,
    ) -> DeviceAdministrationResult:
        if not isinstance(request, DeviceAdministrationRequest):
            return DeviceAdministrationResult(False, False, DeviceAdministrationReason.MALFORMED_REQUEST)
        try:
            authorization = self._authorizer.authorize(context, request.action, request.device_id)
        except Exception:
            return DeviceAdministrationResult(False, False, DeviceAdministrationReason.ADMINISTRATION_DENIED)
        if (
            not isinstance(authorization, VerifiedDeviceAdministrator)
            or not authorization.actor_id
            or authorization.action is not request.action
            or authorization.device_id != request.device_id
        ):
            reason = (
                DeviceAdministrationReason.ADMINISTRATION_DENIED
                if authorization is None
                else DeviceAdministrationReason.AMBIGUOUS_AUTHORIZATION
            )
            return DeviceAdministrationResult(False, False, reason)

        with self._lock:
            prior_operation = self._operations.get(request.operation_id)
            if prior_operation is not None:
                if prior_operation.request == request:
                    return DeviceAdministrationResult(
                        True,
                        False,
                        DeviceAdministrationReason.IDEMPOTENT_REPLAY,
                        prior_operation.record,
                    )
                return DeviceAdministrationResult(
                    False, False, DeviceAdministrationReason.IDEMPOTENCY_CONFLICT
                )
            current = self._records.get(request.device_id)
            if current is None:
                return DeviceAdministrationResult(
                    False, False, DeviceAdministrationReason.DEVICE_NOT_FOUND
                )
            if current.revision != request.expected_revision:
                return DeviceAdministrationResult(
                    False, False, DeviceAdministrationReason.REVISION_CONFLICT
                )
            candidate, reason = self._candidate(current, request)
            if candidate is None:
                if reason is DeviceAdministrationReason.NO_CHANGE:
                    return DeviceAdministrationResult(True, False, reason, current)
                return DeviceAdministrationResult(False, False, reason)
            updated = replace(candidate, revision=current.revision + 1, last_seen_at=self._trusted_now())
            self._records[request.device_id] = updated
            self._operations[request.operation_id] = _AppliedOperation(request, updated)
            return DeviceAdministrationResult(
                True, True, DeviceAdministrationReason.APPLIED, updated
            )

    def _candidate(
        self,
        current: SmartHomeDeviceRecord,
        request: DeviceAdministrationRequest,
    ) -> tuple[SmartHomeDeviceRecord | None, DeviceAdministrationReason]:
        if current.trust_state is DeviceTrustState.REVOKED:
            return None, DeviceAdministrationReason.DEVICE_REVOKED
        if request.action is DeviceAdministrationAction.TRUST_DEVICE:
            if current.trust_state is DeviceTrustState.TRUSTED:
                return None, DeviceAdministrationReason.NO_CHANGE
            return replace(current, trust_state=DeviceTrustState.TRUSTED), DeviceAdministrationReason.APPLIED
        if request.action is DeviceAdministrationAction.REVOKE_DEVICE:
            return (
                replace(
                    current,
                    trust_state=DeviceTrustState.REVOKED,
                    approved_capabilities=frozenset(),
                ),
                DeviceAdministrationReason.APPLIED,
            )
        capability = request.capability
        if capability is None:
            return None, DeviceAdministrationReason.MALFORMED_REQUEST
        if request.action is DeviceAdministrationAction.GRANT_CAPABILITY:
            if current.trust_state is not DeviceTrustState.TRUSTED:
                return None, DeviceAdministrationReason.DEVICE_NOT_TRUSTED
            if capability not in current.advertised_capabilities:
                return None, DeviceAdministrationReason.CAPABILITY_NOT_ADVERTISED
            if self._capabilities.resolve(capability) is None:
                return None, DeviceAdministrationReason.CAPABILITY_NOT_REVIEWED
            if capability in current.approved_capabilities:
                return None, DeviceAdministrationReason.NO_CHANGE
            return (
                replace(
                    current,
                    approved_capabilities=current.approved_capabilities.union({capability}),
                ),
                DeviceAdministrationReason.APPLIED,
            )
        if request.action is DeviceAdministrationAction.REVOKE_CAPABILITY:
            if capability not in current.approved_capabilities:
                return None, DeviceAdministrationReason.NO_CHANGE
            return (
                replace(
                    current,
                    approved_capabilities=current.approved_capabilities.difference({capability}),
                ),
                DeviceAdministrationReason.APPLIED,
            )
        return None, DeviceAdministrationReason.MALFORMED_REQUEST

    def _trusted_now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise RuntimeError("device registry clock must be timezone-aware")
        return now


@dataclass(frozen=True)
class AuthorizedToolRequestContext:
    """Trusted user/session facts resolved outside the LLM and device adapter."""

    request_id: str
    actor_id: str
    roles: frozenset[ActorRole]
    explicit_user_request: bool
    active_session: bool
    session_id: str | None
    node_id: str | None
    administrator_action: bool = False
    confirmed_confirmation_ids: frozenset[str] = frozenset()


class SmartHomePolicyContextResolver:
    """Build Policy context from trusted user facts plus Registry device facts."""

    def __init__(self, devices: SmartHomeDeviceRegistry) -> None:
        if not isinstance(devices, SmartHomeDeviceRegistry):
            raise TypeError("devices must be a SmartHomeDeviceRegistry")
        self._devices = devices

    def resolve(
        self,
        proposal: ToolProposal,
        authorized: AuthorizedToolRequestContext,
    ) -> PolicyEvaluationContext:
        if not isinstance(proposal, ToolProposal):
            raise TypeError("proposal must be a ToolProposal")
        if not isinstance(authorized, AuthorizedToolRequestContext):
            raise TypeError("authorized context is invalid")
        target = proposal.arguments.get("device_id")
        facts = self._devices.policy_facts(target) if isinstance(target, str) else None
        trusted_ids = (
            frozenset({facts.device_id}) if facts is not None and facts.trusted else frozenset()
        )
        capabilities = (
            facts.approved_capabilities if facts is not None and facts.trusted else frozenset()
        )
        return PolicyEvaluationContext(
            request_id=authorized.request_id,
            actor_id=authorized.actor_id,
            roles=authorized.roles,
            explicit_user_request=authorized.explicit_user_request,
            active_session=authorized.active_session,
            session_id=authorized.session_id,
            node_id=authorized.node_id,
            administrator_action=authorized.administrator_action,
            granted_capabilities=capabilities,
            trusted_device_ids=trusted_ids,
            confirmed_confirmation_ids=authorized.confirmed_confirmation_ids,
        )
