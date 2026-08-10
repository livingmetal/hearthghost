"""Ports for the privileged Node administration boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from apps.assistant.src.modules.node_administration import (
        AdministrationAction,
        AdministrationMutation,
        AdministrationRequest,
        AdministrationResult,
        NodeAdministrationRecord,
        StoreApplyResult,
        StoredAdministrationOperation,
        VerifiedAdministrator,
    )


class AdministratorAuthorizer(Protocol):
    """Performs action-specific administrator authentication and authorization."""

    def authorize(
        self,
        context: object,
        action: AdministrationAction,
        node_id: str,
    ) -> VerifiedAdministrator | None:
        """Return bound administrator evidence, or ``None`` when denied."""


class NodeCapabilityReader(Protocol):
    """Reads current Node-advertised capability state without granting it."""

    def is_advertised(self, node_id: str, capability: str) -> bool:
        """Return whether the Node currently advertises the capability."""


class AtomicNodeAdministrationStore(Protocol):
    """Stores Node administration state and audit metadata atomically.

    ``apply`` must check operation idempotency and the expected revision in the
    same atomic operation that persists both the new Node record and audit event.
    It must never expose a state change without its corresponding audit record.
    """

    def get_node(self, node_id: str) -> NodeAdministrationRecord | None:
        """Return the current enrolled Node administration record."""

    def get_operation(
        self, operation_id: str
    ) -> StoredAdministrationOperation | None:
        """Return a previously completed operation for idempotent retry."""

    def apply(self, mutation: AdministrationMutation) -> StoreApplyResult:
        """Atomically apply one revisioned, audited, idempotent mutation."""


class NodeAdministrationBoundary(Protocol):
    """Privileged administration interface; it grants no action execution."""

    def administer(
        self, context: object, request: AdministrationRequest
    ) -> AdministrationResult:
        """Apply an explicitly authorized Node registry mutation."""
