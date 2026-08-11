"""Fail-closed Node identity, credential, session, and replay boundary.

This module does not perform cryptography or networking. A reviewed adapter must
authenticate transport-specific credential proof and return only verified public
identity evidence. The domain then checks the authoritative credential record,
Node trust, capability grant, session binding, and replay state independently.

An admitted result means only that the Node Gateway accepted the request. It is
not a Policy Decision, device execution authorization, conversation session, or
node-local camera/microphone/notification gate decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import uuid4

from apps.assistant.src.ports.node_gateway import (
    Clock,
    CredentialAuthenticator,
    CredentialRepository,
    NodeRepository,
    ReplayProtector,
    SessionRepository,
)


IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
CREDENTIAL_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
CAPABILITY_PATTERN = re.compile(
    r"^[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)*$"
)
SENSITIVE_LOCAL_CAPABILITIES = frozenset(
    {
        "camera.snapshot",
        "camera.stream",
        "microphone",
        "microphone.session",
        "notification.local",
    }
)


class CredentialStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    REPLACED = "replaced"


class NodeTrustState(str, Enum):
    UNTRUSTED = "untrusted"
    PENDING_APPROVAL = "pending_approval"
    TRUSTED = "trusted"
    RESTRICTED = "restricted"
    REVOKED = "revoked"


class SecurityReason(str, Enum):
    AUTHENTICATED = "authenticated"
    GATEWAY_ADMITTED = "gateway_admitted"
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHENTICATOR_UNAVAILABLE = "authenticator_unavailable"
    MALFORMED_IDENTITY = "malformed_identity"
    IDENTITY_MISMATCH = "identity_mismatch"
    UNKNOWN_CREDENTIAL = "unknown_credential"
    CREDENTIAL_STATE_UNAVAILABLE = "credential_state_unavailable"
    AMBIGUOUS_CREDENTIAL_STATE = "ambiguous_credential_state"
    CREDENTIAL_REVOKED = "credential_revoked"
    CREDENTIAL_EXPIRED = "credential_expired"
    CREDENTIAL_REPLACED = "credential_replaced"
    UNKNOWN_NODE = "unknown_node"
    NODE_STATE_UNAVAILABLE = "node_state_unavailable"
    AMBIGUOUS_NODE_STATE = "ambiguous_node_state"
    NODE_REVOKED = "node_revoked"
    NODE_NOT_TRUSTED = "node_not_trusted"
    SESSION_NOT_AUTHENTICATED = "session_not_authenticated"
    SESSION_UNKNOWN = "session_unknown"
    SESSION_CLOSED = "session_closed"
    SESSION_EXPIRED = "session_expired"
    SESSION_STATE_UNAVAILABLE = "session_state_unavailable"
    MALFORMED_REQUEST = "malformed_request"
    REPLAY_DETECTED = "replay_detected"
    REPLAY_STATE_UNAVAILABLE = "replay_state_unavailable"
    CAPABILITY_NOT_ADVERTISED = "capability_not_advertised"
    CAPABILITY_NOT_GRANTED = "capability_not_granted"


@dataclass(frozen=True)
class VerifiedCredential:
    """Public result produced only by a trusted credential authenticator."""

    credential_id: str
    node_id: str


@dataclass(frozen=True)
class CredentialRecord:
    """Public lifecycle metadata; never contains a private key or bearer secret."""

    credential_id: str
    node_id: str
    credential_type: str
    issued_at: datetime
    status: CredentialStatus
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    replacement_credential_id: str | None = None


@dataclass(frozen=True)
class CapabilityAdvertisement:
    name: str
    local_authorization_required: bool


@dataclass(frozen=True)
class NodeRecord:
    """Logical Node metadata independent of network address and credentials."""

    node_id: str
    trust_state: NodeTrustState
    advertised_capabilities: tuple[CapabilityAdvertisement, ...]
    granted_capabilities: frozenset[str]


@dataclass(frozen=True)
class AuthenticatedNode:
    node_id: str
    credential_id: str


@dataclass(frozen=True)
class AuthenticationResult:
    authenticated: bool
    reason: SecurityReason
    principal: AuthenticatedNode | None = None


@dataclass(frozen=True)
class NodeSession:
    """Authenticated technical session, distinct from a conversation session."""

    session_id: str
    node_id: str
    credential_id: str
    opened_at: datetime
    expires_at: datetime
    closed_at: datetime | None = None


@dataclass(frozen=True)
class SessionResult:
    opened: bool
    reason: SecurityReason
    session: NodeSession | None = None


@dataclass(frozen=True)
class CapabilityRequest:
    """A Node Gateway request protected by session and per-session sequence."""

    request_id: str
    session_id: str
    sequence: int
    capability: str


@dataclass(frozen=True)
class GatewayAdmissionResult:
    """Gateway admission only; never sufficient for device or sensor execution."""

    admitted: bool
    reason: SecurityReason
    node_id: str | None = None
    credential_id: str | None = None
    node_local_gate_required: bool = False


class NodeGatewaySecurity:
    """Authenticate, open bounded sessions, and admit capability requests."""

    def __init__(
        self,
        *,
        authenticator: CredentialAuthenticator,
        credentials: CredentialRepository,
        nodes: NodeRepository,
        sessions: SessionRepository,
        replay: ReplayProtector,
        clock: Clock,
        session_lifetime: timedelta,
    ) -> None:
        if session_lifetime <= timedelta(0):
            raise ValueError("session_lifetime must be positive")
        self._authenticator = authenticator
        self._credentials = credentials
        self._nodes = nodes
        self._sessions = sessions
        self._replay = replay
        self._clock = clock
        self._session_lifetime = session_lifetime

    def authenticate_node(
        self, context: object, requested_node_id: str
    ) -> AuthenticationResult:
        if not _valid_identifier(requested_node_id):
            return AuthenticationResult(False, SecurityReason.MALFORMED_IDENTITY)
        try:
            verified = self._authenticator.authenticate(context)
        except Exception:
            return AuthenticationResult(False, SecurityReason.AUTHENTICATOR_UNAVAILABLE)
        if verified is None:
            return AuthenticationResult(False, SecurityReason.AUTHENTICATION_FAILED)
        if (
            not isinstance(verified, VerifiedCredential)
            or not _valid_identifier(verified.credential_id)
            or not _valid_identifier(verified.node_id)
            or verified.node_id != requested_node_id
        ):
            return AuthenticationResult(False, SecurityReason.IDENTITY_MISMATCH)
        try:
            credential = self._credentials.get(verified.credential_id)
        except Exception:
            return AuthenticationResult(False, SecurityReason.CREDENTIAL_STATE_UNAVAILABLE)
        if credential is None:
            return AuthenticationResult(False, SecurityReason.UNKNOWN_CREDENTIAL)
        if not _valid_credential_record(credential, verified):
            return AuthenticationResult(False, SecurityReason.AMBIGUOUS_CREDENTIAL_STATE)
        state_reason = _credential_state_reason(credential, self._trusted_now())
        if state_reason is not None:
            return AuthenticationResult(False, state_reason)
        return AuthenticationResult(
            True,
            SecurityReason.AUTHENTICATED,
            AuthenticatedNode(verified.node_id, verified.credential_id),
        )

    def open_session(self, context: object, requested_node_id: str) -> SessionResult:
        authentication = self.authenticate_node(context, requested_node_id)
        if not authentication.authenticated or authentication.principal is None:
            return SessionResult(False, authentication.reason)
        now = self._trusted_now()
        if now is None:
            return SessionResult(False, SecurityReason.SESSION_STATE_UNAVAILABLE)
        principal = authentication.principal
        session = NodeSession(
            session_id=str(uuid4()),
            node_id=principal.node_id,
            credential_id=principal.credential_id,
            opened_at=now,
            expires_at=now + self._session_lifetime,
        )
        try:
            self._sessions.put(session)
        except Exception:
            return SessionResult(False, SecurityReason.SESSION_STATE_UNAVAILABLE)
        return SessionResult(True, SecurityReason.AUTHENTICATED, session)

    def admit_request(
        self, context: object, request: CapabilityRequest
    ) -> GatewayAdmissionResult:
        if not _valid_capability_request(request):
            return GatewayAdmissionResult(False, SecurityReason.MALFORMED_REQUEST)
        now = self._trusted_now()
        if now is None:
            return GatewayAdmissionResult(False, SecurityReason.SESSION_STATE_UNAVAILABLE)
        try:
            session = self._sessions.get(request.session_id)
        except Exception:
            return GatewayAdmissionResult(False, SecurityReason.SESSION_STATE_UNAVAILABLE)
        if session is None:
            return GatewayAdmissionResult(False, SecurityReason.SESSION_UNKNOWN)
        if not _valid_session(session, now):
            return GatewayAdmissionResult(False, SecurityReason.SESSION_STATE_UNAVAILABLE)
        if session.closed_at is not None:
            return GatewayAdmissionResult(False, SecurityReason.SESSION_CLOSED)
        if now >= session.expires_at:
            return GatewayAdmissionResult(False, SecurityReason.SESSION_EXPIRED)
        try:
            node = self._nodes.get(session.node_id)
        except Exception:
            return GatewayAdmissionResult(False, SecurityReason.NODE_STATE_UNAVAILABLE)
        if node is None:
            return GatewayAdmissionResult(False, SecurityReason.UNKNOWN_NODE)
        if not _valid_node_record(node):
            return GatewayAdmissionResult(False, SecurityReason.AMBIGUOUS_NODE_STATE)
        if node.trust_state is NodeTrustState.REVOKED:
            return GatewayAdmissionResult(False, SecurityReason.NODE_REVOKED)
        if node.trust_state is not NodeTrustState.TRUSTED:
            return GatewayAdmissionResult(False, SecurityReason.NODE_NOT_TRUSTED)
        advertisements = [
            item
            for item in node.advertised_capabilities
            if item.name == request.capability
        ]
        if len(advertisements) != 1:
            return GatewayAdmissionResult(False, SecurityReason.CAPABILITY_NOT_ADVERTISED)
        if request.capability not in node.granted_capabilities:
            return GatewayAdmissionResult(False, SecurityReason.CAPABILITY_NOT_GRANTED)
        try:
            replayed = self._replay.check_and_record(
                request.session_id, request.sequence, request.request_id
            )
        except Exception:
            return GatewayAdmissionResult(False, SecurityReason.REPLAY_STATE_UNAVAILABLE)
        if replayed:
            return GatewayAdmissionResult(False, SecurityReason.REPLAY_DETECTED)
        advertisement = advertisements[0]
        return GatewayAdmissionResult(
            True,
            SecurityReason.GATEWAY_ADMITTED,
            node_id=session.node_id,
            credential_id=session.credential_id,
            node_local_gate_required=advertisement.local_authorization_required,
        )

    def close_session(self, context: object, session_id: str) -> bool:
        now = self._trusted_now()
        if now is None or not _valid_identifier(session_id):
            return False
        try:
            session = self._sessions.get(session_id)
        except Exception:
            return False
        if session is None or session.closed_at is not None:
            return False
        try:
            verified = self._authenticator.authenticate(context)
        except Exception:
            return False
        if (
            verified is None
            or not isinstance(verified, VerifiedCredential)
            or verified.node_id != session.node_id
            or verified.credential_id != session.credential_id
        ):
            return False
        try:
            self._sessions.put(
                NodeSession(
                    session_id=session.session_id,
                    node_id=session.node_id,
                    credential_id=session.credential_id,
                    opened_at=session.opened_at,
                    expires_at=session.expires_at,
                    closed_at=now,
                )
            )
        except Exception:
            return False
        return True

    def _trusted_now(self) -> datetime | None:
        try:
            now = self._clock.now()
        except Exception:
            return None
        if now.tzinfo is None or now.utcoffset() is None:
            return None
        return now


def _credential_state_reason(
    credential: CredentialRecord, now: datetime | None
) -> SecurityReason | None:
    if credential.status is CredentialStatus.REVOKED:
        return SecurityReason.CREDENTIAL_REVOKED
    if credential.status is CredentialStatus.REPLACED:
        return SecurityReason.CREDENTIAL_REPLACED
    if credential.status is CredentialStatus.EXPIRED:
        return SecurityReason.CREDENTIAL_EXPIRED
    if now is None:
        return SecurityReason.CREDENTIAL_STATE_UNAVAILABLE
    if credential.expires_at is not None and now >= credential.expires_at:
        return SecurityReason.CREDENTIAL_EXPIRED
    return None


def _valid_identifier(value: object) -> bool:
    return isinstance(value, str) and IDENTIFIER_PATTERN.fullmatch(value) is not None


def _valid_credential_record(
    credential: object, verified: VerifiedCredential
) -> bool:
    if not isinstance(credential, CredentialRecord):
        return False
    if (
        credential.credential_id != verified.credential_id
        or credential.node_id != verified.node_id
        or not _valid_identifier(credential.credential_id)
        or not _valid_identifier(credential.node_id)
        or not isinstance(credential.credential_type, str)
        or CREDENTIAL_TYPE_PATTERN.fullmatch(credential.credential_type) is None
        or credential.issued_at.tzinfo is None
        or credential.issued_at.utcoffset() is None
        or (
            credential.expires_at is not None
            and (
                credential.expires_at.tzinfo is None
                or credential.expires_at.utcoffset() is None
            )
        )
        or (
            credential.revoked_at is not None
            and (
                credential.revoked_at.tzinfo is None
                or credential.revoked_at.utcoffset() is None
            )
        )
        or (
            credential.replacement_credential_id is not None
            and not _valid_identifier(credential.replacement_credential_id)
        )
    ):
        return False
    return True


def _valid_node_record(node: object) -> bool:
    if not isinstance(node, NodeRecord) or not _valid_identifier(node.node_id):
        return False
    if not isinstance(node.trust_state, NodeTrustState):
        return False
    names: set[str] = set()
    for item in node.advertised_capabilities:
        if (
            not isinstance(item, CapabilityAdvertisement)
            or not isinstance(item.name, str)
            or CAPABILITY_PATTERN.fullmatch(item.name) is None
            or not isinstance(item.local_authorization_required, bool)
            or item.name in names
            or (
                item.name in SENSITIVE_LOCAL_CAPABILITIES
                and not item.local_authorization_required
            )
        ):
            return False
        names.add(item.name)
    return all(
        isinstance(capability, str)
        and CAPABILITY_PATTERN.fullmatch(capability) is not None
        for capability in node.granted_capabilities
    )


def _valid_capability_request(request: object) -> bool:
    return (
        isinstance(request, CapabilityRequest)
        and _valid_identifier(request.request_id)
        and _valid_identifier(request.session_id)
        and isinstance(request.sequence, int)
        and not isinstance(request.sequence, bool)
        and request.sequence > 0
        and isinstance(request.capability, str)
        and CAPABILITY_PATTERN.fullmatch(request.capability) is not None
    )
