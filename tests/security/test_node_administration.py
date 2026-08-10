import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from apps.assistant.src.modules.node_administration import (
    AdministrationAction,
    AdministrationReason,
    AdministrationRequest,
    AdministrationResult,
    NodeAdministration,
    NodeAdministrationRecord,
    StoreApplyOutcome,
    StoreApplyResult,
    StoredAdministrationOperation,
    VerifiedAdministrator,
)
from apps.assistant.src.modules.node_security import AuthenticatedNode, NodeTrustState


NOW = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
NODE_ID = "livingroom-main"
ADMIN_ID = "household-admin"


class FixedClock:
    def __init__(self):
        self.value = NOW

    def now(self):
        return self.value


class StubAdministratorAuthorizer:
    def __init__(self, allowed_context):
        self.allowed_context = allowed_context
        self.error = None
        self.evidence = None

    def authorize(self, context, action, node_id):
        if self.error is not None:
            raise self.error
        if context is not self.allowed_context:
            return None
        if self.evidence is not None:
            return self.evidence
        return VerifiedAdministrator(ADMIN_ID, action, node_id)


class StubCapabilityReader:
    def __init__(self):
        self.advertised = {NODE_ID: {"speaker.play", "camera.snapshot"}}
        self.error = None
        self.override = None

    def is_advertised(self, node_id, capability):
        if self.error is not None:
            raise self.error
        if self.override is not None:
            return self.override
        return capability in self.advertised.get(node_id, set())


class InMemoryAtomicAdministrationStore:
    def __init__(self):
        self.nodes = {}
        self.operations = {}
        self.audit_events = []
        self.unavailable = False
        self.fail_atomic_write = False

    def get_node(self, node_id):
        if self.unavailable:
            raise RuntimeError("state unavailable")
        return self.nodes.get(node_id)

    def get_operation(self, operation_id):
        if self.unavailable:
            raise RuntimeError("state unavailable")
        return self.operations.get(operation_id)

    def apply(self, mutation):
        if self.unavailable:
            raise RuntimeError("state unavailable")

        prior = self.operations.get(mutation.request.operation_id)
        if prior is not None:
            if prior.request == mutation.request:
                return StoreApplyResult(StoreApplyOutcome.IDEMPOTENT, prior.record)
            return StoreApplyResult(StoreApplyOutcome.IDEMPOTENCY_CONFLICT)

        current = self.nodes.get(mutation.request.node_id)
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
        if self.fail_atomic_write:
            raise RuntimeError("atomic state/audit write failed")

        stored = StoredAdministrationOperation(
            mutation.request,
            mutation.record,
            mutation.audit_event,
        )
        self.nodes[mutation.request.node_id] = mutation.record
        self.audit_events.append(mutation.audit_event)
        self.operations[mutation.request.operation_id] = stored
        return StoreApplyResult(StoreApplyOutcome.APPLIED, mutation.record)


