from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from apps.assistant.src.adapters.in_memory_conversation import InMemoryConversationRepository
from apps.assistant.src.modules.conversation import (
    AdmittedConversationNode,
    ConversationManager,
    ConversationReason,
    ConversationState,
)


class MutableClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 8, 11, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.current


class FailingRepository:
    def get(self, session_id):
        raise RuntimeError("storage unavailable")

    def put(self, session):
        raise RuntimeError("storage unavailable")


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.clock = MutableClock()
        self.repository = InMemoryConversationRepository()
        self.conversation = ConversationManager(
            repository=self.repository,
            clock=self.clock,
            follow_up_timeout=timedelta(seconds=30),
        )
        self.node = AdmittedConversationNode(
            admitted=True,
            node_id="client-living-room",
            node_session_id="node-session-1",
            capability="conversation.text",
        )

    def test_node_gateway_admission_and_exact_capability_are_required(self):
        for node, reason in (
            (AdmittedConversationNode(False, "client-living-room", "node-session-1", "conversation.text"), ConversationReason.NOT_ADMITTED),
            (AdmittedConversationNode(True, "client-living-room", "node-session-1", "speaker"), ConversationReason.CAPABILITY_MISMATCH),
        ):
            with self.subTest(reason=reason):
                result = self.conversation.open(node)
                self.assertFalse(result.accepted)
                self.assertEqual(result.reason, reason)

    def test_conversation_and_node_session_identifiers_are_distinct(self):
        opened = self.conversation.open(self.node)
        self.assertTrue(opened.accepted)
        self.assertNotEqual(opened.session.session_id, self.node.node_session_id)
        self.assertEqual(opened.session.state, ConversationState.LISTENING)
        self.assertEqual(opened.session.follow_up_timeout_sec, 30)

    def test_text_turn_transitions_thinking_speaking_and_engaged(self):
        opened = self.conversation.open(self.node)
        accepted = self.conversation.accept_text(self.node, opened.session.session_id, "  How was my schedule today?  ")
        completed = self.conversation.complete_response(self.node, opened.session.session_id, "You had three appointments.")
        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.turn.text, "How was my schedule today?")
        self.assertEqual(accepted.session.state, ConversationState.THINKING)
        self.assertEqual([event.state for event in accepted.events], [ConversationState.LISTENING, ConversationState.THINKING])
        self.assertEqual([event.state for event in completed.events], [ConversationState.SPEAKING, ConversationState.ENGAGED])
        self.assertEqual(completed.session.state, ConversationState.ENGAGED)

    def test_malformed_text_fails_without_changing_session_state(self):
        opened = self.conversation.open(self.node)
        for text in ("", "   ", "bad\x00text", "x" * 4_001):
            with self.subTest(text_length=len(text)):
                result = self.conversation.accept_text(self.node, opened.session.session_id, text)
                self.assertFalse(result.accepted)
                self.assertEqual(result.reason, ConversationReason.MALFORMED_TEXT)
        self.assertEqual(self.repository.get(opened.session.session_id).state, ConversationState.LISTENING)

    def test_other_technical_session_cannot_continue_conversation(self):
        opened = self.conversation.open(self.node)
        other_session = AdmittedConversationNode(True, self.node.node_id, "node-session-2", "conversation.text")
        result = self.conversation.accept_text(other_session, opened.session.session_id, "hello")
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, ConversationReason.NODE_SESSION_MISMATCH)

    def test_timeout_ends_only_conversation_state(self):
        opened = self.conversation.open(self.node)
        self.clock.current += timedelta(seconds=30)
        expired = self.conversation.expire(opened.session.session_id)
        self.assertTrue(expired.accepted)
        self.assertEqual(expired.reason, ConversationReason.TIMED_OUT)
        self.assertEqual(expired.session.state, ConversationState.SLEEPING)
        self.assertEqual(self.node.node_session_id, "node-session-1")
        self.assertTrue(self.node.admitted)

    def test_default_timeout_update_affects_future_sessions_only(self):
        existing = self.conversation.open(self.node)
        self.conversation.set_follow_up_timeout(timedelta(seconds=45))
        future = self.conversation.open(self.node)
        self.assertEqual(existing.session.follow_up_timeout_sec, 30)
        self.assertEqual(future.session.follow_up_timeout_sec, 45)

    def test_scoped_session_timeout_update_changes_only_target_session(self):
        first = self.conversation.open(self.node)
        second = self.conversation.open(self.node)
        updated = self.conversation.set_session_follow_up_timeout(
            self.node,
            first.session.session_id,
            timedelta(seconds=45),
        )
        self.assertTrue(updated.accepted)
        self.assertEqual(updated.session.follow_up_timeout_sec, 45)
        self.assertEqual(self.repository.get(second.session.session_id).follow_up_timeout_sec, 30)
        self.clock.current += timedelta(seconds=30)
        self.assertFalse(self.conversation.expire(first.session.session_id).accepted)
        self.assertTrue(self.conversation.expire(second.session.session_id).accepted)

    def test_timeout_update_is_bounded_by_behavior_contract(self):
        opened = self.conversation.open(self.node)
        for value in (timedelta(seconds=4), timedelta(seconds=121)):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.conversation.set_session_follow_up_timeout(self.node, opened.session.session_id, value)
        self.assertEqual(self.repository.get(opened.session.session_id).follow_up_timeout_sec, 30)

    def test_open_accepts_explicit_per_session_timeout(self):
        opened = self.conversation.open(self.node, follow_up_timeout=timedelta(seconds=75))
        self.assertEqual(opened.session.follow_up_timeout_sec, 75)
        self.assertEqual(self.conversation.follow_up_timeout, timedelta(seconds=30))

    def test_early_expiration_attempt_does_not_end_session(self):
        opened = self.conversation.open(self.node)
        self.clock.current += timedelta(seconds=29)
        result = self.conversation.expire(opened.session.session_id)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, ConversationReason.SESSION_INACTIVE)
        self.assertEqual(result.session.state, ConversationState.LISTENING)

    def test_repository_failure_fails_closed(self):
        manager = ConversationManager(repository=FailingRepository(), clock=self.clock, follow_up_timeout=timedelta(seconds=30))
        result = manager.open(self.node)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, ConversationReason.STATE_UNAVAILABLE)

    def test_response_cannot_complete_before_input(self):
        opened = self.conversation.open(self.node)
        result = self.conversation.complete_response(self.node, opened.session.session_id, "unexpected")
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, ConversationReason.SESSION_INACTIVE)


if __name__ == "__main__":
    unittest.main()
