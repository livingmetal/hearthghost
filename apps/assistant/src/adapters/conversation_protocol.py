"""Text conversation protocol on the existing authenticated Node channel."""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from uuid import UUID

from apps.assistant.src.adapters.node_gateway_protocol import (
    CONTRACT_VERSION,
    MAX_SEQUENCE,
    NodeProtocolError,
    read_frame,
    write_frame,
)
from apps.assistant.src.modules.conversation import (
    AdmittedConversationNode,
    ConversationManager,
    ConversationStateEvent,
    TEXT_CAPABILITY,
)
from apps.assistant.src.modules.node_security import (
    CAPABILITY_PATTERN,
    IDENTIFIER_PATTERN,
    CapabilityRequest,
)
from apps.assistant.src.modules.orchestrator import ConversationOrchestrator
from apps.assistant.src.ports.llm import ProposedAction
from apps.assistant.src.ports.node_gateway import NodeGatewaySecurityBoundary


MAX_TEXT_LENGTH = 4_000
MAX_RESPONSE_TEXT_LENGTH = 8_000
MAX_EVENTS = 8
MAX_PROPOSALS = 8


@dataclass(frozen=True)
class ConversationCommand:
    message_type: str
    request_id: str
    node_session_id: str
    sequence: int
    conversation_session_id: str | None = None
    text: str | None = None


@dataclass(frozen=True)
class ConversationWireResult:
    request_id: str
    accepted: bool
    reason_code: str
    node_session_id: str | None = None
    conversation_session_id: str | None = None
    response_text: str | None = None
    events: tuple[dict[str, object], ...] = ()
    proposed_actions: tuple[dict[str, object], ...] = ()

    def to_document(self) -> dict[str, object]:
        document: dict[str, object] = {
            "contract_version": CONTRACT_VERSION,
            "message_type": "conversation.result",
            "request_id": self.request_id,
            "outcome": "accepted" if self.accepted else "denied",
            "reason_code": self.reason_code,
        }
        for field, value in (
            ("node_session_id", self.node_session_id),
            ("conversation_session_id", self.conversation_session_id),
            ("response_text", self.response_text),
        ):
            if value is not None:
                document[field] = value
        if self.events:
            document["events"] = list(self.events)
        if self.proposed_actions:
            document["proposed_actions"] = list(self.proposed_actions)
        return document


class ConversationProtocol:
    """Admits every command through Node Gateway before conversation dispatch."""

    def __init__(
        self,
        *,
        gateway: NodeGatewaySecurityBoundary,
        conversation: ConversationManager,
        orchestrator: ConversationOrchestrator,
    ) -> None:
        self._gateway = gateway
        self._conversation = conversation
        self._orchestrator = orchestrator

    def handle_next(self, channel: ssl.SSLSocket) -> ConversationWireResult:
        if not isinstance(channel, ssl.SSLSocket):
            raise NodeProtocolError("Conversation requires an authenticated TLS channel")
        return self.handle_document(channel, read_frame(channel))

    def handle_document(
        self,
        channel: ssl.SSLSocket,
        document: object,
    ) -> ConversationWireResult:
        """Handle one already-framed command on an authenticated channel."""

        if not isinstance(channel, ssl.SSLSocket):
            raise NodeProtocolError("Conversation requires an authenticated TLS channel")
        command = parse_conversation_command(document)
        admission = self._gateway.admit_request(
            channel,
            CapabilityRequest(
                request_id=command.request_id,
                session_id=command.node_session_id,
                sequence=command.sequence,
                capability=TEXT_CAPABILITY,
            ),
        )
        if not admission.admitted or admission.node_id is None:
            result = ConversationWireResult(
                command.request_id,
                False,
                admission.reason.value,
            )
        else:
            node = AdmittedConversationNode(
                admitted=True,
                node_id=admission.node_id,
                node_session_id=command.node_session_id,
                capability=TEXT_CAPABILITY,
            )
            result = self._dispatch(node, command)
        write_frame(channel, result.to_document())
        return result

    def _dispatch(
        self,
        node: AdmittedConversationNode,
        command: ConversationCommand,
    ) -> ConversationWireResult:
        if command.message_type == "conversation.open":
            opened = self._conversation.open(node)
            return _conversation_result(command, opened)

        if command.message_type == "conversation.close":
            closed = self._conversation.end(node, command.conversation_session_id)
            return _conversation_result(command, closed)

        accepted = self._conversation.accept_text(
            node,
            command.conversation_session_id,
            command.text,
        )
        if not accepted.accepted or accepted.turn is None:
            return _conversation_result(command, accepted)
        response = self._orchestrator.respond(node, accepted.turn)
        if not response.conversation_completed:
            return ConversationWireResult(
                request_id=command.request_id,
                accepted=False,
                reason_code=response.reason.value,
            )
        events = accepted.events + response.events
        return ConversationWireResult(
            request_id=command.request_id,
            accepted=True,
            reason_code=response.reason.value,
            node_session_id=command.node_session_id,
            conversation_session_id=command.conversation_session_id,
            response_text=response.response_text,
            events=tuple(_state_event(event) for event in events),
            proposed_actions=tuple(
                _wire_proposal(proposal) for proposal in response.proposed_actions
            ),
        )