class NodeAdministrationTests(unittest.TestCase):
    def setUp(self):
        self.admin_context = object()
        self.clock = FixedClock()
        self.authorizer = StubAdministratorAuthorizer(self.admin_context)
        self.capabilities = StubCapabilityReader()
        self.store = InMemoryAtomicAdministrationStore()
        self.administration = NodeAdministration(
            authorizer=self.authorizer,
            store=self.store,
            capabilities=self.capabilities,
            clock=self.clock,
        )

    def request(
        self,
        action,
        *,
        operation_id=None,
        node_id=NODE_ID,
        expected_revision=0,
        trust_state=None,
        capability=None,
    ):
        return AdministrationRequest(
            operation_id=operation_id or str(uuid4()),
            correlation_id="admin-request",
            action=action,
            node_id=node_id,
            expected_revision=expected_revision,
            trust_state=trust_state,
            capability=capability,
        )

    def administer(self, request, context=None):
        return self.administration.administer(
            self.admin_context if context is None else context,
            request,
        )

    def enroll(self):
        result = self.administer(self.request(AdministrationAction.ENROLL_NODE))
        self.assert_applied(result, revision=1)
        return result.record

    def assert_applied(self, result, revision):
        self.assertIsInstance(result, AdministrationResult)
        self.assertTrue(result.succeeded)
        self.assertTrue(result.changed)
        self.assertFalse(result.idempotent)
        self.assertEqual(AdministrationReason.APPLIED, result.reason)
        self.assertEqual(revision, result.record.revision)

    def assert_denied(self, result, reason):
        self.assertFalse(result.succeeded)
        self.assertFalse(result.changed)
        self.assertFalse(result.idempotent)
        self.assertEqual(reason, result.reason)

    def test_authenticated_node_is_not_administrative_authority_or_enrolled(self):
        authenticated_node = AuthenticatedNode(NODE_ID, "credential-a")
        result = self.administer(
            self.request(AdministrationAction.ENROLL_NODE),
            context=authenticated_node,
        )
        self.assert_denied(result, AdministrationReason.ADMINISTRATION_DENIED)
        self.assertNotIn(NODE_ID, self.store.nodes)
        self.assertEqual([], self.store.audit_events)

    def test_explicit_enrollment_starts_untrusted_without_grants(self):
        record = self.enroll()
        self.assertEqual(NodeTrustState.UNTRUSTED, record.trust_state)
        self.assertEqual(frozenset(), record.granted_capabilities)
        self.assertEqual(1, len(self.store.audit_events))
        self.assertEqual("node.enroll", self.store.audit_events[0].action)

    def test_enrollment_does_not_implicitly_trust_even_when_capabilities_advertised(self):
        record = self.enroll()
        self.assertEqual(NodeTrustState.UNTRUSTED, record.trust_state)
        self.assertNotEqual(
            self.capabilities.advertised[NODE_ID],
            set(record.granted_capabilities),
        )

    def test_action_specific_authorization_mismatch_fails_closed(self):
        self.authorizer.evidence = VerifiedAdministrator(
            ADMIN_ID, AdministrationAction.REVOKE_NODE, NODE_ID
        )
        result = self.administer(self.request(AdministrationAction.ENROLL_NODE))
        self.assert_denied(result, AdministrationReason.AMBIGUOUS_AUTHORIZATION)

    def test_authorizer_failure_fails_closed(self):
        self.authorizer.error = RuntimeError("authorizer unavailable")
        result = self.administer(self.request(AdministrationAction.ENROLL_NODE))
        self.assert_denied(result, AdministrationReason.AUTHORIZER_UNAVAILABLE)

    def test_generic_administrator_identifier_is_not_forced_into_node_id_grammar(self):
        self.authorizer.evidence = VerifiedAdministrator(
            "user:admin@example.test",
            AdministrationAction.ENROLL_NODE,
            NODE_ID,
        )
        result = self.administer(self.request(AdministrationAction.ENROLL_NODE))
        self.assert_applied(result, revision=1)
        self.assertEqual(
            "user:admin@example.test", self.store.audit_events[0].actor_id
        )

    def test_trust_change_requires_explicit_revisioned_operation(self):
        self.enroll()
        result = self.administer(
            self.request(
                AdministrationAction.SET_TRUST,
                expected_revision=1,
                trust_state=NodeTrustState.TRUSTED,
            )
        )
        self.assert_applied(result, revision=2)
        self.assertEqual(NodeTrustState.TRUSTED, result.record.trust_state)
        self.assertEqual(frozenset(), result.record.granted_capabilities)

    def test_stale_revision_is_rejected_without_state_or_audit_change(self):
        self.enroll()
        before_audit = len(self.store.audit_events)
        result = self.administer(
            self.request(
                AdministrationAction.SET_TRUST,
                expected_revision=7,
                trust_state=NodeTrustState.TRUSTED,
            )
        )
        self.assert_denied(result, AdministrationReason.REVISION_CONFLICT)
        self.assertEqual(1, self.store.nodes[NODE_ID].revision)
        self.assertEqual(before_audit, len(self.store.audit_events))

    def test_advertised_capability_can_be_granted_but_is_not_policy_approval(self):
        self.enroll()
        result = self.administer(
            self.request(
                AdministrationAction.GRANT_CAPABILITY,
                expected_revision=1,
                capability="speaker.play",
            )
        )
        self.assert_applied(result, revision=2)
        self.assertIn("speaker.play", result.record.granted_capabilities)
        self.assertFalse(hasattr(result, "policy_decision"))
        self.assertFalse(hasattr(result, "execution_allowed"))

    def test_unadvertised_capability_cannot_be_granted(self):
        self.enroll()
        result = self.administer(
            self.request(
                AdministrationAction.GRANT_CAPABILITY,
                expected_revision=1,
                capability="mobility.goto",
            )
        )
        self.assert_denied(result, AdministrationReason.CAPABILITY_NOT_ADVERTISED)
        self.assertEqual(frozenset(), self.store.nodes[NODE_ID].granted_capabilities)

    def test_capability_reader_failure_fails_closed(self):
        self.enroll()
        self.capabilities.error = RuntimeError("capability state unavailable")
        result = self.administer(
            self.request(
                AdministrationAction.GRANT_CAPABILITY,
                expected_revision=1,
                capability="speaker.play",
            )
        )
        self.assert_denied(
            result, AdministrationReason.CAPABILITY_STATE_UNAVAILABLE
        )

    def test_capability_grant_can_be_revoked(self):
        self.enroll()
        granted = self.administer(
            self.request(
                AdministrationAction.GRANT_CAPABILITY,
                expected_revision=1,
                capability="speaker.play",
            )
        )
        revoked = self.administer(
            self.request(
                AdministrationAction.REVOKE_CAPABILITY,
                expected_revision=granted.record.revision,
                capability="speaker.play",
            )
        )
        self.assert_applied(revoked, revision=3)
        self.assertNotIn("speaker.play", revoked.record.granted_capabilities)

    def test_node_revocation_is_terminal_for_trust_and_grant_changes(self):
        self.enroll()
        revoked = self.administer(
            self.request(
                AdministrationAction.REVOKE_NODE,
                expected_revision=1,
            )
        )
        self.assert_applied(revoked, revision=2)
        self.assertEqual(NodeTrustState.REVOKED, revoked.record.trust_state)

        trust = self.administer(
            self.request(
                AdministrationAction.SET_TRUST,
                expected_revision=2,
                trust_state=NodeTrustState.TRUSTED,
            )
        )
        grant = self.administer(
            self.request(
                AdministrationAction.GRANT_CAPABILITY,
                expected_revision=2,
                capability="speaker.play",
            )
        )
        self.assert_denied(trust, AdministrationReason.NODE_REVOKED)
        self.assert_denied(grant, AdministrationReason.NODE_REVOKED)

    def test_same_operation_retry_is_idempotent_without_duplicate_audit(self):
        operation_id = str(uuid4())
        request = self.request(
            AdministrationAction.ENROLL_NODE,
            operation_id=operation_id,
        )
        first = self.administer(request)
        second = self.administer(request)
        self.assert_applied(first, revision=1)
        self.assertTrue(second.succeeded)
        self.assertFalse(second.changed)
        self.assertTrue(second.idempotent)
        self.assertEqual(AdministrationReason.IDEMPOTENT_REPLAY, second.reason)
        self.assertEqual(1, len(self.store.audit_events))

    def test_reused_operation_id_with_different_payload_is_rejected(self):
        operation_id = str(uuid4())
        first = self.request(
            AdministrationAction.ENROLL_NODE,
            operation_id=operation_id,
        )
        self.administer(first)
        conflicting = replace(first, node_id="kitchen-main")
        result = self.administer(conflicting)
        self.assert_denied(result, AdministrationReason.IDEMPOTENCY_CONFLICT)
        self.assertNotIn("kitchen-main", self.store.nodes)

    def test_idempotent_record_from_future_trusted_time_fails_closed(self):
        request = self.request(AdministrationAction.ENROLL_NODE)
        self.administer(request)
        self.clock.value = NOW - timedelta(seconds=1)
        result = self.administer(request)
        self.assert_denied(result, AdministrationReason.AMBIGUOUS_STATE)

    def test_desired_state_no_change_does_not_increment_revision_or_audit(self):
        self.enroll()
        request = self.request(
            AdministrationAction.SET_TRUST,
            expected_revision=1,
            trust_state=NodeTrustState.UNTRUSTED,
        )
        result = self.administer(request)
        self.assertTrue(result.succeeded)
        self.assertFalse(result.changed)
        self.assertTrue(result.idempotent)
        self.assertEqual(AdministrationReason.NO_CHANGE, result.reason)
        self.assertEqual(1, result.record.revision)
        self.assertEqual(1, len(self.store.audit_events))

    def test_atomic_audit_failure_does_not_change_state(self):
        self.store.fail_atomic_write = True
        result = self.administer(self.request(AdministrationAction.ENROLL_NODE))
        self.assert_denied(result, AdministrationReason.STATE_UNAVAILABLE)
        self.assertEqual({}, self.store.nodes)
        self.assertEqual({}, self.store.operations)
        self.assertEqual([], self.store.audit_events)

    def test_unknown_node_cannot_receive_trust_or_grants(self):
        trust = self.administer(
            self.request(
                AdministrationAction.SET_TRUST,
                expected_revision=1,
                trust_state=NodeTrustState.TRUSTED,
            )
        )
        grant = self.administer(
            self.request(
                AdministrationAction.GRANT_CAPABILITY,
                expected_revision=1,
                capability="speaker.play",
            )
        )
        self.assert_denied(trust, AdministrationReason.NODE_NOT_ENROLLED)
        self.assert_denied(grant, AdministrationReason.NODE_NOT_ENROLLED)

    def test_malformed_request_fails_before_authorization(self):
        malformed = self.request(
            AdministrationAction.SET_TRUST,
            expected_revision=0,
            trust_state=NodeTrustState.TRUSTED,
        )
        result = self.administer(malformed)
        self.assert_denied(result, AdministrationReason.MALFORMED_REQUEST)

    def test_ambiguous_stored_record_fails_closed(self):
        self.store.nodes[NODE_ID] = {"trust_state": "trusted"}
        result = self.administer(
            self.request(
                AdministrationAction.SET_TRUST,
                expected_revision=1,
                trust_state=NodeTrustState.TRUSTED,
            )
        )
        self.assert_denied(result, AdministrationReason.AMBIGUOUS_STATE)

    def test_successful_change_has_privileged_metadata_only_audit(self):
        self.enroll()
        event = self.store.audit_events[0]
        self.assertEqual("administration", event.category)
        self.assertEqual("user", event.actor_type)
        self.assertEqual(ADMIN_ID, event.actor_id)
        self.assertEqual(NODE_ID, event.node_id)
        self.assertEqual("allow", event.decision)
        self.assertEqual("success", event.result)
        self.assertFalse(hasattr(event, "credential"))
        self.assertFalse(hasattr(event, "secret"))


if __name__ == "__main__":
    unittest.main()
