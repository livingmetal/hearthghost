import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from apps.assistant.src.modules.node_security import (
    AuthenticationResult,
    CapabilityAdvertisement,
    CapabilityRequest,
    CredentialRecord,
    CredentialStatus,
    GatewayAdmissionResult,
    NodeGatewaySecurity,
    NodeRecord,
    NodeSession,
    NodeTrustState,
    SecurityReason,
    VerifiedCredential,
)


NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
NODE_ID = "livingroom-main"
CREDENTIAL_ID = "credential-a"


class FixedClock:
    def __init__(self, now=NOW):
        self.value = now

    def now(self):
        return self.value


class StubAuthenticator:
    def __init__(self, verified=None, error=None):
        self.verified = verified
        self.error = error

    def authenticate(self, presentation):
        if self.error is not None:
            raise self.error
        return self.verified


class DictionaryRepository:
    def __init__(self, values):
        self.values = values

    def get(self, item_id):
        return self.values.get(item_id)


class InMemorySessions:
    def __init__(self):
        self.values = {}

    def get(self, session_id):
        return self.values.get(session_id)

    def put(self, session):
        if session.session_id in self.values:
            raise ValueError("session identifier was already used")
        self.values[session.session_id] = session

    def close(self, session_id, closed_at):
        session = self.values.get(session_id)
        if session is None or session.closed_at is not None:
            return False
        self.values[session_id] = replace(session, closed_at=closed_at)
        return True


class StrictSequenceReplay:
    def __init__(self):
        self.highest = {}
        self.unavailable = False

    def accept(self, session_id, sequence):
        if self.unavailable:
            raise RuntimeError("replay state unavailable")
        previous = self.highest.get(session_id, 0)
        if sequence <= previous:
            return False
        self.highest[session_id] = sequence
        return True

    def forget(self, session_id):
        self.highest.pop(session_id, None)


