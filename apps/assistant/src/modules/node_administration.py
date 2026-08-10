"""Fail-closed Node enrollment, trust, grants, revocation, and audit boundary.

Authentication at the Node Gateway does not enroll a Node and cannot call this
boundary as administrative authority. Every request requires action-specific
administrator evidence. Successful registry mutation is not a Policy Decision,
Tool permission, device execution approval, or node-local sensor decision.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from apps.assistant.src.modules.node_security import (
    CAPABILITY_PATTERN,
    IDENTIFIER_PATTERN,
    NodeTrustState,
)
from apps.assistant.src.ports.node_administration import (
    AdministratorAuthorizer,
    AtomicNodeAdministrationStore,
    NodeCapabilityReader,
)
from apps.assistant.src.ports.node_gateway import Clock


class AdministrationAction(str, Enum):
    ENROLL_NODE = "node.enroll"
    SET_TRUST = "node.trust.set"
    GRANT_CAPABILITY = "node.capability.grant"
    REVOKE_CAPABILITY = "node.capability.revoke"
    REVOKE_NODE = "node.revoke"


class AdministrationReason(str, Enum):
    APPLIED = "applied"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    NO_CHANGE = "no_change"
    MALFORMED_REQUEST = "malformed_request"
    ADMINISTRATION_DENIED = "administration_denied"
    AUTHORIZER_UNAVAILABLE = "authorizer_unavailable"
    AMBIGUOUS_AUTHORIZATION = "ambiguous_authorization"
    STATE_UNAVAILABLE = "state_unavailable"
    AMBIGUOUS_STATE = "ambiguous_state"
    NODE_NOT_ENROLLED = "node_not_enrolled"
    NODE_ALREADY_ENROLLED = "node_already_enrolled"
    NODE_REVOKED = "node_revoked"
    CAPABILITY_NOT_ADVERTISED = "capability_not_advertised"
    CAPABILITY_STATE_UNAVAILABLE = "capability_state_unavailable"
    REVISION_CONFLICT = "revision_conflict"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"


class StoreApplyOutcome(str, Enum):
    APPLIED = "applied"
    IDEMPOTENT = "idempotent"
    REVISION_CONFLICT = "revision_conflict"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"


@dataclass(frozen=True)
class VerifiedAdministrator:
    """Action-specific public evidence returned by the trusted authorizer."""

    actor_id: str
    action: AdministrationAction
    node_id: str


@dataclass(frozen=True)
class AdministrationRequest:
    operation_id: str
    correlation_id: str
    action: AdministrationAction
    node_id: str
    expected_revision: int
    trust_state: NodeTrustState | None = None
    capability: str | None = None


@dataclass(frozen=True)
class NodeAdministrationRecord:
    """Enrolled Node state; existence means enrolled, never authenticated."""

    node_id: str
    trust_state: NodeTrustState
    granted_capabilities: frozenset[str]
    revision: int
    enrolled_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AdministrationAuditEvent:
    """Metadata-only event compatible with the audit-event v1 semantics."""

    event_id: str
    correlation_id: str
    occurred_at: datetime
    category: str
    action: str
    actor_type: str
    actor_id: str
    decision: str
    result: str
    node_id: str
    capability: str | None = None


@dataclass(frozen=True)
class AdministrationMutation:
    request: AdministrationRequest
    record: NodeAdministrationRecord
    audit_event: AdministrationAuditEvent


@dataclass(frozen=True)
class StoredAdministrationOperation:
    request: AdministrationRequest
    record: NodeAdministrationRecord
    audit_event: AdministrationAuditEvent


@dataclass(frozen=True)
class StoreApplyResult:
    outcome: StoreApplyOutcome
    record: NodeAdministrationRecord | None = None


@dataclass(frozen=True)
class AdministrationResult:
    """Registry mutation result; never an action-execution authorization."""

    succeeded: bool
    changed: bool
    idempotent: bool
    reason: AdministrationReason
    record: NodeAdministrationRecord | None = None


class NodeAdministration:
    """Coordinates privileged desired-state changes without choosing storage."""

    def __init__(
        self,
        *,
        authorizer: AdministratorAuthorizer,
        store: AtomicNodeAdministrationStore,
        capabilities: NodeCapabilityReader,
        clock: Clock,
    ) -> None:
        self._authorizer = authorizer
        self._store = store
        self._capabilities = capabilities
        self._clock = clock

    def administer(
        self, context: object, request: AdministrationRequest
    ) -> AdministrationResult:
        if not _valid_request(request):
            return _denied(AdministrationReason.MALFORMED_REQUEST)

        administrator, reason = self._authorize(context, request)
        if administrator is None:
            return _denied(reason)

        now = self._trusted_now()
        if now is None:
            return _denied(AdministrationReason.STATE_UNAVAILABLE)

        prior, reason = self._prior_operation(request, now)
        if reason is not None:
            return _denied(reason)
        if prior is not None:
            return AdministrationResult(
                True,
                False,
                True,
                AdministrationReason.IDEMPOTENT_REPLAY,
                prior.record,
            )

        current, reason = self._current_record(request.node_id, now)
        if reason is not None:
            return _denied(reason)

        candidate, reason = self._candidate(request, current, now)
        if candidate is None:
            if reason is AdministrationReason.NO_CHANGE and current is not None:
                return AdministrationResult(True, False, True, reason, current)
            return _denied(reason)

        event = AdministrationAuditEvent(
            event_id=str(uuid4()),
            correlation_id=request.correlation_id,
            occurred_at=now,
            category="administration",
            action=request.action.value,
            actor_type="user",
            actor_id=administrator.actor_id,
            decision="allow",
            result="success",
            node_id=request.node_id,
            capability=request.capability,
        )
        mutation = AdministrationMutation(request, candidate, event)
        try:
            result = self._store.apply(mutation)
        except Exception:
            return _denied(AdministrationReason.STATE_UNAVAILABLE)
        if not isinstance(result, StoreApplyResult) or not isinstance(
            result.outcome, StoreApplyOutcome
        ):
            return _denied(AdministrationReason.AMBIGUOUS_STATE)

        if result.outcome is StoreApplyOutcome.APPLIED:
            if result.record != candidate:
                return _denied(AdministrationReason.AMBIGUOUS_STATE)
            return AdministrationResult(
                True, True, False, AdministrationReason.APPLIED, candidate
            )
        if result.outcome is StoreApplyOutcome.IDEMPOTENT:
            if not _valid_record(result.record, request.node_id, now):
                return _denied(AdministrationReason.AMBIGUOUS_STATE)
            return AdministrationResult(
                True,
                False,
                True,
                AdministrationReason.IDEMPOTENT_REPLAY,
                result.record,
            )
        if result.outcome is StoreApplyOutcome.REVISION_CONFLICT:
            return _denied(AdministrationReason.REVISION_CONFLICT)
        if result.outcome is StoreApplyOutcome.IDEMPOTENCY_CONFLICT:
            return _denied(AdministrationReason.IDEMPOTENCY_CONFLICT)
        return _denied(AdministrationReason.AMBIGUOUS_STATE)

    def _authorize(
        self, context: object, request: AdministrationRequest
    ) -> tuple[VerifiedAdministrator | None, AdministrationReason]:
        try:
            administrator = self._authorizer.authorize(
                context, request.action, request.node_id
            )
        except Exception:
            return None, AdministrationReason.AUTHORIZER_UNAVAILABLE
        if administrator is None:
            return None, AdministrationReason.ADMINISTRATION_DENIED
        if (
            not isinstance(administrator, VerifiedAdministrator)
            or not _valid_actor_id(administrator.actor_id)
            or administrator.action is not request.action
            or administrator.node_id != request.node_id
        ):
            return None, AdministrationReason.AMBIGUOUS_AUTHORIZATION
        return administrator, AdministrationReason.APPLIED

    def _prior_operation(
        self, request: AdministrationRequest, now: datetime
    ) -> tuple[StoredAdministrationOperation | None, AdministrationReason | None]:
        try:
            prior = self._store.get_operation(request.operation_id)
        except Exception:
            return None, AdministrationReason.STATE_UNAVAILABLE
        if prior is None:
            return None, None
        if (
            not isinstance(prior, StoredAdministrationOperation)
            or not _valid_request(prior.request)
            or prior.request.operation_id != request.operation_id
            or not _valid_audit_event(prior.audit_event)
            or not _valid_record(prior.record, prior.request.node_id, now)
            or prior.audit_event.correlation_id != prior.request.correlation_id
            or prior.audit_event.action != prior.request.action.value
            or prior.audit_event.node_id != prior.request.node_id
            or prior.audit_event.capability != prior.request.capability
            or prior.audit_event.occurred_at != prior.record.updated_at
        ):
            return None, AdministrationReason.AMBIGUOUS_STATE
        if prior.request != request:
            return None, AdministrationReason.IDEMPOTENCY_CONFLICT
        return prior, None

    def _current_record(
        self, node_id: str, now: datetime
    ) -> tuple[NodeAdministrationRecord | None, AdministrationReason | None]:
        try:
            record = self._store.get_node(node_id)
        except Exception:
            return None, AdministrationReason.STATE_UNAVAILABLE
        if record is not None and not _valid_record(record, node_id, now):
            return None, AdministrationReason.AMBIGUOUS_STATE
        return record, None

    def _candidate(
        self,
        request: AdministrationRequest,
        current: NodeAdministrationRecord | None,
        now: datetime,
    ) -> tuple[NodeAdministrationRecord | None, AdministrationReason]:
        if request.action is AdministrationAction.ENROLL_NODE:
            if current is not None:
                return None, AdministrationReason.NODE_ALREADY_ENROLLED
            return (
                NodeAdministrationRecord(
                    node_id=request.node_id,
                    trust_state=NodeTrustState.UNTRUSTED,
                    granted_capabilities=frozenset(),
                    revision=1,
                    enrolled_at=now,
                    updated_at=now,
                ),
                AdministrationReason.APPLIED,
            )

        if current is None:
            return None, AdministrationReason.NODE_NOT_ENROLLED
        if current.revision != request.expected_revision:
            return None, AdministrationReason.REVISION_CONFLICT

        if request.action is AdministrationAction.REVOKE_NODE:
            if current.trust_state is NodeTrustState.REVOKED:
                return None, AdministrationReason.NO_CHANGE
            return (
                replace(
                    current,
                    trust_state=NodeTrustState.REVOKED,
                    revision=current.revision + 1,
                    updated_at=now,
                ),
                AdministrationReason.APPLIED,
            )

        if current.trust_state is NodeTrustState.REVOKED:
            return None, AdministrationReason.NODE_REVOKED

        if request.action is AdministrationAction.SET_TRUST:
            if current.trust_state is request.trust_state:
                return None, AdministrationReason.NO_CHANGE
            return (
                replace(
                    current,
                    trust_state=request.trust_state,
                    revision=current.revision + 1,
                    updated_at=now,
                ),
                AdministrationReason.APPLIED,
            )

        capability = request.capability
        if request.action is AdministrationAction.GRANT_CAPABILITY:
            if capability in current.granted_capabilities:
                return None, AdministrationReason.NO_CHANGE
            try:
                advertised = self._capabilities.is_advertised(
                    request.node_id, capability
                )
            except Exception:
                return None, AdministrationReason.CAPABILITY_STATE_UNAVAILABLE
            if not isinstance(advertised, bool):
                return None, AdministrationReason.CAPABILITY_STATE_UNAVAILABLE
            if not advertised:
                return None, AdministrationReason.CAPABILITY_NOT_ADVERTISED
            return (
                replace(
                    current,
                    granted_capabilities=current.granted_capabilities
                    | frozenset({capability}),
                    revision=current.revision + 1,
                    updated_at=now,
                ),
                AdministrationReason.APPLIED,
            )

        if capability not in current.granted_capabilities:
            return None, AdministrationReason.NO_CHANGE
        return (
            replace(
                current,
                granted_capabilities=current.granted_capabilities
                - frozenset({capability}),
                revision=current.revision + 1,
                updated_at=now,
            ),
            AdministrationReason.APPLIED,
        )

    def _trusted_now(self) -> datetime | None:
        try:
            now = self._clock.now()
        except Exception:
            return None
        return now if _valid_time(now) else None


def _denied(reason: AdministrationReason) -> AdministrationResult:
    return AdministrationResult(False, False, False, reason)


def _valid_request(request: object) -> bool:
    if (
        not isinstance(request, AdministrationRequest)
        or not _valid_uuid(request.operation_id)
        or not _valid_correlation_id(request.correlation_id)
        or not isinstance(request.action, AdministrationAction)
        or not _valid_identifier(request.node_id)
        or not isinstance(request.expected_revision, int)
        or isinstance(request.expected_revision, bool)
        or request.expected_revision < 0
    ):
        return False

    if request.action is AdministrationAction.ENROLL_NODE:
        return (
            request.expected_revision == 0
            and request.trust_state is None
            and request.capability is None
        )
    if request.expected_revision == 0:
        return False
    if request.action is AdministrationAction.SET_TRUST:
        return request.trust_state in {
            NodeTrustState.UNTRUSTED,
            NodeTrustState.TRUSTED,
            NodeTrustState.RESTRICTED,
        } and request.capability is None
    if request.action in {
        AdministrationAction.GRANT_CAPABILITY,
        AdministrationAction.REVOKE_CAPABILITY,
    }:
        return (
            request.trust_state is None
            and _valid_capability(request.capability)
        )
    return request.trust_state is None and request.capability is None


def _valid_record(
    record: object, expected_node_id: str, now: datetime | None
) -> bool:
    return (
        isinstance(record, NodeAdministrationRecord)
        and record.node_id == expected_node_id
        and _valid_identifier(record.node_id)
        and isinstance(record.trust_state, NodeTrustState)
        and isinstance(record.granted_capabilities, frozenset)
        and all(_valid_capability(item) for item in record.granted_capabilities)
        and isinstance(record.revision, int)
        and not isinstance(record.revision, bool)
        and record.revision > 0
        and _valid_time(record.enrolled_at)
        and _valid_time(record.updated_at)
        and record.enrolled_at <= record.updated_at
        and (now is None or record.updated_at <= now)
    )


def _valid_audit_event(event: object) -> bool:
    return (
        isinstance(event, AdministrationAuditEvent)
        and _valid_uuid(event.event_id)
        and _valid_correlation_id(event.correlation_id)
        and _valid_time(event.occurred_at)
        and event.category == "administration"
        and event.action in {item.value for item in AdministrationAction}
        and event.actor_type == "user"
        and _valid_actor_id(event.actor_id)
        and event.decision == "allow"
        and event.result == "success"
        and _valid_identifier(event.node_id)
        and (event.capability is None or _valid_capability(event.capability))
    )


def _valid_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _valid_identifier(value: object) -> bool:
    return isinstance(value, str) and IDENTIFIER_PATTERN.fullmatch(value) is not None


def _valid_capability(value: object) -> bool:
    return isinstance(value, str) and CAPABILITY_PATTERN.fullmatch(value) is not None


def _valid_correlation_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 128
        and value.isprintable()
    )


def _valid_actor_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 128
        and value.isprintable()
    )


def _valid_time(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )
