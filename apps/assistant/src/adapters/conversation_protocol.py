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
from apps.assistant.src.modules.behavior_preference_command import BehaviorPreferenceCommandService
from apps.assistant.src.modules.conversation import (
    AdmittedConversationNode,
    ConversationManager,
    ConversationStateEvent,
    TEXT_CAPABILITY,
)
from apps.assistant.src.modules.memory_command import MemoryCommandService
from apps.assistant.src.modules.node_security import (
    CAPABILITY_PATTERN,
    IDENTIFIER_PATTERN,
    CapabilityRequest,
)
from apps.assistant.src.modules.orchestrator import ConversationOrchestrator
from apps.assistant.src.modules.persona import require_persona_name
from apps.assistant.src.modules.productivity_command import ProductivityCommandService
from apps.assistant.src.modules.reminder_command import ReminderCommandService
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
    character_profile: dict[str, str] | None = None

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
            ("character_profile", self.character_profile),
        ):
            if value is not None:
                document[field] = value
        if self.events:
            document["events"] = list(self.events)
        if self.proposed_actions:
            document["proposed_actions"] = list(self.proposed_actions)
        return document


class ConversationProtocol:
    """Admit every command through Node Gateway before conversation dispatch."""

    def __init__(
        self,
        *,
        gateway: NodeGatewaySecurityBoundary,
        conversation: ConversationManager,
        orchestrator: ConversationOrchestrator,
        memory_commands: MemoryCommandService | None = None,
        reminder_commands: ReminderCommandService | None = None,
        productivity_commands: ProductivityCommandService | None = None,
        preference_commands: BehaviorPreferenceCommandService | None = None,
    ) -> None:
        self._gateway = gateway
        self._conversation = conversation
        self._orchestrator = orchestrator
        self._memory_commands = memory_commands
        self._reminder_commands = reminder_commands
        self._productivity_commands = productivity_commands
        self._preference_commands = preference_commands

    def handle_next(self, channel: ssl.SSLSocket) -> ConversationWireResult:
        if not isinstance(channel, ssl.SSLSocket):
            raise NodeProtocolError("Conversation requires an authenticated TLS channel")
        return self.handle_document(channel, read_frame(channel))

    def handle_document(self, channel: ssl.SSLSocket, document: object) -> ConversationWireResult:
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
            result = ConversationWireResult(command.request_id, False, admission.reason.value)
        else:
            node = AdmittedConversationNode(True, admission.node_id, command.node_session_id, TEXT_CAPABILITY)
            result = self._dispatch(node, command)
        write_frame(channel, result.to_document())
        return result

    def _dispatch(self, node: AdmittedConversationNode, command: ConversationCommand) -> ConversationWireResult:
        if command.message_type == "conversation.open":
            return _conversation_result(
                command,
                self._conversation.open(node),
                character_profile=self._character_profile(),
            )
        if command.message_type == "conversation.close":
            return _conversation_result(
                command,
                self._conversation.end(node, command.conversation_session_id),
                character_profile=self._character_profile(),
            )

        accepted = self._conversation.accept_text(node, command.conversation_session_id, command.text)
        if not accepted.accepted or accepted.turn is None:
            return _conversation_result(command, accepted)

        if self._memory_commands is not None:
            memory_result = self._memory_commands.handle(
                node_id=node.node_id,
                text=accepted.turn.text,
                conversation_session_id=accepted.turn.session_id,
            )
            if memory_result.recognized:
                text = "기억했어요." if memory_result.stored else "기억 범위를 안전하게 확인할 수 없어 저장하지 않았어요."
                return self._complete_local(
                    node=node,
                    command=command,
                    accepted=accepted,
                    reason_code=memory_result.reason,
                    response_text=text,
                )

        if self._reminder_commands is not None:
            reminder_result = self._reminder_commands.handle(
                node_id=node.node_id,
                text=accepted.turn.text,
            )
            if reminder_result.recognized:
                return self._complete_local(
                    node=node,
                    command=command,
                    accepted=accepted,
                    reason_code=reminder_result.reason,
                    response_text=reminder_result.response_text or "알림 요청을 처리하지 않았어요.",
                )

        if self._productivity_commands is not None:
            productivity_result = self._productivity_commands.handle(
                node_id=node.node_id,
                text=accepted.turn.text,
                conversation_session_id=accepted.turn.session_id,
            )
            if productivity_result.recognized:
                return self._complete_local(
                    node=node,
                    command=command,
                    accepted=accepted,
                    reason_code=productivity_result.reason,
                    response_text=productivity_result.response_text or "요청을 처리하지 않았어요.",
                )

        if self._preference_commands is not None:
            preference_result = self._preference_commands.handle(
                node_id=node.node_id,
                text=accepted.turn.text,
            )
            if preference_result.recognized:
                return self._complete_local(
                    node=node,
                    command=command,
                    accepted=accepted,
                    reason_code=preference_result.reason,
                    response_text=preference_result.response_text or "캐릭터 설정 요청을 처리하지 않았어요.",
                )

        response = self._orchestrator.respond(node, accepted.turn)
        if not response.conversation_completed:
            return ConversationWireResult(command.request_id, False, response.reason.value)
        events = accepted.events + response.events
        return ConversationWireResult(
            request_id=command.request_id,
            accepted=True,
            reason_code=response.reason.value,
            node_session_id=command.node_session_id,
            conversation_session_id=command.conversation_session_id,
            response_text=response.response_text,
            events=tuple(_state_event(event) for event in events),
            proposed_actions=tuple(_wire_proposal(proposal) for proposal in response.proposed_actions),
            character_profile=self._character_profile(),
        )

    def _complete_local(
        self,
        *,
        node: AdmittedConversationNode,
        command: ConversationCommand,
        accepted,
        reason_code: str,
        response_text: str,
    ) -> ConversationWireResult:
        completed = self._conversation.complete_response(node, accepted.turn.session_id, response_text)
        if not completed.accepted:
            return ConversationWireResult(command.request_id, False, completed.reason.value)
        events = accepted.events + completed.events
        return ConversationWireResult(
            request_id=command.request_id,
            accepted=True,
            reason_code=reason_code,
            node_session_id=command.node_session_id,
            conversation_session_id=command.conversation_session_id,
            response_text=response_text,
            events=tuple(_state_event(event) for event in events),
            character_profile=self._character_profile(),
        )

    def _character_profile(self) -> dict[str, str]:
        return {"name": require_persona_name(self._orchestrator.persona.name)}