class NodeGatewaySecurityTests(unittest.TestCase):
    def setUp(self):
        self.presentation = object()
        self.clock = FixedClock()
        self.credential = CredentialRecord(
            credential_id=CREDENTIAL_ID,
            node_id=NODE_ID,
            credential_type="node_identity",
            issued_at=NOW - timedelta(days=30),
            expires_at=NOW + timedelta(days=335),
            status=CredentialStatus.ACTIVE,
        )
        self.node = NodeRecord(
            node_id=NODE_ID,
            trust_state=NodeTrustState.TRUSTED,
            advertised_capabilities=(
                CapabilityAdvertisement("speaker.play", False),
                CapabilityAdvertisement("camera.snapshot", True),
            ),
            granted_capabilities=frozenset({"speaker.play"}),
        )
        self.credentials = DictionaryRepository(
            {self.credential.credential_id: self.credential}
        )
        self.nodes = DictionaryRepository({self.node.node_id: self.node})
        self.sessions = InMemorySessions()
        self.replay = StrictSequenceReplay()
        self.authenticator = StubAuthenticator(
            VerifiedCredential(CREDENTIAL_ID, NODE_ID)
        )
        self.gateway = self.make_gateway()

    def make_gateway(self):
        return NodeGatewaySecurity(
            authenticator=self.authenticator,
            credentials=self.credentials,
            nodes=self.nodes,
            sessions=self.sessions,
            replay=self.replay,
            clock=self.clock,
            session_lifetime=timedelta(minutes=15),
        )

    def authenticate(self):
        return self.gateway.authenticate_node(self.presentation, NODE_ID)

    def open_session(self):
        authentication = self.authenticate()
        self.assertTrue(authentication.authenticated)
        result = self.gateway.open_session(self.presentation, NODE_ID)
        self.assertTrue(result.opened)
        self.assertIsNotNone(result.session)
        return result.session

    def request(self, session, sequence=1, capability="speaker.play"):
        return CapabilityRequest(
            request_id=f"request-{sequence}",
            session_id=session.session_id,
            sequence=sequence,
            capability=capability,
        )

    def assert_denied(self, result, reason):
        self.assertIsInstance(
            result, (AuthenticationResult, GatewayAdmissionResult)
        )
        allowed = (
            result.authenticated
            if isinstance(result, AuthenticationResult)
            else result.admitted
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, result.reason)

    def test_unknown_credential_is_denied(self):
        self.authenticator.verified = VerifiedCredential(
            "unknown-credential", NODE_ID
        )
        result = self.authenticate()
        self.assert_denied(result, SecurityReason.UNKNOWN_CREDENTIAL)

    def test_revoked_credential_is_denied_even_for_trusted_node(self):
        self.credentials.values[CREDENTIAL_ID] = replace(
            self.credential,
            status=CredentialStatus.REVOKED,
            revoked_at=NOW - timedelta(minutes=1),
        )
        result = self.authenticate()
        self.assert_denied(result, SecurityReason.CREDENTIAL_REVOKED)

    def test_expired_credential_is_denied(self):
        self.credentials.values[CREDENTIAL_ID] = replace(
            self.credential,
            status=CredentialStatus.EXPIRED,
            expires_at=NOW - timedelta(seconds=1),
        )
        result = self.authenticate()
        self.assert_denied(result, SecurityReason.CREDENTIAL_EXPIRED)

    def test_valid_credential_for_unknown_node_is_denied(self):
        self.nodes.values.clear()
        result = self.authenticate()
        self.assert_denied(result, SecurityReason.UNKNOWN_NODE)

    def test_active_credential_does_not_override_revoked_node_state(self):
        self.nodes.values[NODE_ID] = replace(
            self.node, trust_state=NodeTrustState.REVOKED
        )
        result = self.authenticate()
        self.assert_denied(result, SecurityReason.NODE_REVOKED)

    def test_untrusted_node_can_authenticate_but_not_use_protected_capability(self):
        self.nodes.values[NODE_ID] = replace(
            self.node, trust_state=NodeTrustState.UNTRUSTED
        )
        authentication = self.authenticate()
        self.assertTrue(authentication.authenticated)
        session_result = self.gateway.open_session(self.presentation, NODE_ID)
        self.assertTrue(session_result.opened)
        result = self.gateway.admit_request(
            self.presentation, self.request(session_result.session)
        )
        self.assert_denied(result, SecurityReason.NODE_NOT_TRUSTED)

    def test_trusted_node_with_unadvertised_capability_is_denied(self):
        session = self.open_session()
        result = self.gateway.admit_request(
            self.presentation,
            self.request(session, capability="microphone.session"),
        )
        self.assert_denied(result, SecurityReason.CAPABILITY_NOT_ADVERTISED)

    def test_advertised_but_ungranted_capability_is_denied(self):
        session = self.open_session()
        result = self.gateway.admit_request(
            self.presentation,
            self.request(session, capability="camera.snapshot"),
        )
        self.assert_denied(result, SecurityReason.CAPABILITY_NOT_GRANTED)

    def test_duplicate_or_older_sequence_is_denied(self):
        session = self.open_session()
        first = self.gateway.admit_request(
            self.presentation, self.request(session, sequence=3)
        )
        self.assertTrue(first.admitted)
        duplicate = self.gateway.admit_request(
            self.presentation, self.request(session, sequence=3)
        )
        older = self.gateway.admit_request(
            self.presentation, self.request(session, sequence=2)
        )
        self.assert_denied(duplicate, SecurityReason.REPLAY_DETECTED)
        self.assert_denied(older, SecurityReason.REPLAY_DETECTED)

    def test_replay_sequence_is_isolated_between_sessions(self):
        first_session = self.open_session()
        second_session = self.open_session()
        self.assertNotEqual(first_session.session_id, second_session.session_id)

        first = self.gateway.admit_request(
            self.presentation, self.request(first_session, sequence=8)
        )
        second = self.gateway.admit_request(
            self.presentation, self.request(second_session, sequence=1)
        )

        self.assertTrue(first.admitted)
        self.assertTrue(second.admitted)

    def test_replay_sequence_is_isolated_between_nodes(self):
        first_session = self.open_session()
        second_node_id = "kitchen-main"
        second_credential_id = "credential-b"
        self.credentials.values[second_credential_id] = replace(
            self.credential,
            credential_id=second_credential_id,
            node_id=second_node_id,
        )
        self.nodes.values[second_node_id] = replace(
            self.node,
            node_id=second_node_id,
        )
        self.authenticator.verified = VerifiedCredential(
            second_credential_id, second_node_id
        )
        second_result = self.gateway.open_session(
            self.presentation, second_node_id
        )
        self.assertTrue(second_result.opened)
        self.assertIsNotNone(second_result.session)
        second_session = second_result.session

        self.authenticator.verified = VerifiedCredential(CREDENTIAL_ID, NODE_ID)
        first = self.gateway.admit_request(
            self.presentation, self.request(first_session, sequence=8)
        )
        self.authenticator.verified = VerifiedCredential(
            second_credential_id, second_node_id
        )
        second = self.gateway.admit_request(
            self.presentation, self.request(second_session, sequence=1)
        )

        self.assertTrue(first.admitted)
        self.assertTrue(second.admitted)

    def test_new_session_does_not_reuse_closed_session_sequence_state(self):
        first_session = self.open_session()
        first = self.gateway.admit_request(
            self.presentation, self.request(first_session, sequence=8)
        )
        self.assertTrue(first.admitted)
        self.assertTrue(
            self.gateway.close_session(self.presentation, first_session.session_id)
        )

        second_session = self.open_session()
        self.assertNotEqual(first_session.session_id, second_session.session_id)
        second = self.gateway.admit_request(
            self.presentation, self.request(second_session, sequence=1)
        )
        old = self.gateway.admit_request(
            self.presentation, self.request(first_session, sequence=9)
        )

        self.assertTrue(second.admitted)
        self.assert_denied(old, SecurityReason.SESSION_CLOSED)

    def test_malformed_claimed_identity_is_denied_before_authentication(self):
        result = self.gateway.authenticate_node(self.presentation, "../livingroom")
        self.assert_denied(result, SecurityReason.MALFORMED_IDENTITY)

    def test_ambiguous_credential_state_is_denied(self):
        self.credentials.values[CREDENTIAL_ID] = replace(
            self.credential,
            status="active",
            revoked_at=NOW - timedelta(minutes=1),
        )
        result = self.authenticate()
        self.assert_denied(result, SecurityReason.AMBIGUOUS_CREDENTIAL_STATE)

    def test_contradictory_credential_lifecycle_metadata_is_denied(self):
        self.credentials.values[CREDENTIAL_ID] = replace(
            self.credential,
            status=CredentialStatus.EXPIRED,
            expires_at=NOW - timedelta(seconds=1),
            replacement_credential_id="credential-b",
        )
        result = self.authenticate()
        self.assert_denied(result, SecurityReason.AMBIGUOUS_CREDENTIAL_STATE)

    def test_malformed_credential_record_is_denied_instead_of_raising(self):
        self.credentials.values[CREDENTIAL_ID] = {"status": "active"}
        result = self.authenticate()
        self.assert_denied(result, SecurityReason.AMBIGUOUS_CREDENTIAL_STATE)

    def test_ambiguous_node_state_is_denied(self):
        self.nodes.values[NODE_ID] = replace(self.node, trust_state="trusted")
        result = self.authenticate()
        self.assert_denied(result, SecurityReason.AMBIGUOUS_NODE_STATE)

    def test_malformed_node_record_is_denied_instead_of_raising(self):
        self.nodes.values[NODE_ID] = {"security_state": "trusted"}
        result = self.authenticate()
        self.assert_denied(result, SecurityReason.AMBIGUOUS_NODE_STATE)

    def test_revocation_is_rechecked_after_session_open(self):
        session = self.open_session()
        self.credentials.values[CREDENTIAL_ID] = replace(
            self.credential,
            status=CredentialStatus.REVOKED,
            revoked_at=NOW,
        )
        result = self.gateway.admit_request(self.presentation, self.request(session))
        self.assert_denied(result, SecurityReason.CREDENTIAL_REVOKED)

    def test_replaced_credential_is_denied_and_replacement_keeps_node_identity(self):
        replacement = replace(
            self.credential,
            credential_id="credential-b",
            issued_at=NOW,
        )
        self.credentials.values[CREDENTIAL_ID] = replace(
            self.credential,
            status=CredentialStatus.REPLACED,
            replacement_credential_id=replacement.credential_id,
        )
        self.credentials.values[replacement.credential_id] = replacement
        old_result = self.authenticate()
        self.assert_denied(old_result, SecurityReason.CREDENTIAL_REPLACED)
        self.authenticator.verified = VerifiedCredential(
            replacement.credential_id, NODE_ID
        )
        new_result = self.authenticate()
        self.assertTrue(new_result.authenticated)
        self.assertEqual(NODE_ID, new_result.principal.node_id)

    def test_replaced_credential_invalidates_its_existing_session(self):
        session = self.open_session()
        replacement = replace(
            self.credential,
            credential_id="credential-b",
            issued_at=NOW,
        )
        self.credentials.values[CREDENTIAL_ID] = replace(
            self.credential,
            status=CredentialStatus.REPLACED,
            replacement_credential_id=replacement.credential_id,
        )
        self.credentials.values[replacement.credential_id] = replacement

        old_credential = self.gateway.admit_request(
            self.presentation, self.request(session)
        )
        self.assert_denied(old_credential, SecurityReason.CREDENTIAL_REPLACED)

        self.authenticator.verified = VerifiedCredential(
            replacement.credential_id, NODE_ID
        )
        replacement_on_old_session = self.gateway.admit_request(
            self.presentation, self.request(session)
        )
        self.assert_denied(
            replacement_on_old_session, SecurityReason.IDENTITY_MISMATCH
        )

    def test_authentication_success_does_not_imply_gateway_admission(self):
        authentication = self.authenticate()
        self.assertTrue(authentication.authenticated)
        self.assertFalse(hasattr(authentication, "admitted"))

        session = self.open_session()
        result = self.gateway.admit_request(
            self.presentation,
            self.request(session, capability="camera.snapshot"),
        )

        self.assert_denied(result, SecurityReason.CAPABILITY_NOT_GRANTED)

    def test_sensitive_advertisement_cannot_disable_node_local_gate(self):
        self.nodes.values[NODE_ID] = replace(
            self.node,
            advertised_capabilities=(
                CapabilityAdvertisement("camera.snapshot", False),
            ),
            granted_capabilities=frozenset({"camera.snapshot"}),
        )
        result = self.authenticate()
        self.assert_denied(result, SecurityReason.AMBIGUOUS_NODE_STATE)

    def test_camera_gateway_admission_still_requires_node_local_gate(self):
        self.nodes.values[NODE_ID] = replace(
            self.node,
            granted_capabilities=frozenset({"camera.snapshot"}),
        )
        session = self.open_session()
        result = self.gateway.admit_request(
            self.presentation,
            self.request(session, capability="camera.snapshot"),
        )
        self.assertTrue(result.admitted)
        self.assertTrue(result.node_local_gate_required)
        self.assertEqual(SecurityReason.GATEWAY_ADMITTED, result.reason)

    def test_replay_state_unavailable_fails_closed(self):
        session = self.open_session()
        self.replay.unavailable = True
        result = self.gateway.admit_request(self.presentation, self.request(session))
        self.assert_denied(result, SecurityReason.REPLAY_STATE_UNAVAILABLE)

    def test_request_credential_must_match_authenticated_session_binding(self):
        session = self.open_session()
        second = replace(
            self.credential,
            credential_id="credential-b",
            issued_at=NOW,
        )
        self.credentials.values[second.credential_id] = second
        self.authenticator.verified = VerifiedCredential(
            second.credential_id, NODE_ID
        )

        result = self.gateway.admit_request(self.presentation, self.request(session))

        self.assert_denied(result, SecurityReason.IDENTITY_MISMATCH)

    def test_expired_technical_session_is_denied(self):
        session = self.open_session()
        self.clock.value = session.expires_at
        result = self.gateway.admit_request(self.presentation, self.request(session))
        self.assert_denied(result, SecurityReason.SESSION_EXPIRED)

    def test_ambiguous_session_binding_is_denied(self):
        session = self.open_session()
        self.sessions.values[session.session_id] = replace(
            session, session_id="different-session"
        )
        result = self.gateway.admit_request(self.presentation, self.request(session))
        self.assert_denied(result, SecurityReason.SESSION_STATE_UNAVAILABLE)

    def test_malformed_sequence_is_denied(self):
        session = self.open_session()
        result = self.gateway.admit_request(
            self.presentation, self.request(session, sequence=0)
        )
        self.assert_denied(result, SecurityReason.MALFORMED_REQUEST)

    def test_closed_session_is_denied_without_becoming_conversation_state(self):
        session = self.open_session()
        self.assertTrue(
            self.gateway.close_session(self.presentation, session.session_id)
        )
        result = self.gateway.admit_request(self.presentation, self.request(session))
        self.assert_denied(result, SecurityReason.SESSION_CLOSED)
        self.assertIsInstance(self.sessions.get(session.session_id), NodeSession)


if __name__ == "__main__":
    unittest.main()
