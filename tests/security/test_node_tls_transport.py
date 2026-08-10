from __future__ import annotations

import shutil
import socket
import ssl
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apps.assistant.src.adapters.node_tls_transport import (
    NODE_ALPN_PROTOCOL,
    MutualTlsClientAdapter,
    MutualTlsCredentialAuthenticator,
    MutualTlsServerAdapter,
    create_node_client_context,
    create_node_server_context,
)
from apps.assistant.src.modules.node_security import (
    CapabilityAdvertisement,
    CapabilityRequest,
    CredentialRecord,
    CredentialStatus,
    NodeGatewaySecurity,
    NodeRecord,
    NodeTrustState,
    SecurityReason,
    VerifiedCredential,
)


OPENSSL = shutil.which("openssl")
SERVER_NAME = "core.test.invalid"


@dataclass(frozen=True)
class TestCertificates:
    ca: Path
    server_certificate: Path
    server_key: Path
    node_certificate: Path
    node_key: Path
    unknown_node_certificate: Path
    unknown_node_key: Path


class MemoryCertificateIdentities:
    def __init__(self, bindings: dict[bytes, VerifiedCredential]) -> None:
        self._bindings = bindings

    def resolve(self, peer_certificate_der: bytes) -> VerifiedCredential | None:
        return self._bindings.get(peer_certificate_der)


class BrokenCertificateIdentities:
    def resolve(self, peer_certificate_der: bytes) -> VerifiedCredential | None:
        raise RuntimeError("identity store unavailable")


class FixedClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current


class MemoryRecords:
    def __init__(self, records: dict[str, object]) -> None:
        self.records = records

    def get(self, identifier: str):
        return self.records.get(identifier)


class MemorySessions:
    def __init__(self) -> None:
        self.records = {}

    def get(self, session_id: str):
        return self.records.get(session_id)

    def put(self, session) -> None:
        if session.session_id in self.records:
            raise ValueError("duplicate session")
        self.records[session.session_id] = session

    def close(self, session_id: str, closed_at: datetime) -> bool:
        return False


class MemoryReplay:
    def __init__(self) -> None:
        self.latest = {}

    def accept(self, session_id: str, sequence: int) -> bool:
        previous = self.latest.get(session_id, 0)
        if sequence <= previous:
            return False
        self.latest[session_id] = sequence
        return True

    def forget(self, session_id: str) -> None:
        self.latest.pop(session_id, None)