def read_conversation_command(channel) -> ConversationCommand:
    return parse_conversation_command(read_frame(channel))


def parse_conversation_command(document: object) -> ConversationCommand:
    """Validate a decoded conversation document without weakening framing."""

    if not isinstance(document, dict):
        raise NodeProtocolError("Conversation command must be an object")
    if document.get("contract_version") != CONTRACT_VERSION:
        raise NodeProtocolError("unsupported conversation contract version")
    message_type = document.get("message_type")
    request_id = document.get("request_id")
    node_session_id = document.get("node_session_id")
    sequence = document.get("sequence")
    if (
        message_type
        not in {"conversation.open", "conversation.text", "conversation.close"}
        or not _valid_uuid(request_id)
        or not _valid_identifier(node_session_id)
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not 1 <= sequence <= MAX_SEQUENCE
    ):
        raise NodeProtocolError("invalid conversation command identity")

    base = {
        "contract_version",
        "message_type",
        "request_id",
        "node_session_id",
        "sequence",
    }
    if message_type == "conversation.open":
        _require_exact_fields(document, base)
        return ConversationCommand(message_type, request_id, node_session_id, sequence)

    conversation_session_id = document.get("conversation_session_id")
    if not _valid_identifier(conversation_session_id):
        raise NodeProtocolError("conversation command requires a session identifier")
    if message_type == "conversation.close":
        _require_exact_fields(document, base | {"conversation_session_id"})
        return ConversationCommand(
            message_type,
            request_id,
            node_session_id,
            sequence,
            conversation_session_id,
        )

    _require_exact_fields(document, base | {"conversation_session_id", "text"})
    text = document.get("text")
    if not isinstance(text, str) or not 1 <= len(text) <= MAX_TEXT_LENGTH:
        raise NodeProtocolError("conversation.text requires bounded text")
    return ConversationCommand(
        message_type,
        request_id,
        node_session_id,
        sequence,
        conversation_session_id,
        text,
    )


