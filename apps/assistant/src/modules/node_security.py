"""Fail-closed Node identity, credential, session, and replay boundary.

This module does not perform cryptography or networking. A reviewed adapter must
authenticate transport-specific credential proof and return only verified public
identity evidence. The domain then checks the authoritative credential record,
Node trust, capability grant, session binding, and replay state independently.

An admitted result means only that the Node Gateway accepted the request. It is
not a Policy Decision, device execution authorization, conversation session, or
node-local camera/microphone gate decision.
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
    """Coordinates independent checks without implementing a network transport."""

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
        self, presentation: object, claimed_node_id: str
    ) -> AuthenticationResult:
        """Authenticate identity without granting trust or a capability."""

        if not _valid_identifier(claimed_node_id):
            return AuthenticationResult(False, SecurityReason.MALFORMED_IDENTITY)

        verified, reason = self._verify_presentation(presentation)
        if verified is None:
            return AuthenticationResult(False, reason)
        if verified.node_id != claimed_node_id:
            return AuthenticationResult(False, SecurityReason.IDENTITY_MISMATCH)

        binding, reason = self._resolve_current_binding(
            verified.credential_id, verified.node_id
        )
        if binding is None:
            return AuthenticationResult(False, reason)
        _, node = binding
        if node.trust_state is NodeTrustState.REVOKED:
            return AuthenticationResult(False, SecurityReason.NODE_REVOKED)

        return AuthenticationResult(
            True,
            SecurityReason.AUTHENTICATED,
            AuthenticatedNode(
                node_id=verified.node_id,
                credential_id=verified.credential_id,
            ),
        )

    def open_session(
        self, presentation: object, claimed_node_id: str
    ) -> SessionResult:
        """Open a technical session for an authenticated, non-revoked Node.

        Untrusted or pending Nodes may authenticate and maintain a technical
        session for future onboarding flows, but protected capability requests
        remain denied until the Node is explicitly trusted and granted access.
        """

        authentication = self.authenticate_node(presentation, claimed_node_id)
        principal = authentication.principal
        if not authentication.authenticated or principal is None:
            return SessionResult(False, SecurityReason.SESSION_NOT_AUTHENTICATED)

        binding, reason = self._resolve_current_binding(
            principal.credential_id, principal.node_id
        )
        if binding is None:
            return SessionResult(False, reason)
        _, node = binding
        if node.trust_state is NodeTrustState.REVOKED:
            return SessionResult(False, SecurityReason.NODE_REVOKED)

        now = self._trusted_now()
        if now is None:
            return SessionResult(False, SecurityReason.SESSION_STATE_UNAVAILABLE)
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

    def close_session(self, presentation: object, session_id: str) -> bool:
        """Close a technical session and discard only its replay tracking state."""

        if not _valid_identifier(session_id):
            return False
        verified, _ = self._verify_presentation(presentation)
        if verified is None:
            return False
        now = self._trusted_now()
        if now is None:
            return False
        try:
            session = self._sessions.get(session_id)
            if (
                session is None
                or not _valid_session(session, session_id, now)
                or session.node_id != verified.node_id
                or session.credential_id != verified.credential_id
            ):
                return False
            closed = self._sessions.close(session_id, now)
            if closed:
                self._replay.forget(session_id)
            return closed
        except Exception:
            return False

    def admit_request(
        self, presentation: object, request: CapabilityRequest
    ) -> GatewayAdmissionResult:
        """Apply current session, credential, replay, trust, and grant checks.

        Sequence state is consumed before trust/capability evaluation. A denied
        authenticated request therefore cannot later become valid merely because
        the Node's trust or grants changed.
        """

        if not _valid_request(request):
            return GatewayAdmissionResult(False, SecurityReason.MALFORMED_REQUEST)

        verified, reason = self._verify_presentation(presentation)
        if verified is None:
            return GatewayAdmissionResult(False, reason)

        binding, reason = self._resolve_current_binding(
            verified.credential_id, verified.node_id
        )
        if binding is None:
            return GatewayAdmissionResult(False, reason)
        credential, node = binding
        if node.trust_state is NodeTrustState.REVOKED:
            return GatewayAdmissionResult(False, SecurityReason.NODE_REVOKED)

        now = self._trusted_now()
        if now is None:
            return GatewayAdmissionResult(
                False, SecurityReason.SESSION_STATE_UNAVAILABLE
            )
        try:
            session = self._sessions.get(request.session_id)
        except Exception:
            return GatewayAdmissionResult(
                False, SecurityReason.SESSION_STATE_UNAVAILABLE
            )
        if session is None:
            return GatewayAdmissionResult(False, SecurityReason.SESSION_UNKNOWN)
        if not _valid_session(session, request.session_id, now):
            return GatewayAdmissionResult(
                False, SecurityReason.SESSION_STATE_UNAVAILABLE
            )
        if session.closed_at is not None:
            return GatewayAdmissionResult(False, SecurityReason.SESSION_CLOSED)
        if session.expires_at <= now:
            return GatewayAdmissionResult(False, SecurityReason.SESSION_EXPIRED)
        if (
            session.node_id != verified.node_id
            or session.credential_id != verified.credential_id
        ):
            return GatewayAdmissionResult(False, SecurityReason.IDENTITY_MISMATCH)

        try:
            fresh_sequence = self._replay.accept(
                request.session_id, request.sequence
            )
        except Exception:
            return GatewayAdmissionResult(
                False, SecurityReason.REPLAY_STATE_UNAVAILABLE
            )
        if not fresh_sequence:
            return GatewayAdmissionResult(False, SecurityReason.REPLAY_DETECTED)

        if node.trust_state is not NodeTrustState.TRUSTED:
            return GatewayAdmissionResult(
                False,
                SecurityReason.NODE_NOT_TRUSTED,
                node_id=node.node_id,
                credential_id=credential.credential_id,
            )

        advertisement = _find_advertisement(node, request.capability)
        if advertisement is None:
            return GatewayAdmissionResult(
                False,
                SecurityReason.CAPABILITY_NOT_ADVERTISED,
                node_id=node.node_id,
                credential_id=credential.credential_id,
            )
        if request.capability not in node.granted_capabilities:
            return GatewayAdmissionResult(
                False,
                SecurityReason.CAPABILITY_NOT_GRANTED,
                node_id=node.node_id,
                credential_id=credential.credential_id,
            )

        return GatewayAdmissionResult(
            True,
            SecurityReason.GATEWAY_ADMITTED,
            node_id=node.node_id,
            credential_id=credential.credential_id,
            node_local_gate_required=advertisement.local_authorization_required,
        )

    def _resolve_current_binding(
        self, credential_id: str, node_id: str
    ) -> tuple[tuple[CredentialRecord, NodeRecord] | None, SecurityReason]:
        try:
            credential = self._credentials.get(credential_id)
        except Exception:
            return None, SecurityReason.CREDENTIAL_STATE_UNAVAILABLE
        if credential is None:
            return None, SecurityReason.UNKNOWN_CREDENTIAL
        if not isinstance(credential, CredentialRecord):
            return None, SecurityReason.AMBIGUOUS_CREDENTIAL_STATE
        if credential.credential_id != credential_id:
            return None, SecurityReason.AMBIGUOUS_CREDENTIAL_STATE

        now = self._trusted_now()
        if now is None:
            return None, SecurityReason.CREDENTIAL_STATE_UNAVAILABLE
        reason = _credential_denial_reason(credential, node_id, now)
        if reason is not None:
            return None, reason

        try:
            node = self._nodes.get(node_id)
        except Exception:
            return None, SecurityReason.NODE_STATE_UNAVAILABLE
        if node is None:
            return None, SecurityReason.UNKNOWN_NODE
        if not isinstance(node, NodeRecord):
            return None, SecurityReason.AMBIGUOUS_NODE_STATE
        reason = _node_denial_reason(node, node_id)
        if reason is not None:
            return None, reason
        return (credential, node), SecurityReason.AUTHENTICATED

    def _verify_presentation(
        self, presentation: object
    ) -> tuple[VerifiedCredential | None, SecurityReason]:
        try:
            verified = self._authenticator.authenticate(presentation)
        except Exception:
            return None, SecurityReason.AUTHENTICATOR_UNAVAILABLE
        if verified is None:
            return None, SecurityReason.AUTHENTICATION_FAILED
        if (
            not isinstance(verified, VerifiedCredential)
            or not _valid_identifier(verified.node_id)
            or not _valid_identifier(verified.credential_id)
        ):
            return None, SecurityReason.MALFORMED_IDENTITY
        return verified, SecurityReason.AUTHENTICATED

    def _trusted_now(self) -> datetime | None:
        try:
            now = self._clock.now()
        except Exception:
            return None
        return now if _valid_time(now) else None


def _credential_denial_reason(
    credential: CredentialRecord, expected_node_id: str, now: datetime
) -> SecurityReason | None:
    if (
        not _valid_identifier(credential.credential_id)
        or not _valid_identifier(credential.node_id)
        or credential.node_id != expected_node_id
        or not isinstance(credential.credential_type, str)
        or CREDENTIAL_TYPE_PATTERN.fullmatch(credential.credential_type) is None
        or not _valid_time(credential.issued_at)
        or credential.issued_at > now
        or not isinstance(credential.status, CredentialStatus)
        or (credential.expires_at is not None and not _valid_time(credential.expires_at))
        or (credential.revoked_at is not None and not _valid_time(credential.revoked_at))
        or (
            credential.replacement_credential_id is not None
            and not _valid_identifier(credential.replacement_credential_id)
        )
    ):
        return SecurityReason.AMBIGUOUS_CREDENTIAL_STATE

    if (
        credential.status is not CredentialStatus.REVOKED
        and credential.revoked_at is not None
    ) or (
        credential.status is not CredentialStatus.REPLACED
        and credential.replacement_credential_id is not None
    ):
        return SecurityReason.AMBIGUOUS_CREDENTIAL_STATE

    if credential.status is CredentialStatus.ACTIVE:
        if credential.expires_at is not None and credential.expires_at <= now:
            return SecurityReason.CREDENTIAL_EXPIRED
        return None
    if credential.status is CredentialStatus.REVOKED:
        if credential.revoked_at is None or credential.revoked_at > now:
            return SecurityReason.AMBIGUOUS_CREDENTIAL_STATE
        return SecurityReason.CREDENTIAL_REVOKED
    if credential.status is CredentialStatus.EXPIRED:
        if credential.expires_at is None or credential.expires_at > now:
            return SecurityReason.AMBIGUOUS_CREDENTIAL_STATE
        return SecurityReason.CREDENTIAL_EXPIRED
    if credential.status is CredentialStatus.REPLACED:
        if not credential.replacement_credential_id:
            return SecurityReason.AMBIGUOUS_CREDENTIAL_STATE
        if credential.replacement_credential_id == credential.credential_id:
            return SecurityReason.AMBIGUOUS_CREDENTIAL_STATE
        return SecurityReason.CREDENTIAL_REPLACED
    return SecurityReason.AMBIGUOUS_CREDENTIAL_STATE


def _node_denial_reason(
    node: NodeRecord, expected_node_id: str
) -> SecurityReason | None:
    if (
        not _valid_identifier(node.node_id)
        or node.node_id != expected_node_id
        or not isinstance(node.trust_state, NodeTrustState)
        or not isinstance(node.advertised_capabilities, tuple)
        or not isinstance(node.granted_capabilities, frozenset)
    ):
        return SecurityReason.AMBIGUOUS_NODE_STATE

    names: set[str] = set()
    for advertisement in node.advertised_capabilities:
        if (
            not isinstance(advertisement, CapabilityAdvertisement)
            or not _valid_capability(advertisement.name)
            or not isinstance(advertisement.local_authorization_required, bool)
            or advertisement.name in names
            or (
                advertisement.name in SENSITIVE_LOCAL_CAPABILITIES
                and not advertisement.local_authorization_required
            )
        ):
            return SecurityReason.AMBIGUOUS_NODE_STATE
        names.add(advertisement.name)
    if any(not _valid_capability(item) for item in node.granted_capabilities):
        return SecurityReason.AMBIGUOUS_NODE_STATE
    return None


def _find_advertisement(
    node: NodeRecord, capability: str
) -> CapabilityAdvertisement | None:
    for advertisement in node.advertised_capabilities:
        if advertisement.name == capability:
            return advertisement
    return None


def _valid_identifier(value: object) -> bool:
    return isinstance(value, str) and IDENTIFIER_PATTERN.fullmatch(value) is not None


def _valid_capability(value: object) -> bool:
    return isinstance(value, str) and CAPABILITY_PATTERN.fullmatch(value) is not None


def _valid_time(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _valid_request(request: CapabilityRequest) -> bool:
    return (
        isinstance(request, CapabilityRequest)
        and isinstance(request.request_id, str)
        and 1 <= len(request.request_id) <= 128
        and _valid_identifier(request.session_id)
        and isinstance(request.sequence, int)
        and not isinstance(request.sequence, bool)
        and request.sequence > 0
        and _valid_capability(request.capability)
    )


def _valid_session(session: object, expected_session_id: str, now: datetime) -> bool:
    return (
        isinstance(session, NodeSession)
        and session.session_id == expected_session_id
        and _valid_identifier(session.session_id)
        and _valid_identifier(session.node_id)
        and _valid_identifier(session.credential_id)
        and _valid_time(session.opened_at)
        and _valid_time(session.expires_at)
        and session.opened_at <= now
        and session.opened_at < session.expires_at
        and (session.closed_at is None or _valid_time(session.closed_at))
    )


class SystemClock:
    """Standard-library clock suitable for application wiring."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
