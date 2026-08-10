"""Ports used by the secure Node transport adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from apps.assistant.src.modules.node_security import VerifiedCredential


class NodeCertificateIdentityResolver(Protocol):
    """Maps a TLS-verified public certificate to a credential binding.

    Certificate-chain validation belongs to the TLS implementation. This port
    resolves the verified DER certificate to authoritative public identity
    evidence; it does not grant Node trust, a capability, or execution authority.
    """

    def resolve(
        self, peer_certificate_der: bytes
    ) -> VerifiedCredential | None:
        """Return the known credential binding, or ``None`` when unknown."""
