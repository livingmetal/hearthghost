"""Bounded text-only conversation sessions with no execution authority."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from uuid import uuid4

from apps.assistant.src.ports.conversation import ConversationRepository
from apps.assistant.src.ports.node_gateway import Clock


MAX_TEXT_LENGTH = 4_000
TEXT_CAPABILITY = "conversation.text"
MIN_FOLLOW_UP_TIMEOUT = timedelta(seconds=5)
MAX_FOLLOW_UP_TIMEOUT = timedelta(seconds=120)


class ConversationState(str, Enum):
    SLEEPING = "sleeping"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ENGAGED = "engaged"


class ConversationReason(str, Enum):
    OPENED = "opened"
    INPUT_ACCEPTED = "input_accepted"
    RESPONSE_ACCEPTED = "response_accepted"
    ENDED = "ended"
    TIMED_OUT = "timed_out"
    NOT_ADMITTED = "not_admitted"
    CAPABILITY_MISMATCH = "capability_mismatch"
    SESSION_UNKNOWN = "session_unknown"
    NODE_SESSION_MISMATCH = "node_session_mismatch"
    SESSION_INACTIVE = "session_inactive"
    MALFORMED_TEXT = "malformed_text"
    STATE_UNAVAILABLE = "state_unavailable"


@dataclass(frozen=True)
class AdmittedConversationNode:
    """Gateway-derived context; admission is not Policy or execution approval."""

    admitted: bool
    node_id: str
    node_session_id: str
    capability: str


@dataclass(frozen=True)
class ConversationSession:
    session_id: str
    node_id: str
    node_session_id: str
    state: ConversationState
    opened_at: datetime
    last_activity_at: datetime
    follow_up_timeout_sec: int
    ended_at: datetime | None = None


@dataclass(frozen=True)
class ConversationStateEvent:
    session_id: str | None
    state: ConversationState
    occurred_at: datetime
    reason: str


@dataclass(frozen=True)
class ConversationTurn:
    message_id: str
    session_id: str
    node_id: str
    text: str
    accepted_at: datetime


@dataclass(frozen=True)
class ConversationResult:
    accepted: bool
    reason: ConversationReason
    session: ConversationSession | None = None
    turn: ConversationTurn | None = None
    events: tuple[ConversationStateEvent, ...] = ()


class ConversationManager:
    """Owns dialogue lifecycle but never calls providers, Policy, or devices.

    The manager keeps one bounded default timeout for new sessions, while every
    opened session captures its own timeout. This prevents one principal's
    behavior preference from changing another principal's active conversation.
    """

    def __init__(
        self,
        *,
        repository: ConversationRepository,
        clock: Clock,
        follow_up_timeout: timedelta,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._follow_up_timeout = _validate_follow_up_timeout(follow_up_timeout)

    @property
    def follow_up_timeout(self) -> timedelta:
        """Default timeout used only for newly opened sessions."""
        return self._follow_up_timeout

    def set_follow_up_timeout(self, value: timedelta) -> None:
        """Change the default for future sessions; existing sessions are isolated."""
        self._follow_up_timeout = _validate_follow_up_timeout(value)

    def open(
        self,
        node: AdmittedConversationNode,
        *,
        follow_up_timeout: timedelta | None = None,
    ) -> ConversationResult:
        denied = self._validate_node(node)
        if denied is not None:
            return denied
        timeout = _validate_follow_up_timeout(
            self._follow_up_timeout if follow_up_timeout is None else follow_up_timeout
        )
        now = self._now()
        if now is None:
            return ConversationResult(False, ConversationReason.STATE_UNAVAILABLE)
        session = ConversationSession(
            session_id=str(uuid4()),
            node_id=node.node_id,
            node_session_id=node.node_session_id,
            state=ConversationState.LISTENING,
            opened_at=now,
            last_activity_at=now,
            follow_up_timeout_sec=int(timeout.total_seconds()),
        )
        if not self._put(session):
            return ConversationResult(False, ConversationReason.STATE_UNAVAILABLE)
        return ConversationResult(
            True,
            ConversationReason.OPENED,
            session,
            events=(self._event(session, now, "conversation_opened"),),
        )

    def set_session_follow_up_timeout(
        self,
        node: AdmittedConversationNode,
        session_id: str,
        value: timedelta,
    ) -> ConversationResult:
        timeout = _validate_follow_up_timeout(value)
        resolved = self._active_session(node, session_id, allow_expired=True)
        if isinstance(resolved, ConversationResult):
            return resolved
        session, now = resolved
        updated = replace(
            session,
            follow_up_timeout_sec=int(timeout.total_seconds()),
        )
        if not self._put(updated):
            return ConversationResult(False, ConversationReason.STATE_UNAVAILABLE)
        return ConversationResult(True, ConversationReason.INPUT_ACCEPTED, updated)

    def accept_text(
        self,
        node: AdmittedConversationNode,
        session_id: str,
        text: str,
    ) -> ConversationResult:
        resolved = self._active_session(node, session_id)
        if isinstance(resolved, ConversationResult):
            return resolved
        session, now = resolved
        normalized = _normalize_text(text)
        if normalized is None:
            return ConversationResult(False, ConversationReason.MALFORMED_TEXT)
        listening = replace(
            session,
            state=ConversationState.LISTENING,
            last_activity_at=now,
        )
        thinking = replace(
            session,
            state=ConversationState.THINKING,
            last_activity_at=now,
        )
        if not self._put(thinking):
            return ConversationResult(False, ConversationReason.STATE_UNAVAILABLE)
        turn = ConversationTurn(
            message_id=str(uuid4()),
            session_id=session.session_id,
            node_id=session.node_id,
            text=normalized,
            accepted_at=now,
        )
        return ConversationResult(
            True,
            ConversationReason.INPUT_ACCEPTED,
            thinking,
            turn,
            (
                self._event(listening, now, "text_input_received"),
                self._event(thinking, now, "text_input_accepted"),
            ),
        )

    def complete_response(
        self,
        node: AdmittedConversationNode,
        session_id: str,
        response_text: str,
    ) -> ConversationResult:
        resolved = self._active_session(node, session_id)
        if isinstance(resolved, ConversationResult):
            return resolved
        session, now = resolved
        if session.state is not ConversationState.THINKING:
            return ConversationResult(False, ConversationReason.SESSION_INACTIVE)
        if _normalize_text(response_text) is None:
            return ConversationResult(False, ConversationReason.MALFORMED_TEXT)
        speaking = replace(session, state=ConversationState.SPEAKING)
        engaged = replace(
            speaking,
            state=ConversationState.ENGAGED,
            last_activity_at=now,
        )
        if not self._put(engaged):
            return ConversationResult(False, ConversationReason.STATE_UNAVAILABLE)
        return ConversationResult(
            True,
            ConversationReason.RESPONSE_ACCEPTED,
            engaged,
            events=(
                self._event(speaking, now, "response_started"),
                self._event(engaged, now, "response_completed"),
            ),
        )

    def end(
        self,
        node: AdmittedConversationNode,
        session_id: str,
    ) -> ConversationResult:
        resolved = self._active_session(node, session_id, allow_expired=True)
        if isinstance(resolved, ConversationResult):
            return resolved
        session, now = resolved
        return self._end(session, now, ConversationReason.ENDED)

    def expire(self, session_id: str) -> ConversationResult:
        now = self._now()
        if now is None:
            return ConversationResult(False, ConversationReason.STATE_UNAVAILABLE)
        try:
            session = self._repository.get(session_id)
        except Exception:
            return ConversationResult(False, ConversationReason.STATE_UNAVAILABLE)
        if session is None:
            return ConversationResult(False, ConversationReason.SESSION_UNKNOWN)
        if session.ended_at is not None:
            return ConversationResult(False, ConversationReason.SESSION_INACTIVE)
        if now < session.last_activity_at + _session_timeout(session):
            return ConversationResult(False, ConversationReason.SESSION_INACTIVE, session)
        return self._end(session, now, ConversationReason.TIMED_OUT)

    def _active_session(
        self,
        node: AdmittedConversationNode,
        session_id: str,
        *,
        allow_expired: bool = False,
    ) -> tuple[ConversationSession, datetime] | ConversationResult:
        denied = self._validate_node(node)
        if denied is not None:
            return denied
        now = self._now()
        if now is None:
            return ConversationResult(False, ConversationReason.STATE_UNAVAILABLE)
        try:
            session = self._repository.get(session_id)
        except Exception:
            return ConversationResult(False, ConversationReason.STATE_UNAVAILABLE)
        if session is None:
            return ConversationResult(False, ConversationReason.SESSION_UNKNOWN)
        if (
            session.node_id != node.node_id
            or session.node_session_id != node.node_session_id
        ):
            return ConversationResult(False, ConversationReason.NODE_SESSION_MISMATCH)
        if session.ended_at is not None:
            return ConversationResult(False, ConversationReason.SESSION_INACTIVE)
        if not allow_expired and now >= session.last_activity_at + _session_timeout(session):
            self._end(session, now, ConversationReason.TIMED_OUT)
            return ConversationResult(False, ConversationReason.SESSION_INACTIVE)
        return session, now

    @staticmethod
    def _validate_node(
        node: AdmittedConversationNode,
    ) -> ConversationResult | None:
        if not node.admitted or not node.node_id or not node.node_session_id:
            return ConversationResult(False, ConversationReason.NOT_ADMITTED)
        if node.capability != TEXT_CAPABILITY:
            return ConversationResult(False, ConversationReason.CAPABILITY_MISMATCH)
        return None

    def _end(
        self,
        session: ConversationSession,
        now: datetime,
        reason: ConversationReason,
    ) -> ConversationResult:
        sleeping = replace(
            session,
            state=ConversationState.SLEEPING,
            last_activity_at=now,
            ended_at=now,
        )
        if not self._put(sleeping):
            return ConversationResult(False, ConversationReason.STATE_UNAVAILABLE)
        return ConversationResult(
            True,
            reason,
            sleeping,
            events=(self._event(sleeping, now, reason.value),),
        )

    def _now(self) -> datetime | None:
        try:
            now = self._clock.now()
        except Exception:
            return None
        if now.tzinfo is None or now.utcoffset() is None:
            return None
        return now

    def _put(self, session: ConversationSession) -> bool:
        try:
            self._repository.put(session)
        except Exception:
            return False
        return True

    @staticmethod
    def _event(
        session: ConversationSession,
        now: datetime,
        reason: str,
    ) -> ConversationStateEvent:
        return ConversationStateEvent(session.session_id, session.state, now, reason)


def _session_timeout(session: ConversationSession) -> timedelta:
    try:
        return _validate_follow_up_timeout(timedelta(seconds=session.follow_up_timeout_sec))
    except (AttributeError, TypeError, ValueError, OverflowError) as error:
        raise RuntimeError("conversation session has invalid follow-up timeout") from error


def _validate_follow_up_timeout(value: timedelta) -> timedelta:
    if not isinstance(value, timedelta):
        raise ValueError("follow_up_timeout must be a timedelta")
    if value < MIN_FOLLOW_UP_TIMEOUT or value > MAX_FOLLOW_UP_TIMEOUT:
        raise ValueError("follow_up_timeout must be between 5 and 120 seconds")
    if value.total_seconds() != int(value.total_seconds()):
        raise ValueError("follow_up_timeout must use whole seconds")
    return value


def _normalize_text(text: object) -> str | None:
    if not isinstance(text, str):
        return None
    normalized = text.strip()
    if not normalized or len(normalized) > MAX_TEXT_LENGTH or "\x00" in normalized:
        return None
    if any(ord(character) < 32 and character not in "\n\t" for character in normalized):
        return None
    return normalized