def read_conversation_command(channel) -> ConversationCommand:
    return parse_conversation_command(read_frame(channel))


def parse_conversation_command(document: object) -> ConversationCommand:
    if not isinstance(document, dict):
        raise NodeProtocolError("Conversation command must be an object")
    if document.get("contract_version") != CONTRACT_VERSION:
        raise NodeProtocolError("unsupported conversation contract version")
    message_type = document.get("message_type")
    request_id = document.get("request_id")
    node_session_id = document.get("node_session_id")
    sequence = document.get("sequence")
    if (
        message_type not in {"conversation.open", "conversation.text", "conversation.close"}
        or not _valid_uuid(request_id)
        or not _valid_identifier(node_session_id)
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not 1 <= sequence <= MAX_SEQUENCE
    ):
        raise NodeProtocolError("invalid conversation command identity")
    base = {"contract_version", "message_type", "request_id", "node_session_id", "sequence"}
    if message_type == "conversation.open":
        _require_exact_fields(document, base)
        return ConversationCommand(message_type, request_id, node_session_id, sequence)
    conversation_session_id = document.get("conversation_session_id")
    if not _valid_identifier(conversation_session_id):
        raise NodeProtocolError("conversation command requires a session identifier")
    if message_type == "conversation.close":
        _require_exact_fields(document, base | {"conversation_session_id"})
        return ConversationCommand(message_type, request_id, node_session_id, sequence, conversation_session_id)
    _require_exact_fields(document, base | {"conversation_session_id", "text"})
    text = document.get("text")
    if not isinstance(text, str) or not 1 <= len(text) <= MAX_TEXT_LENGTH:
        raise NodeProtocolError("conversation.text requires bounded text")
    return ConversationCommand(message_type, request_id, node_session_id, sequence, conversation_session_id, text)


def read_conversation_result(channel) -> ConversationWireResult:
    document = read_frame(channel)
    if not isinstance(document, dict):
        raise NodeProtocolError("Conversation result must be an object")
    allowed = {"contract_version", "message_type", "request_id", "outcome", "reason_code", "node_session_id", "conversation_session_id", "response_text", "events", "proposed_actions", "character_profile"}
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
        or (conversation_session_id is not None and not _valid_identifier(conversation_session_id))
        or (response_text is not None and (not isinstance(response_text, str) or not 1 <= len(response_text) <= MAX_RESPONSE_TEXT_LENGTH))
    ):
        raise NodeProtocolError("invalid Conversation result")
    return ConversationWireResult(
        request_id=request_id,
        accepted=outcome == "accepted",
        reason_code=reason_code,
        node_session_id=node_session_id,
        conversation_session_id=conversation_session_id,
        response_text=response_text,
        events=_read_events(document.get("events", [])),
        proposed_actions=_read_proposals(document.get("proposed_actions", [])),
        character_profile=_read_character_profile(document.get("character_profile")),
    )


def _conversation_result(command, result, *, character_profile: dict[str, str] | None = None) -> ConversationWireResult:
    session = result.session
    return ConversationWireResult(
        request_id=command.request_id,
        accepted=result.accepted,
        reason_code=result.reason.value,
        node_session_id=command.node_session_id if result.accepted else None,
        conversation_session_id=session.session_id if result.accepted and session is not None else None,
        events=tuple(_state_event(event) for event in result.events),
        character_profile=character_profile if result.accepted else None,
    )


def _state_event(event: ConversationStateEvent) -> dict[str, object]:
    return {"type": "character.state", "payload": {"state": event.state.value}}


def _wire_proposal(proposal: ProposedAction) -> dict[str, object]:
    return {"name": proposal.name, "arguments": dict(proposal.arguments), "authorization_status": "pending_policy", "execution_status": "not_executed"}


def _read_character_profile(value: object) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"name"}:
        raise NodeProtocolError("Conversation result character profile is invalid")
    try:
        name = require_persona_name(value.get("name"))
    except ValueError as error:
        raise NodeProtocolError("Conversation result character profile is invalid") from error
    return {"name": name}


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
            or event["payload"].get("state") not in {"sleeping", "listening", "thinking", "speaking", "engaged"}
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
            or set(proposal) != {"name", "arguments", "authorization_status", "execution_status"}
            or not isinstance(proposal.get("name"), str)
            or CAPABILITY_PATTERN.fullmatch(proposal["name"]) is None
            or not isinstance(proposal.get("arguments"), dict)
            or any(not isinstance(key, str) or not isinstance(item, str) or len(key) > 128 or len(item) > 256 for key, item in proposal["arguments"].items())
            or proposal.get("authorization_status") != "pending_policy"
            or proposal.get("execution_status") != "not_executed"
        ):
            raise NodeProtocolError("Conversation result contains authoritative proposal")
        proposals.append(proposal)
    return tuple(proposals)


def _require_exact_fields(document: dict[str, object], expected: set[str]) -> None:
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
    return isinstance(value, str) and IDENTIFIER_PATTERN.fullmatch(value) is not None
