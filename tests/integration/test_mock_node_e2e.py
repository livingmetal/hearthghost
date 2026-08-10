from __future__ import annotations

import socket
import ssl
import struct
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from apps.assistant.src.adapters.node_gateway_protocol import (
    MAX_FRAME_BYTES,
    NodeGatewayProtocol,
    NodeProtocolError,
    read_gateway_message,
)
from apps.assistant.src.adapters.node_tls_transport import (
    MutualTlsCredentialAuthenticator,
    MutualTlsServerAdapter,
    create_node_client_context,
    create_node_server_context,
)
from apps.assistant.src.modules.node_administration import (
    AdministrationAction,
    AdministrationRequest,
    VerifiedAdministrator,
)
from apps.assistant.src.modules.node_security import (
    CapabilityAdvertisement,
    CredentialRecord,
    CredentialStatus,
    NodeTrustState,
)
from apps.assistant.src.runtime.core import build_core
from apps.mock_node.src.client import (
    MOCK_NODE_CAPABILITIES,
    MOCK_NODE_ID,
    MockNode,
)
from tests.support.tls_certificates import (
    OPENSSL,
    SERVER_NAME,
    create_test_certificates,
)


CREDENTIAL_ID = "mock-node-credential"
ADMIN_CONTEXT = object()


class ExactCertificateResolver:
    def __init__(self, peer_certificate: bytes) -> None:
        from apps.assistant.src.modules.node_security import VerifiedCredential

        self._peer_certificate = peer_certificate
        self._verified = VerifiedCredential(CREDENTIAL_ID, MOCK_NODE_ID)

    def resolve(self, peer_certificate_der: bytes):
        if peer_certificate_der != self._peer_certificate:
            return None
        return self._verified


class TestAdministratorAuthorizer:
    def authorize(self, context, action, node_id):
        if context is not ADMIN_CONTEXT:
            return None
        return VerifiedAdministrator("test-harness-admin", action, node_id)


