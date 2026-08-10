from __future__ import annotations

import socket
import ssl
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from apps.assistant.src.adapters.conversation_protocol import (
    ConversationProtocol,
    read_conversation_result,
)
from apps.assistant.src.adapters.fake_llm import FakeLLMAdapter
from apps.assistant.src.adapters.node_gateway_protocol import (
    NodeGatewayProtocol,
    NodeProtocolError,
    write_frame,
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
from apps.client_node.src.client import (
    CLIENT_NODE_CAPABILITIES,
    CLIENT_NODE_ID,
    DevelopmentTextClientNode,
)
from tests.support.tls_certificates import (
    OPENSSL,
    SERVER_NAME,
    create_test_certificates,
)


CREDENTIAL_ID = "development-client-credential"
ADMIN_CONTEXT = object()


class ExactClientCertificateResolver:
    def __init__(self, peer_certificate: bytes) -> None:
        from apps.assistant.src.modules.node_security import VerifiedCredential

        self._peer_certificate = peer_certificate
        self._verified = VerifiedCredential(CREDENTIAL_ID, CLIENT_NODE_ID)

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
class TextWalkingSkeletonEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary_directory = tempfile.TemporaryDirectory(
            prefix="hearthghost-test-only-text-client-"
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
            identities=ExactClientCertificateResolver(peer_der),
        )
        self.fake_llm = FakeLLMAdapter()
        self.core = build_core(
            authenticator=authenticator,
            administrator_authorizer=TestAdministratorAuthorizer(),
            llm=self.fake_llm,
        )
        self.node_protocol = NodeGatewayProtocol(self.core.node_gateway)
        self.conversation_protocol = ConversationProtocol(
            gateway=self.core.node_gateway,
            conversation=self.core.conversation,
            orchestrator=self.core.orchestrator,
        )
        now = datetime.now(timezone.utc)
        self.active_credential = CredentialRecord(
            credential_id=CREDENTIAL_ID,
            node_id=CLIENT_NODE_ID,
            credential_type="x509",
            issued_at=now - timedelta(minutes=1),
            status=CredentialStatus.ACTIVE,
            expires_at=now + timedelta(days=1),
        )
        self.core.credentials.register(self.active_credential)
        self.core.registry.replace_advertisements(
            CLIENT_NODE_ID,
            tuple(
                CapabilityAdvertisement(name, False)
                for name in CLIENT_NODE_CAPABILITIES
            ),
        )

    def test_text_walking_skeleton_through_fake_privacy_llm_and_semantic_events(self):
        self._approve_text_client()
        server, client = self._connect()
        try:
            opened_node = self._gateway_exchange(server, client.open_session)
            self.assertTrue(opened_node.accepted)
            node_session_id = client.session_id

            opened = self._conversation_exchange(
                server,
                lambda: client.open_conversation(sequence=1),
            )
            self.assertTrue(opened.accepted)
            self.assertNotEqual(opened.conversation_session_id, node_session_id)
            self.assertEqual(
                [event["payload"]["state"] for event in opened.events],
                ["listening"],
            )

            schedule = self._conversation_exchange(
                server,
                lambda: client.send_text(
                    "오늘 회사에서 담당한 일이 뭐였어?",
                    sequence=2,
                ),
            )
            self.assertTrue(schedule.accepted)
            self.assertIn("Fake HearthGhost response", schedule.response_text)
            self.assertEqual(
                [event["payload"]["state"] for event in schedule.events],
                ["listening", "thinking", "speaking", "engaged"],
            )
            self.assertEqual(client.conversation_session_id, opened.conversation_session_id)

            light = self._conversation_exchange(
                server,
                lambda: client.send_text("거실 불 꺼줘", sequence=3),
            )
            self.assertTrue(light.accepted)
            self.assertIn("no device is connected", light.response_text)
            self.assertEqual(len(light.proposed_actions), 1)
            self.assertEqual(
                light.proposed_actions[0]["authorization_status"],
                "pending_policy",
            )
            self.assertEqual(
                light.proposed_actions[0]["execution_status"],
                "not_executed",
            )
            self.assertFalse(hasattr(self.conversation_protocol, "execute"))

            ended = self._conversation_exchange(
                server,
                lambda: client.close_conversation(sequence=4),
            )
            self.assertTrue(ended.accepted)
            self.assertEqual(ended.events[0]["payload"]["state"], "sleeping")
            self.assertIsNone(client.conversation_session_id)
            self.assertEqual(client.session_id, node_session_id)
            self.assertEqual(len(self.fake_llm.requests), 2)
        finally:
            server.close()
            client.close()

    def test_unknown_client_cannot_open_node_session(self):
        server, client = self._connect()
        try:
            result = self._gateway_exchange(server, client.open_session)
            self.assertFalse(result.accepted)
            self.assertEqual(result.reason_code, "session_not_authenticated")
        finally:
            server.close()
            client.close()

    def test_untrusted_and_ungranted_clients_cannot_open_conversation(self):
        self._administer(AdministrationAction.ENROLL_NODE, 0)
        server, client = self._connect()
        try:
            self.assertTrue(self._gateway_exchange(server, client.open_session).accepted)
            denied = self._conversation_exchange(
                server,
                lambda: client.open_conversation(sequence=1),
            )
            self.assertFalse(denied.accepted)
            self.assertEqual(denied.reason_code, "node_not_trusted")

            self._administer(
                AdministrationAction.SET_TRUST,
                1,
                trust_state=NodeTrustState.TRUSTED,
            )
            still_denied = self._conversation_exchange(
                server,
                lambda: client.open_conversation(sequence=2),
            )
            self.assertFalse(still_denied.accepted)
            self.assertEqual(still_denied.reason_code, "capability_not_granted")
        finally:
            server.close()
            client.close()

    def test_conversation_replay_is_denied(self):
        self._approve_text_client()
        server, client = self._connect()
        try:
            self._gateway_exchange(server, client.open_session)
            self.assertTrue(
                self._conversation_exchange(
                    server,
                    lambda: client.open_conversation(sequence=1),
                ).accepted
            )
            replay = self._conversation_exchange(
                server,
                lambda: client.send_text("replay", sequence=1),
            )
            self.assertFalse(replay.accepted)
            self.assertEqual(replay.reason_code, "replay_detected")
            self.assertEqual(self.fake_llm.requests, [])
        finally:
            server.close()
            client.close()

    def test_revoked_credential_blocks_open_conversation(self):
        self._approve_text_client()
        server, client = self._connect()
        try:
            self._gateway_exchange(server, client.open_session)
            now = datetime.now(timezone.utc)
            self.core.credentials.replace(
                replace(
                    self.active_credential,
                    status=CredentialStatus.REVOKED,
                    revoked_at=now,
                )
            )
            denied = self._conversation_exchange(
                server,
                lambda: client.open_conversation(sequence=1),
            )
            self.assertFalse(denied.accepted)
            self.assertEqual(denied.reason_code, "credential_revoked")
        finally:
            server.close()
            client.close()

    def test_revoked_node_blocks_conversation_follow_up(self):
        self._approve_text_client()
        server, client = self._connect()
        try:
            self._gateway_exchange(server, client.open_session)
            self._conversation_exchange(
                server,
                lambda: client.open_conversation(sequence=1),
            )
            self._administer(AdministrationAction.REVOKE_NODE, 3)
            denied = self._conversation_exchange(
                server,
                lambda: client.send_text("hello", sequence=2),
            )
            self.assertFalse(denied.accepted)
            self.assertEqual(denied.reason_code, "node_revoked")
            self.assertEqual(self.fake_llm.requests, [])
        finally:
            server.close()
            client.close()

    def test_client_rejects_renderer_specific_or_malformed_state(self):
        sender, receiver = socket.socketpair()
        try:
            write_frame(
                sender,
                {
                    "contract_version": "1.0",
                    "message_type": "conversation.result",
                    "request_id": str(uuid4()),
                    "outcome": "accepted",
                    "reason_code": "allowed",
                    "events": [
                        {
                            "type": "character.state",
                            "payload": {
                                "state": "speaking_happy",
                                "blendshape": "Fcl_MTH_A",
                            },
                        }
                    ],
                },
            )
            with self.assertRaisesRegex(NodeProtocolError, "semantic event"):
                read_conversation_result(receiver)
        finally:
            sender.close()
            receiver.close()

    def test_conversation_protocol_rejects_plaintext(self):
        server, client = socket.socketpair()
        try:
            with self.assertRaisesRegex(NodeProtocolError, "authenticated TLS"):
                self.conversation_protocol.handle_next(server)
        finally:
            server.close()
            client.close()

    def _approve_text_client(self) -> None:
        self._administer(AdministrationAction.ENROLL_NODE, 0)
        self._administer(
            AdministrationAction.SET_TRUST,
            1,
            trust_state=NodeTrustState.TRUSTED,
        )
        self._administer(
            AdministrationAction.GRANT_CAPABILITY,
            2,
            capability="conversation.text",
        )

    def _administer(
        self,
        action,
        expected_revision,
        *,
        trust_state=None,
        capability=None,
    ):
        return self.core.node_administration.administer(
            ADMIN_CONTEXT,
            AdministrationRequest(
                operation_id=str(uuid4()),
                correlation_id="text-walking-skeleton-e2e",
                action=action,
                node_id=CLIENT_NODE_ID,
                expected_revision=expected_revision,
                trust_state=trust_state,
                capability=capability,
            ),
        )

    def _connect(self):
        server_plain, client_plain = socket.socketpair()
        server_plain.settimeout(5)
        client_plain.settimeout(5)
        server_adapter = MutualTlsServerAdapter(self.server_context)
        client = DevelopmentTextClientNode()
        with ThreadPoolExecutor(max_workers=2) as executor:
            server_future = executor.submit(
                server_adapter.wrap_connected_socket,
                server_plain,
            )
            client_future = executor.submit(
                client.connect,
                client_plain,
                context=self.client_context,
                server_hostname=SERVER_NAME,
            )
            server_channel = server_future.result()
            client_future.result()
        return server_channel, client

    def _gateway_exchange(self, server_channel, client_call):
        with ThreadPoolExecutor(max_workers=1) as executor:
            server_future = executor.submit(self.node_protocol.handle_next, server_channel)
            client_result = client_call()
            server_result = server_future.result()
        self.assertEqual(client_result, server_result)
        return client_result

    def _conversation_exchange(self, server_channel, client_call):
        with ThreadPoolExecutor(max_workers=1) as executor:
            server_future = executor.submit(
                self.conversation_protocol.handle_next,
                server_channel,
            )
            client_result = client_call()
            server_result = server_future.result()
        self.assertEqual(client_result, server_result)
        return client_result


if __name__ == "__main__":
    unittest.main()