def read_conversation_result(channel) -> ConversationWireResult:
    document = read_frame(channel)
    if not isinstance(document, dict):
        raise NodeProtocolError("Conversation result must be an object")
    allowed = {
        "contract_version",
        "message_type",
        "request_id",
        "outcome",
        "reason_code",
        "node_session_id",
        "conversation_session_id",
        "response_text",
        "events",
        "proposed_actions",
    }
    if set(document) - allowed:
        raise NodeProtocolError("Conversation result contains unknown fields")
    request_id = document.get("request_id")
    outcome = document.get("outcome")
    reason_code = document.get("reason_code")
    node_session_id = document.get("node_session_id")
    conversation_session_id = document.get("conversation_session_id")
    response_text = document.get("response_text")
    if (
        document.get("contract_version") != CONTRACT_VERSION
        or document.get("message_type") != "conversation.result"
        or not _valid_uuid(request_id)
        or outcome not in {"accepted", "denied"}
        or not isinstance(reason_code, str)
        or not 1 <= len(reason_code) <= 128
        or (node_session_id is not None and not _valid_identifier(node_session_id))
        or (
            conversation_session_id is not None
            and not _valid_identifier(conversation_session_id)
        )
        or (
            response_text is not None
            and (
                not isinstance(response_text, str)
                or not 1 <= len(response_text) <= MAX_RESPONSE_TEXT_LENGTH
            )
        )
    ):
        raise NodeProtocolError("invalid Conversation result")
    events = _read_events(document.get("events", []))
    proposals = _read_proposals(document.get("proposed_actions", []))
    return ConversationWireResult(
        request_id,
        outcome == "accepted",
        reason_code,
        node_session_id,
        conversation_session_id,
        response_text,
        events,
        proposals,
    )


def _conversation_result(command, result) -> ConversationWireResult:
    session = result.session
    return ConversationWireResult(
        request_id=command.request_id,
        accepted=result.accepted,
        reason_code=result.reason.value,
        node_session_id=command.node_session_id if result.accepted else None,
        conversation_session_id=(
            session.session_id if result.accepted and session is not None else None
        ),
        events=tuple(_state_event(event) for event in result.events),
    )


def _state_event(event: ConversationStateEvent) -> dict[str, object]:
    return {"type": "character.state", "payload": {"state": event.state.value}}


def _wire_proposal(proposal: ProposedAction) -> dict[str, object]:
    return {
        "name": proposal.name,
        "arguments": dict(proposal.arguments),
        "authorization_status": "pending_policy",
        "execution_status": "not_executed",
    }


def _read_events(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list) or len(value) > MAX_EVENTS:
        raise NodeProtocolError("Conversation result events are invalid")
    events = []
    for event in value:
        if (
            not isinstance(event, dict)
            or set(event) != {"type", "payload"}
            or event.get("type") != "character.state"
            or not isinstance(event.get("payload"), dict)
            or set(event["payload"]) != {"state"}
            or event["payload"].get("state")
            not in {"sleeping", "listening", "thinking", "speaking", "engaged"}
        ):
            raise NodeProtocolError("Conversation result contains invalid semantic event")
        events.append(event)
    return tuple(events)


def _read_proposals(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list) or len(value) > MAX_PROPOSALS:
        raise NodeProtocolError("Conversation result proposals are invalid")
    proposals = []
    for proposal in value:
        if (
            not isinstance(proposal, dict)
            or set(proposal)
            != {"name", "arguments", "authorization_status", "execution_status"}
            or not isinstance(proposal.get("name"), str)
            or CAPABILITY_PATTERN.fullmatch(proposal["name"]) is None
            or not isinstance(proposal.get("arguments"), dict)
            or any(
                not isinstance(key, str)
                or not isinstance(item, str)
                or len(key) > 128
                or len(item) > 256
                for key, item in proposal["arguments"].items()
            )
            or proposal.get("authorization_status") != "pending_policy"
            or proposal.get("execution_status") != "not_executed"
        ):
            raise NodeProtocolError("Conversation result contains authoritative proposal")
        proposals.append(proposal)
    return tuple(proposals)


def _require_exact_fields(
    document: dict[str, object],
    expected: set[str],
) -> None:
    if set(document) != expected:
        raise NodeProtocolError("Conversation fields do not match its message type")


def _valid_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _valid_identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and IDENTIFIER_PATTERN.fullmatch(value) is not None
    )
