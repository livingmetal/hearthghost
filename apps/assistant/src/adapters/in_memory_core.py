"""Ephemeral standard-library adapters for the initial Core runtime.

These adapters make the security boundaries executable without selecting a
database or identity provider. State disappears on restart; no method here
turns an authenticated Node into an administrator or Policy authority.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from threading import RLock

from apps.assistant.src.modules.node_administration import (
    AdministrationAction,
    AdministrationMutation,
    NodeAdministrationRecord,
    StoreApplyOutcome,
    StoreApplyResult,
    StoredAdministrationOperation,
    VerifiedAdministrator,
)
from apps.assistant.src.modules.node_security import (
    CAPABILITY_PATTERN,
    SENSITIVE_LOCAL_CAPABILITIES,
    CapabilityAdvertisement,
    CredentialRecord,
    CredentialStatus,
    NodeRecord,
    NodeSession,
    VerifiedCredential,
)


class RejectingCredentialAuthenticator:
    """Fail-closed placeholder until a reviewed transport is wired."""

    def authenticate(self, presentation: object) -> VerifiedCredential | None:
        return None


class DenyingAdministratorAuthorizer:
    """Never derives administrative authority from caller-controlled context."""

    def authorize(
        self,
        context: object,
        action: AdministrationAction,
        node_id: str,
    ) -> VerifiedAdministrator | None:
        return None


class InMemoryCredentialRepository:
    """Ephemeral authoritative credential records, initially empty."""

    def __init__(self) -> None:
        self._records: dict[str, CredentialRecord] = {}
        self._lock = RLock()

    def get(self, credential_id: str) -> CredentialRecord | None:
        with self._lock:
            return self._records.get(credential_id)

    def register(self, record: CredentialRecord) -> None:
        """Provision test/runtime state without implying Node trust."""

        with self._lock:
            if record.credential_id in self._records:
                raise ValueError("credential already exists")
            self._records[record.credential_id] = record

    def replace(self, record: CredentialRecord) -> None:
        """Replace existing lifecycle metadata without changing its identity."""

        with self._lock:
            prior = self._records.get(record.credential_id)
            if prior is None:
                raise ValueError("credential does not exist")
            if prior.node_id != record.node_id:
                raise ValueError("credential Node binding cannot change")
            if (
                prior.status is not CredentialStatus.ACTIVE
                and record != prior
            ):
                raise ValueError("terminal credential lifecycle cannot change")
            self._records[record.credential_id] = record


class InMemoryNodeRegistry:
    """Atomic ephemeral Node administration store and Gateway read model."""

    def __init__(self) -> None:
        self._nodes: dict[str, NodeAdministrationRecord] = {}
        self._operations: dict[str, StoredAdministrationOperation] = {}
        self._audit_events = []
        self._advertisements: dict[str, tuple[CapabilityAdvertisement, ...]] = {}
        self._lock = RLock()

    def get(self, node_id: str) -> NodeRecord | None:
        """Return the Gateway view without conflating advertisement and grants."""

        with self._lock:
            record = self._nodes.get(node_id)
            if record is None:
                return None
            return NodeRecord(
                node_id=record.node_id,
                trust_state=record.trust_state,
                advertised_capabilities=self._advertisements.get(node_id, ()),
                granted_capabilities=record.granted_capabilities,
            )

    def get_node(self, node_id: str) -> NodeAdministrationRecord | None:
        with self._lock:
            return self._nodes.get(node_id)

    def get_operation(
        self, operation_id: str
    ) -> StoredAdministrationOperation | None:
        with self._lock:
            return self._operations.get(operation_id)

    def is_advertised(self, node_id: str, capability: str) -> bool:
        with self._lock:
            return any(
                item.name == capability
                for item in self._advertisements.get(node_id, ())
            )

    def replace_advertisements(
        self,
        node_id: str,
        advertisements: tuple[CapabilityAdvertisement, ...],
    ) -> None:
        """Replace observed capabilities without granting any capability."""

        if not isinstance(node_id, str) or not node_id:
            raise ValueError("node_id is required")
        if not isinstance(advertisements, tuple):
            raise ValueError("advertisements must be capability records")
        names = set()
        for item in advertisements:
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
                raise ValueError("advertisements violate the Node capability boundary")
            names.add(item.name)
        with self._lock:
            self._advertisements[node_id] = advertisements

    def apply(self, mutation: AdministrationMutation) -> StoreApplyResult:
        """Atomically persist state, idempotency record, and audit metadata."""

        with self._lock:
            prior = self._operations.get(mutation.request.operation_id)
            if prior is not None:
                if prior.request == mutation.request:
                    return StoreApplyResult(
                        StoreApplyOutcome.IDEMPOTENT,
                        prior.record,
                    )
                return StoreApplyResult(StoreApplyOutcome.IDEMPOTENCY_CONFLICT)

            current = self._nodes.get(mutation.request.node_id)
            if mutation.request.action is AdministrationAction.ENROLL_NODE:
                revision_matches = (
                    current is None and mutation.request.expected_revision == 0
                )
            else:
                revision_matches = (
                    current is not None
                    and current.revision == mutation.request.expected_revision
                )
            if not revision_matches:
                return StoreApplyResult(StoreApplyOutcome.REVISION_CONFLICT)

            stored = StoredAdministrationOperation(
                request=mutation.request,
                record=mutation.record,
                audit_event=mutation.audit_event,
            )
            self._nodes[mutation.request.node_id] = mutation.record
            self._audit_events.append(mutation.audit_event)
            self._operations[mutation.request.operation_id] = stored
            return StoreApplyResult(StoreApplyOutcome.APPLIED, mutation.record)

    @property
    def audit_event_count(self) -> int:
        with self._lock:
            return len(self._audit_events)


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, NodeSession] = {}
        self._lock = RLock()

    def get(self, session_id: str) -> NodeSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def put(self, session: NodeSession) -> None:
        with self._lock:
            if session.session_id in self._sessions:
                raise ValueError("session ID was already used")
            self._sessions[session.session_id] = session

    def close(self, session_id: str, closed_at: datetime) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.closed_at is not None:
                return False
            self._sessions[session_id] = replace(session, closed_at=closed_at)
            return True


class InMemoryReplayProtector:
    def __init__(self) -> None:
        self._highest: dict[str, int] = {}
        self._lock = RLock()

    def accept(self, session_id: str, sequence: int) -> bool:
        with self._lock:
            prior = self._highest.get(session_id, 0)
            if sequence <= prior:
                return False
            self._highest[session_id] = sequence
            return True

    def forget(self, session_id: str) -> None:
        with self._lock:
            self._highest.pop(session_id, None)
