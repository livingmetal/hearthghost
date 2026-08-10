"""TLS 1.3 mutual-authentication adapter for connected Node sockets.

The adapter deliberately does not create a listener or interpret application
messages. It converts an already-connected socket into an authenticated TLS
channel and exposes the verified peer certificate to the existing Node Gateway
credential boundary.
"""

from __future__ import annotations

import socket
import ssl
from os import PathLike

from apps.assistant.src.modules.node_security import VerifiedCredential
from apps.assistant.src.ports.node_transport import (
    NodeCertificateIdentityResolver,
)


NODE_ALPN_PROTOCOL = "hearthghost-node/1"


def create_node_server_context(
    *,
    certificate_file: str | PathLike[str],
    private_key_file: str | PathLike[str],
    client_ca_file: str | PathLike[str],
) -> ssl.SSLContext:
    """Build a TLS 1.3 server context requiring a trusted client certificate."""

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    _apply_node_profile(context)
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=client_ca_file)
    context.load_cert_chain(
        certfile=certificate_file,
        keyfile=private_key_file,
    )
    context.num_tickets = 0
    return context


def create_node_client_context(
    *,
    certificate_file: str | PathLike[str],
    private_key_file: str | PathLike[str],
    server_ca_file: str | PathLike[str],
) -> ssl.SSLContext:
    """Build the corresponding mutually-authenticated Node client context."""

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    _apply_node_profile(context)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.load_verify_locations(cafile=server_ca_file)
    context.load_cert_chain(
        certfile=certificate_file,
        keyfile=private_key_file,
    )
    return context


class MutualTlsServerAdapter:
    """Wrap already-accepted sockets without owning network-listener policy."""

    def __init__(self, context: ssl.SSLContext) -> None:
        _require_server_context(context)
        self._context = context

    @property
    def context(self) -> ssl.SSLContext:
        """Return the exact context required by the credential authenticator."""

        return self._context

    def wrap_connected_socket(self, connected_socket: socket.socket) -> ssl.SSLSocket:
        """Perform the initial mutual-TLS handshake and enforce the profile."""

        if not isinstance(connected_socket, socket.socket) or isinstance(
            connected_socket, ssl.SSLSocket
        ):
            raise TypeError("connected_socket must be a plain socket")
        tls_socket = self._context.wrap_socket(
            connected_socket,
            server_side=True,
        )
        try:
            _require_negotiated_profile(tls_socket)
            if not tls_socket.getpeercert(binary_form=True):
                raise ssl.SSLError("Node client certificate is required")
            return tls_socket
        except Exception:
            tls_socket.close()
            raise


class MutualTlsClientAdapter:
    """Node-side wrapper reusable by isolated mock Nodes in a later milestone."""

    def __init__(self, context: ssl.SSLContext) -> None:
        _require_client_context(context)
        self._context = context

    def wrap_connected_socket(
        self,
        connected_socket: socket.socket,
        *,
        server_hostname: str,
    ) -> ssl.SSLSocket:
        """Authenticate the server and enforce the same TLS/ALPN profile."""

        if not isinstance(server_hostname, str) or not server_hostname:
            raise ValueError("server_hostname is required")
        if not isinstance(connected_socket, socket.socket) or isinstance(
            connected_socket, ssl.SSLSocket
        ):
            raise TypeError("connected_socket must be a plain socket")
        tls_socket = self._context.wrap_socket(
            connected_socket,
            server_hostname=server_hostname,
        )
        try:
            _require_negotiated_profile(tls_socket)
            if not tls_socket.getpeercert(binary_form=True):
                raise ssl.SSLError("Core server certificate is required")
            return tls_socket
        except Exception:
            tls_socket.close()
            raise


class MutualTlsCredentialAuthenticator:
    """Turn a certificate from the configured mTLS channel into identity evidence."""

    def __init__(
        self,
        *,
        server_context: ssl.SSLContext,
        identities: NodeCertificateIdentityResolver,
    ) -> None:
        _require_server_context(server_context)
        self._server_context = server_context
        self._identities = identities

    def authenticate(self, presentation: object) -> VerifiedCredential | None:
        """Resolve only peers negotiated by the exact trusted server context."""

        if not isinstance(presentation, ssl.SSLSocket):
            return None
        if presentation.context is not self._server_context:
            return None
        try:
            _require_negotiated_profile(presentation)
            peer_certificate = presentation.getpeercert(binary_form=True)
        except (OSError, ValueError, ssl.SSLError):
            return None
        if not peer_certificate:
            return None
        return self._identities.resolve(peer_certificate)


def _apply_node_profile(context: ssl.SSLContext) -> None:
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    context.set_alpn_protocols([NODE_ALPN_PROTOCOL])
    context.options |= ssl.OP_NO_COMPRESSION
    if hasattr(ssl, "OP_NO_TICKET"):
        context.options |= ssl.OP_NO_TICKET
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        context.verify_flags |= ssl.VERIFY_X509_STRICT


def _require_server_context(context: ssl.SSLContext) -> None:
    if not isinstance(context, ssl.SSLContext):
        raise TypeError("context must be an SSLContext")
    if context.protocol != ssl.PROTOCOL_TLS_SERVER:
        raise ValueError("server context must use PROTOCOL_TLS_SERVER")
    if context.verify_mode != ssl.CERT_REQUIRED:
        raise ValueError("server context must require client certificates")
    if context.minimum_version != ssl.TLSVersion.TLSv1_3:
        raise ValueError("server context must require TLS 1.3")
    if context.maximum_version != ssl.TLSVersion.TLSv1_3:
        raise ValueError("server context must allow only TLS 1.3")
    if context.num_tickets != 0:
        raise ValueError("server context must disable TLS session tickets")


def _require_client_context(context: ssl.SSLContext) -> None:
    if not isinstance(context, ssl.SSLContext):
        raise TypeError("context must be an SSLContext")
    if context.protocol != ssl.PROTOCOL_TLS_CLIENT:
        raise ValueError("client context must use PROTOCOL_TLS_CLIENT")
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise ValueError("client context must verify server certificate and hostname")
    if context.minimum_version != ssl.TLSVersion.TLSv1_3:
        raise ValueError("client context must require TLS 1.3")
    if context.maximum_version != ssl.TLSVersion.TLSv1_3:
        raise ValueError("client context must allow only TLS 1.3")


def _require_negotiated_profile(tls_socket: ssl.SSLSocket) -> None:
    if tls_socket.version() != "TLSv1.3":
        raise ssl.SSLError("Node transport requires TLS 1.3")
    if tls_socket.selected_alpn_protocol() != NODE_ALPN_PROTOCOL:
        raise ssl.SSLError("Node transport ALPN was not negotiated")