@unittest.skipUnless(OPENSSL, "OpenSSL CLI is required for ephemeral TLS fixtures")
class MockNodeEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary_directory = tempfile.TemporaryDirectory(
            prefix="hearthghost-test-only-mock-node-"
        )
        cls.certificates = create_test_certificates(
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
        self.client_context = create_node_client_context(
            certificate_file=self.certificates.node_certificate,
            private_key_file=self.certificates.node_key,
            server_ca_file=self.certificates.ca,
        )
        peer_der = ssl.PEM_cert_to_DER_cert(
            self.certificates.node_certificate.read_text(encoding="ascii")
        )
        authenticator = MutualTlsCredentialAuthenticator(
            server_context=self.server_context,
            identities=ExactCertificateResolver(peer_der),
        )
        self.core = build_core(
            authenticator=authenticator,
            administrator_authorizer=TestAdministratorAuthorizer(),
        )
        self.protocol = NodeGatewayProtocol(self.core.node_gateway)
        now = datetime.now(timezone.utc)
        self.active_credential = CredentialRecord(
            credential_id=CREDENTIAL_ID,
            node_id=MOCK_NODE_ID,
            credential_type="x509",
            issued_at=now - timedelta(minutes=1),
            status=CredentialStatus.ACTIVE,
            expires_at=now + timedelta(days=1),
        )
        self.core.credentials.register(self.active_credential)
        self.core.registry.replace_advertisements(
            MOCK_NODE_ID,
            tuple(
                CapabilityAdvertisement(name, False)
                for name in MOCK_NODE_CAPABILITIES
            ),
        )

    def test_full_mock_node_security_lifecycle(self):
        server_channel, mock = self._connect()
        try:
            unknown = self._exchange(server_channel, mock.open_session)
            self.assertFalse(unknown.accepted)
            self.assertEqual(unknown.reason_code, "session_not_authenticated")
        finally:
            server_channel.close()
            mock.close()

        enrolled = self._administer(AdministrationAction.ENROLL_NODE, 0)
        self.assertTrue(enrolled.succeeded)
        self.assertEqual(enrolled.record.trust_state, NodeTrustState.UNTRUSTED)
        self.assertEqual(frozenset(), enrolled.record.granted_capabilities)
        trusted = self._administer(
            AdministrationAction.SET_TRUST,
            1,
            trust_state=NodeTrustState.TRUSTED,
        )
        granted = self._administer(
            AdministrationAction.GRANT_CAPABILITY,
            2,
            capability="test.echo",
        )
        self.assertTrue(trusted.succeeded)
        self.assertTrue(granted.succeeded)

        first_server, first_mock = self._connect()
        try:
            opened = self._exchange(first_server, first_mock.open_session)
            self.assertTrue(opened.accepted)
            first_session_id = first_mock.session_id

            admitted = self._exchange(
                first_server,
                lambda: first_mock.request_capability("test.echo", sequence=1),
            )
            self.assertTrue(admitted.accepted)
            self.assertEqual(admitted.reason_code, "gateway_admitted")

            replay = self._exchange(
                first_server,
                lambda: first_mock.request_capability("test.echo", sequence=1),
            )
            self.assertFalse(replay.accepted)
            self.assertEqual(replay.reason_code, "replay_detected")

            revoked = self._administer(
                AdministrationAction.REVOKE_CAPABILITY,
                3,
                capability="test.echo",
            )
            self.assertTrue(revoked.succeeded)
            no_grant = self._exchange(
                first_server,
                lambda: first_mock.request_capability("test.echo", sequence=2),
            )
            self.assertFalse(no_grant.accepted)
            self.assertEqual(no_grant.reason_code, "capability_not_granted")

            self._administer(
                AdministrationAction.GRANT_CAPABILITY,
                4,
                capability="test.echo",
            )
            self._administer(
                AdministrationAction.SET_TRUST,
                5,
                trust_state=NodeTrustState.UNTRUSTED,
            )
            no_trust = self._exchange(
                first_server,
                lambda: first_mock.request_capability("test.echo", sequence=3),
            )
            self.assertFalse(no_trust.accepted)
            self.assertEqual(no_trust.reason_code, "node_not_trusted")
            self._administer(
                AdministrationAction.SET_TRUST,
                6,
                trust_state=NodeTrustState.TRUSTED,
            )
        finally:
            first_server.close()
            first_mock.close()

        second_server, second_mock = self._connect()
        try:
            reopened = self._exchange(second_server, second_mock.open_session)
            self.assertTrue(reopened.accepted)
            self.assertNotEqual(second_mock.session_id, first_session_id)
            after_reconnect = self._exchange(
                second_server,
                lambda: second_mock.request_capability("test.echo", sequence=1),
            )
            self.assertTrue(after_reconnect.accepted)

            now = datetime.now(timezone.utc)
            self.core.credentials.replace(
                replace(
                    self.active_credential,
                    status=CredentialStatus.REVOKED,
                    revoked_at=now,
                )
            )
            revoked_credential = self._exchange(
                second_server,
                lambda: second_mock.request_capability("test.echo", sequence=2),
            )
            self.assertFalse(revoked_credential.accepted)
            self.assertEqual(
                revoked_credential.reason_code,
                "credential_revoked",
            )
            with self.assertRaisesRegex(ValueError, "terminal credential"):
                self.core.credentials.replace(self.active_credential)
        finally:
            second_server.close()
            second_mock.close()

        third_server, third_mock = self._connect()
        try:
            denied_reconnect = self._exchange(third_server, third_mock.open_session)
            self.assertFalse(denied_reconnect.accepted)
            self.assertEqual(
                denied_reconnect.reason_code,
                "session_not_authenticated",
            )
        finally:
            third_server.close()
            third_mock.close()

    def test_mock_node_has_only_harmless_declared_capabilities(self):
        self.assertEqual(
            MOCK_NODE_CAPABILITIES,
            ("display", "speaker", "test.echo"),
        )
        mock = MockNode()
        mock.session_id = "session-for-local-validation"
        with self.assertRaisesRegex(ValueError, "undeclared capability"):
            mock.request_capability("mobility.goto", sequence=1)

    def test_authenticated_untrusted_node_cannot_use_declared_capability(self):
        enrolled = self._administer(AdministrationAction.ENROLL_NODE, 0)
        self.assertTrue(enrolled.succeeded)

        server_channel, mock = self._connect()
        try:
            opened = self._exchange(server_channel, mock.open_session)
            self.assertTrue(opened.accepted)
            denied = self._exchange(
                server_channel,
                lambda: mock.request_capability("test.echo", sequence=1),
            )
            self.assertFalse(denied.accepted)
            self.assertEqual(denied.reason_code, "node_not_trusted")
        finally:
            server_channel.close()
            mock.close()

    def test_node_revocation_invalidates_open_session_and_reconnect(self):
        self._administer(AdministrationAction.ENROLL_NODE, 0)
        self._administer(
            AdministrationAction.SET_TRUST,
            1,
            trust_state=NodeTrustState.TRUSTED,
        )
        self._administer(
            AdministrationAction.GRANT_CAPABILITY,
            2,
            capability="test.echo",
        )

        server_channel, mock = self._connect()
        try:
            opened = self._exchange(server_channel, mock.open_session)
            self.assertTrue(opened.accepted)
            admitted = self._exchange(
                server_channel,
                lambda: mock.request_capability("test.echo", sequence=1),
            )
            self.assertTrue(admitted.accepted)

            revoked = self._administer(AdministrationAction.REVOKE_NODE, 3)
            self.assertTrue(revoked.succeeded)
            denied = self._exchange(
                server_channel,
                lambda: mock.request_capability("test.echo", sequence=2),
            )
            self.assertFalse(denied.accepted)
            self.assertEqual(denied.reason_code, "node_revoked")
        finally:
            server_channel.close()
            mock.close()

        reconnect_server, reconnect_mock = self._connect()
        try:
            denied_reconnect = self._exchange(
                reconnect_server,
                reconnect_mock.open_session,
            )
            self.assertFalse(denied_reconnect.accepted)
            self.assertEqual(
                denied_reconnect.reason_code,
                "session_not_authenticated",
            )
        finally:
            reconnect_server.close()
            reconnect_mock.close()

    def test_protocol_rejects_plaintext_and_oversized_frames(self):
        plain_server, plain_client = socket.socketpair()
        try:
            with self.assertRaisesRegex(NodeProtocolError, "authenticated TLS"):
                self.protocol.handle_next(plain_server)
            plain_client.sendall(struct.pack("!I", MAX_FRAME_BYTES + 1))
            with self.assertRaisesRegex(NodeProtocolError, "frame size"):
                read_gateway_message(plain_server)
        finally:
            plain_server.close()
            plain_client.close()

    def _administer(
        self,
        action: AdministrationAction,
        expected_revision: int,
        *,
        trust_state: NodeTrustState | None = None,
        capability: str | None = None,
    ):
        return self.core.node_administration.administer(
            ADMIN_CONTEXT,
            AdministrationRequest(
                operation_id=str(uuid4()),
                correlation_id="mock-node-e2e",
                action=action,
                node_id=MOCK_NODE_ID,
                expected_revision=expected_revision,
                trust_state=trust_state,
                capability=capability,
            ),
        )

    def _connect(self) -> tuple[ssl.SSLSocket, MockNode]:
        server_plain, node_plain = socket.socketpair()
        server_plain.settimeout(5)
        node_plain.settimeout(5)
        server_adapter = MutualTlsServerAdapter(self.server_context)
        mock = MockNode()
        with ThreadPoolExecutor(max_workers=2) as executor:
            server_future = executor.submit(
                server_adapter.wrap_connected_socket,
                server_plain,
            )
            node_future = executor.submit(
                mock.connect,
                node_plain,
                context=self.client_context,
                server_hostname=SERVER_NAME,
            )
            server_channel = server_future.result()
            node_future.result()
        return server_channel, mock

    def _exchange(self, server_channel, client_call):
        with ThreadPoolExecutor(max_workers=1) as executor:
            server_future = executor.submit(
                self.protocol.handle_next,
                server_channel,
            )
            client_result = client_call()
            server_result = server_future.result()
        self.assertEqual(client_result, server_result)
        return client_result


if __name__ == "__main__":
    unittest.main()