@unittest.skipUnless(OPENSSL, "OpenSSL CLI is required for ephemeral TLS fixtures")
class NodeTlsTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary_directory = tempfile.TemporaryDirectory(
            prefix="hearthghost-test-only-tls-"
        )
        cls.certificates = _create_test_certificates(
            Path(cls._temporary_directory.name)
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary_directory.cleanup()

    def setUp(self) -> None:
        self.server_context = create_node_server_context(
            certificate_file=self.certificates.server_certificate,
            private_key_file=self.certificates.server_key,
            client_ca_file=self.certificates.ca,
        )
        self.node_context = self._client_context(
            self.certificates.node_certificate,
            self.certificates.node_key,
        )

    def _client_context(
        self, certificate: Path, private_key: Path
    ) -> ssl.SSLContext:
        return create_node_client_context(
            certificate_file=certificate,
            private_key_file=private_key,
            server_ca_file=self.certificates.ca,
        )

    def test_contexts_require_tls13_certificates_hostname_and_no_tickets(self):
        self.assertEqual(self.server_context.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(
            self.server_context.minimum_version, ssl.TLSVersion.TLSv1_3
        )
        self.assertEqual(
            self.server_context.maximum_version, ssl.TLSVersion.TLSv1_3
        )
        self.assertEqual(self.server_context.num_tickets, 0)
        self.assertEqual(self.node_context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(self.node_context.check_hostname)
        self.assertEqual(
            self.node_context.minimum_version, ssl.TLSVersion.TLSv1_3
        )
        self.assertEqual(
            self.node_context.maximum_version, ssl.TLSVersion.TLSv1_3
        )
        if hasattr(ssl, "VERIFY_X509_STRICT"):
            self.assertTrue(
                self.server_context.verify_flags & ssl.VERIFY_X509_STRICT
            )
            self.assertTrue(
                self.node_context.verify_flags & ssl.VERIFY_X509_STRICT
            )

    def test_client_adapter_rejects_a_legacy_tls_profile(self):
        legacy_context = self._client_context(
            self.certificates.node_certificate,
            self.certificates.node_key,
        )
        legacy_context.minimum_version = ssl.TLSVersion.TLSv1_2
        with self.assertRaisesRegex(ValueError, "require TLS 1.3"):
            MutualTlsClientAdapter(legacy_context)

    def test_mutual_tls_socket_negotiates_expected_profile(self):
        server_socket, node_socket = self._handshake(
            self.server_context, self.node_context
        )
        with server_socket, node_socket:
            self.assertEqual(server_socket.version(), "TLSv1.3")
            self.assertEqual(node_socket.version(), "TLSv1.3")
            self.assertEqual(
                server_socket.selected_alpn_protocol(), NODE_ALPN_PROTOCOL
            )
            self.assertEqual(
                node_socket.selected_alpn_protocol(), NODE_ALPN_PROTOCOL
            )
            node_socket.sendall(b"test-only")
            self.assertEqual(server_socket.recv(9), b"test-only")

    def test_server_rejects_client_without_certificate(self):
        anonymous_context = _create_anonymous_test_client_context(
            self.certificates.ca
        )
        server_result, client_result = self._handshake_results(
            self.server_context, anonymous_context
        )
        self._close_result(server_result)
        self._close_result(client_result)
        self.assertTrue(
            isinstance(server_result, ssl.SSLError)
            or isinstance(client_result, ssl.SSLError)
        )

    def test_client_rejects_server_hostname_mismatch(self):
        server_result, client_result = self._handshake_results(
            self.server_context,
            self.node_context,
            server_hostname="wrong.test.invalid",
        )
        self._close_result(server_result)
        self._close_result(client_result)
        self.assertIsInstance(client_result, ssl.SSLCertVerificationError)

    def test_adapters_reject_missing_alpn(self):
        incompatible_context = self._client_context(
            self.certificates.node_certificate,
            self.certificates.node_key,
        )
        incompatible_context.set_alpn_protocols(["not-hearthghost/1"])
        server_result, client_result = self._handshake_results(
            self.server_context, incompatible_context
        )
        self._close_result(server_result)
        self._close_result(client_result)
        self.assertTrue(
            isinstance(server_result, ssl.SSLError)
            or isinstance(client_result, ssl.SSLError)
        )

    def test_authenticator_resolves_only_the_verified_peer_certificate(self):
        server_socket, node_socket = self._handshake(
            self.server_context, self.node_context
        )
        with server_socket, node_socket:
            certificate_der = server_socket.getpeercert(binary_form=True)
            expected = VerifiedCredential("credential-node-a", "node-a")
            authenticator = MutualTlsCredentialAuthenticator(
                server_context=self.server_context,
                identities=MemoryCertificateIdentities(
                    {certificate_der: expected}
                ),
            )
            self.assertEqual(authenticator.authenticate(server_socket), expected)
            self.assertIsNone(authenticator.authenticate(object()))
            self.assertIsNone(authenticator.authenticate(node_socket))

    def test_valid_but_unknown_certificate_is_not_an_identity(self):
        unknown_context = self._client_context(
            self.certificates.unknown_node_certificate,
            self.certificates.unknown_node_key,
        )
        server_socket, node_socket = self._handshake(
            self.server_context, unknown_context
        )
        with server_socket, node_socket:
            authenticator = MutualTlsCredentialAuthenticator(
                server_context=self.server_context,
                identities=MemoryCertificateIdentities({}),
            )
            self.assertIsNone(authenticator.authenticate(server_socket))

    def test_mutual_tls_authentication_does_not_grant_node_authority(self):
        server_socket, node_socket = self._handshake(
            self.server_context, self.node_context
        )
        with server_socket, node_socket:
            certificate_der = server_socket.getpeercert(binary_form=True)
            verified = VerifiedCredential("credential-node-a", "node-a")
            authenticator = MutualTlsCredentialAuthenticator(
                server_context=self.server_context,
                identities=MemoryCertificateIdentities(
                    {certificate_der: verified}
                ),
            )
            now = datetime(2026, 1, 1, tzinfo=timezone.utc)
            gateway = NodeGatewaySecurity(
                authenticator=authenticator,
                credentials=MemoryRecords(
                    {
                        verified.credential_id: CredentialRecord(
                            credential_id=verified.credential_id,
                            node_id=verified.node_id,
                            credential_type="x509",
                            issued_at=now - timedelta(days=1),
                            status=CredentialStatus.ACTIVE,
                            expires_at=now + timedelta(days=1),
                        )
                    }
                ),
                nodes=MemoryRecords(
                    {
                        verified.node_id: NodeRecord(
                            node_id=verified.node_id,
                            trust_state=NodeTrustState.UNTRUSTED,
                            advertised_capabilities=(
                                CapabilityAdvertisement("test.echo", False),
                            ),
                            granted_capabilities=frozenset(),
                        )
                    }
                ),
                sessions=MemorySessions(),
                replay=MemoryReplay(),
                clock=FixedClock(now),
                session_lifetime=timedelta(minutes=5),
            )

            authentication = gateway.authenticate_node(server_socket, "node-a")
            self.assertTrue(authentication.authenticated)
            session_result = gateway.open_session(server_socket, "node-a")
            self.assertTrue(session_result.opened)
            admission = gateway.admit_request(
                server_socket,
                CapabilityRequest(
                    request_id="request-1",
                    session_id=session_result.session.session_id,
                    sequence=1,
                    capability="test.echo",
                ),
            )
            self.assertFalse(admission.admitted)
            self.assertEqual(admission.reason, SecurityReason.NODE_NOT_TRUSTED)

    def test_identity_store_failure_is_denied_by_node_gateway(self):
        server_socket, node_socket = self._handshake(
            self.server_context, self.node_context
        )
        with server_socket, node_socket:
            authenticator = MutualTlsCredentialAuthenticator(
                server_context=self.server_context,
                identities=BrokenCertificateIdentities(),
            )
            gateway = NodeGatewaySecurity(
                authenticator=authenticator,
                credentials=MemoryRecords({}),
                nodes=MemoryRecords({}),
                sessions=MemorySessions(),
                replay=MemoryReplay(),
                clock=FixedClock(datetime(2026, 1, 1, tzinfo=timezone.utc)),
                session_lifetime=timedelta(minutes=5),
            )
            result = gateway.authenticate_node(server_socket, "node-a")
            self.assertFalse(result.authenticated)
            self.assertEqual(
                result.reason, SecurityReason.AUTHENTICATOR_UNAVAILABLE
            )

    def test_adapter_owns_no_listener_or_network_address(self):
        server_adapter = MutualTlsServerAdapter(self.server_context)
        self.assertFalse(hasattr(server_adapter, "bind"))
        self.assertFalse(hasattr(server_adapter, "listen"))
        self.assertFalse(hasattr(server_adapter, "address"))

    def _handshake(
        self,
        server_context: ssl.SSLContext,
        client_context: ssl.SSLContext,
    ) -> tuple[ssl.SSLSocket, ssl.SSLSocket]:
        server_result, client_result = self._handshake_results(
            server_context, client_context
        )
        if isinstance(server_result, BaseException):
            self._close_result(client_result)
            raise server_result
        if isinstance(client_result, BaseException):
            self._close_result(server_result)
            raise client_result
        return server_result, client_result

    def _handshake_results(
        self,
        server_context: ssl.SSLContext,
        client_context: ssl.SSLContext,
        *,
        server_hostname: str = SERVER_NAME,
    ) -> tuple[ssl.SSLSocket | BaseException, ssl.SSLSocket | BaseException]:
        server_plain, client_plain = socket.socketpair()
        server_plain.settimeout(5)
        client_plain.settimeout(5)
        server_adapter = MutualTlsServerAdapter(server_context)
        client_adapter = MutualTlsClientAdapter(client_context)

        def capture(callable_):
            try:
                return callable_()
            except BaseException as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            server_future = executor.submit(
                capture,
                lambda: server_adapter.wrap_connected_socket(server_plain),
            )
            client_future = executor.submit(
                capture,
                lambda: client_adapter.wrap_connected_socket(
                    client_plain,
                    server_hostname=server_hostname,
                ),
            )
            return server_future.result(), client_future.result()

    @staticmethod
    def _close_result(result: ssl.SSLSocket | BaseException) -> None:
        if isinstance(result, ssl.SSLSocket):
            result.close()


def _create_test_certificates(directory: Path) -> TestCertificates:
    ca_key = directory / "TEST-ONLY-ca.key"
    ca_certificate = directory / "TEST-ONLY-ca.pem"
    _run_openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-sha256",
        "-days",
        "2",
        "-subj",
        "/CN=HearthGhost TEST ONLY Ephemeral CA",
        "-addext",
        "basicConstraints=critical,CA:TRUE,pathlen:0",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
        "-keyout",
        str(ca_key),
        "-out",
        str(ca_certificate),
    )

    server_certificate, server_key = _create_leaf_certificate(
        directory,
        name="server",
        subject="/CN=HearthGhost TEST ONLY Core",
        ca_certificate=ca_certificate,
        ca_key=ca_key,
        extended_key_usage="serverAuth",
        subject_alt_name=f"DNS:{SERVER_NAME}",
    )
    node_certificate, node_key = _create_leaf_certificate(
        directory,
        name="node-a",
        subject="/CN=HearthGhost TEST ONLY Node A",
        ca_certificate=ca_certificate,
        ca_key=ca_key,
        extended_key_usage="clientAuth",
    )
    unknown_certificate, unknown_key = _create_leaf_certificate(
        directory,
        name="unknown-node",
        subject="/CN=HearthGhost TEST ONLY Unknown Node",
        ca_certificate=ca_certificate,
        ca_key=ca_key,
        extended_key_usage="clientAuth",
    )
    return TestCertificates(
        ca=ca_certificate,
        server_certificate=server_certificate,
        server_key=server_key,
        node_certificate=node_certificate,
        node_key=node_key,
        unknown_node_certificate=unknown_certificate,
        unknown_node_key=unknown_key,
    )


def _create_anonymous_test_client_context(
    server_ca_file: Path,
) -> ssl.SSLContext:
    """Build an intentionally incomplete context for one denial test only."""

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.load_verify_locations(cafile=server_ca_file)
    context.set_alpn_protocols([NODE_ALPN_PROTOCOL])
    context.options |= ssl.OP_NO_COMPRESSION
    if hasattr(ssl, "OP_NO_TICKET"):
        context.options |= ssl.OP_NO_TICKET
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        context.verify_flags |= ssl.VERIFY_X509_STRICT
    return context


def _create_leaf_certificate(
    directory: Path,
    *,
    name: str,
    subject: str,
    ca_certificate: Path,
    ca_key: Path,
    extended_key_usage: str,
    subject_alt_name: str | None = None,
) -> tuple[Path, Path]:
    private_key = directory / f"TEST-ONLY-{name}.key"
    signing_request = directory / f"TEST-ONLY-{name}.csr"
    certificate = directory / f"TEST-ONLY-{name}.pem"
    extensions = directory / f"TEST-ONLY-{name}.ext"
    extension_lines = [
        "basicConstraints=critical,CA:FALSE",
        "keyUsage=critical,digitalSignature,keyEncipherment",
        f"extendedKeyUsage={extended_key_usage}",
        "subjectKeyIdentifier=hash",
        "authorityKeyIdentifier=keyid,issuer",
    ]
    if subject_alt_name is not None:
        extension_lines.append(f"subjectAltName={subject_alt_name}")
    extensions.write_text("\n".join(extension_lines) + "\n", encoding="ascii")

    _run_openssl(
        "req",
        "-new",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-sha256",
        "-subj",
        subject,
        "-keyout",
        str(private_key),
        "-out",
        str(signing_request),
    )
    _run_openssl(
        "x509",
        "-req",
        "-in",
        str(signing_request),
        "-CA",
        str(ca_certificate),
        "-CAkey",
        str(ca_key),
        "-CAcreateserial",
        "-days",
        "2",
        "-sha256",
        "-extfile",
        str(extensions),
        "-out",
        str(certificate),
    )
    return certificate, private_key


def _run_openssl(*arguments: str) -> None:
    subprocess.run(
        [OPENSSL, *arguments],
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15,
    )


if __name__ == "__main__":
    unittest.main()
