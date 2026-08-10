"""Technology-neutral ports required by the Node Gateway security boundary."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from apps.assistant.src.modules.node_security import (
        AuthenticationResult,
        CapabilityRequest,
        CredentialRecord,
        GatewayAdmissionResult,
        NodeRecord,
        NodeSession,
        SessionResult,
        VerifiedCredential,
    )


class Clock(Protocol):
    """Supplies trusted server time for credential and session validity checks."""

    def now(self) -> datetime:
        """Return a timezone-aware current time."""


class CredentialAuthenticator(Protocol):
    """Verifies transport-specific proof without exposing it to domain logic.

    The presentation is opaque to the Node Gateway. Implementations may later use
    an mTLS peer certificate or another reviewed mechanism. Presentations and
    private key material must never be persisted or logged by this boundary.
    """

    def authenticate(self, presentation: object) -> VerifiedCredential | None:
        """Return verified public identity evidence, or ``None`` on failure."""


class CredentialRepository(Protocol):
    """Resolves authoritative credential lifecycle records by public identifier."""

    def get(self, credential_id: str) -> CredentialRecord | None:
        """Return the credential record when known."""


class NodeRepository(Protocol):
    """Resolves Node trust and capability state independently of credentials."""

    def get(self, node_id: str) -> NodeRecord | None:
        """Return the Node record when known."""


class SessionRepository(Protocol):
    """Stores authenticated technical sessions, not conversation sessions."""

    def get(self, session_id: str) -> NodeSession | None:
        """Return the session when known."""

    def put(self, session: NodeSession) -> None:
        """Persist a new session, rejecting any previously used session ID."""

    def close(self, session_id: str, closed_at: datetime) -> bool:
        """Close a session and return whether an open session was found."""


class ReplayProtector(Protocol):
    """Atomically enforces strictly increasing sequences per Node session.

    Callers must present requests to this boundary in sequence order. A transport
    that can reorder delivery must restore ordering before calling accept.
    """

    def accept(self, session_id: str, sequence: int) -> bool:
        """Record a new sequence, returning false for duplicates or older values."""

    def forget(self, session_id: str) -> None:
        """Release replay state after the corresponding session is closed."""


class NodeGatewaySecurityBoundary(Protocol):
    """Inbound application interface; it does not expose a network transport."""

    def authenticate_node(
        self, presentation: object, claimed_node_id: str
    ) -> AuthenticationResult:
        """Verify identity without implying trust or capability authorization."""

    def open_session(
        self, presentation: object, claimed_node_id: str
    ) -> SessionResult:
        """Open an authenticated technical session, not a conversation session."""

    def close_session(self, presentation: object, session_id: str) -> bool:
        """Close only the session bound to the currently verified credential."""

    def admit_request(
        self, presentation: object, request: CapabilityRequest
    ) -> GatewayAdmissionResult:
        """Evaluate Gateway admission without granting device execution."""
