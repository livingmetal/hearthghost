"""Length-prefixed JSON framing for the authenticated Node Gateway channel."""

from __future__ import annotations

import json
import socket
import ssl
import struct
from dataclasses import dataclass
from uuid import UUID

from apps.assistant.src.modules.node_security import (
    CAPABILITY_PATTERN,
    IDENTIFIER_PATTERN,
    CapabilityRequest,
)
from apps.assistant.src.ports.node_gateway import NodeGatewaySecurityBoundary


CONTRACT_VERSION = "1.0"
MAX_FRAME_BYTES = 16 * 1024
MAX_SEQUENCE = 2**63 - 1


class NodeProtocolError(ValueError):
    """The peer supplied a malformed, oversized, or truncated frame."""


@dataclass(frozen=True)
class GatewayMessage:
    message_type: str
    request_id: str
    node_id: str | None = None
    session_id: str | None = None
    sequence: int | None = None
    capability: str | None = None


@dataclass(frozen=True)
class GatewayResult:
    request_id: str
    accepted: bool
    reason_code: str
    session_id: str | None = None
    node_id: str | None = None

    def to_document(self) -> dict[str, object]:
        document: dict[str, object] = {
            "contract_version": CONTRACT_VERSION,
            "message_type": "node.result",
            "request_id": self.request_id,
            "outcome": "accepted" if self.accepted else "denied",
            "reason_code": self.reason_code,
        }
        if self.session_id is not None:
            document["session_id"] = self.session_id
        if self.node_id is not None:
            document["node_id"] = self.node_id
        return document


class NodeGatewayProtocol:
    """Dispatch one framed request through the public Node Gateway boundary."""

    def __init__(self, gateway: NodeGatewaySecurityBoundary) -> None:
        self._gateway = gateway

    def handle_next(self, channel: ssl.SSLSocket) -> GatewayResult:
        if not isinstance(channel, ssl.SSLSocket):
            raise NodeProtocolError("Node Gateway requires an authenticated TLS channel")
        message = read_gateway_message(channel)
        result = self._dispatch(channel, message)
        write_frame(channel, result.to_document())
        return result

    def _dispatch(
        self,
        channel: ssl.SSLSocket,
        message: GatewayMessage,
    ) -> GatewayResult:
        if message.message_type == "session.open":
            result = self._gateway.open_session(channel, message.node_id)
            return GatewayResult(
                request_id=message.request_id,
                accepted=result.opened,
                reason_code=result.reason.value,
                session_id=(
                    result.session.session_id
                    if result.opened and result.session is not None
                    else None
                ),
            )
        if message.message_type == "capability.request":
            result = self._gateway.admit_request(
                channel,
                CapabilityRequest(
                    request_id=message.request_id,
                    session_id=message.session_id,
                    sequence=message.sequence,
                    capability=message.capability,
                ),
            )
            return GatewayResult(
                request_id=message.request_id,
                accepted=result.admitted,
                reason_code=result.reason.value,
                node_id=result.node_id,
            )
        closed = self._gateway.close_session(channel, message.session_id)
        return GatewayResult(
            request_id=message.request_id,
            accepted=closed,
            reason_code="session_closed" if closed else "session_close_denied",
            session_id=message.session_id if closed else None,
        )


def read_gateway_message(channel: socket.socket) -> GatewayMessage:
    document = read_frame(channel)
    if not isinstance(document, dict):
        raise NodeProtocolError("Node message must be an object")
    if document.get("contract_version") != CONTRACT_VERSION:
        raise NodeProtocolError("unsupported Node message contract version")
    message_type = document.get("message_type")
    request_id = document.get("request_id")
    if message_type not in {
        "session.open",
        "capability.request",
        "session.close",
    } or not _valid_uuid(request_id):
        raise NodeProtocolError("invalid Node message identity")

    if message_type == "session.open":
        _require_exact_fields(
            document,
            {"contract_version", "message_type", "request_id", "node_id"},
        )
        node_id = document.get("node_id")
        if not _valid_identifier(node_id):
            raise NodeProtocolError("session.open requires node_id")
        return GatewayMessage(message_type, request_id, node_id=node_id)

    if message_type == "capability.request":
        _require_exact_fields(
            document,
            {
                "contract_version",
                "message_type",
                "request_id",
                "session_id",
                "sequence",
                "capability",
            },
        )
        session_id = document.get("session_id")
        sequence = document.get("sequence")
        capability = document.get("capability")
        if (
            not _valid_identifier(session_id)
            or not isinstance(sequence, int)
            or isinstance(sequence, bool)
            or not 1 <= sequence <= MAX_SEQUENCE
            or not isinstance(capability, str)
            or CAPABILITY_PATTERN.fullmatch(capability) is None
        ):
            raise NodeProtocolError("invalid capability.request fields")
        return GatewayMessage(
            message_type,
            request_id,
            session_id=session_id,
            sequence=sequence,
            capability=capability,
        )

    _require_exact_fields(
        document,
        {"contract_version", "message_type", "request_id", "session_id"},
    )
    session_id = document.get("session_id")
    if not _valid_identifier(session_id):
        raise NodeProtocolError("session.close requires session_id")
    return GatewayMessage(message_type, request_id, session_id=session_id)


def read_gateway_result(channel: socket.socket) -> GatewayResult:
    document = read_frame(channel)
    if not isinstance(document, dict):
        raise NodeProtocolError("Node result must be an object")
    allowed_fields = {
        "contract_version",
        "message_type",
        "request_id",
        "outcome",
        "reason_code",
        "session_id",
        "node_id",
    }
    if set(document) - allowed_fields:
        raise NodeProtocolError("Node result contains unknown fields")
    request_id = document.get("request_id")
    outcome = document.get("outcome")
    reason = document.get("reason_code")
    if (
        document.get("contract_version") != CONTRACT_VERSION
        or document.get("message_type") != "node.result"
        or not _valid_uuid(request_id)
        or outcome not in {"accepted", "denied"}
        or not isinstance(reason, str)
        or not 1 <= len(reason) <= 128
        or (
            document.get("session_id") is not None
            and not _valid_identifier(document.get("session_id"))
        )
        or (
            document.get("node_id") is not None
            and not _valid_identifier(document.get("node_id"))
        )
    ):
        raise NodeProtocolError("invalid Node result")
    return GatewayResult(
        request_id=request_id,
        accepted=outcome == "accepted",
        reason_code=reason,
        session_id=document.get("session_id"),
        node_id=document.get("node_id"),
    )


def write_frame(channel: socket.socket, document: dict[str, object]) -> None:
    try:
        payload = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise NodeProtocolError("message is not JSON serializable") from error
    if not payload or len(payload) > MAX_FRAME_BYTES:
        raise NodeProtocolError("Node frame size is invalid")
    channel.sendall(struct.pack("!I", len(payload)) + payload)


def read_frame(channel: socket.socket) -> object:
    header = _read_exact(channel, 4)
    length = struct.unpack("!I", header)[0]
    if not 1 <= length <= MAX_FRAME_BYTES:
        raise NodeProtocolError("Node frame size is invalid")
    payload = _read_exact(channel, length)
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise NodeProtocolError("Node frame is not valid UTF-8 JSON") from error


def _read_exact(channel: socket.socket, length: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < length:
        chunk = channel.recv(length - len(chunks))
        if not chunk:
            raise NodeProtocolError("Node frame was truncated")
        chunks.extend(chunk)
    return bytes(chunks)


def _require_exact_fields(
    document: dict[str, object], expected: set[str]
) -> None:
    if set(document) != expected:
        raise NodeProtocolError("Node message fields do not match its type")


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
