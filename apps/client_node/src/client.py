"""Outbound development Client Node for the text walking skeleton."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from uuid import uuid4

from apps.assistant.src.adapters.conversation_protocol import (
    ConversationWireResult,
    read_conversation_result,
)
from apps.assistant.src.adapters.node_gateway_protocol import (
    CONTRACT_VERSION,
    NodeProtocolError,
    write_frame,
)
from apps.mock_node.src.client import MockNode


CLIENT_NODE_ID = "development-client-01"
CLIENT_NODE_CAPABILITIES = ("display", "conversation.text")


@dataclass
class DevelopmentTextClientNode(MockNode):
    node_id: str = CLIENT_NODE_ID
    declared_capabilities: tuple[str, ...] = CLIENT_NODE_CAPABILITIES
    conversation_session_id: str | None = None
    semantic_events: list[dict[str, object]] = field(default_factory=list)

    def open_conversation(self, *, sequence: int) -> ConversationWireResult:
        if self.session_id is None:
            raise RuntimeError("Client Node has no authenticated technical session")
        result = self._conversation_exchange(
            {
                "contract_version": CONTRACT_VERSION,
                "message_type": "conversation.open",
                "request_id": str(uuid4()),
                "node_session_id": self.session_id,
                "sequence": sequence,
            }
        )
        if result.accepted:
            self.conversation_session_id = result.conversation_session_id
        return result

    def send_text(self, text: str, *, sequence: int) -> ConversationWireResult:
        if self.session_id is None or self.conversation_session_id is None:
            raise RuntimeError("Client Node has no active conversation")
        return self._conversation_exchange(
            {
                "contract_version": CONTRACT_VERSION,
                "message_type": "conversation.text",
                "request_id": str(uuid4()),
                "node_session_id": self.session_id,
                "sequence": sequence,
                "conversation_session_id": self.conversation_session_id,
                "text": text,
            }
        )

    def close_conversation(self, *, sequence: int) -> ConversationWireResult:
        if self.session_id is None or self.conversation_session_id is None:
            raise RuntimeError("Client Node has no active conversation")
        result = self._conversation_exchange(
            {
                "contract_version": CONTRACT_VERSION,
                "message_type": "conversation.close",
                "request_id": str(uuid4()),
                "node_session_id": self.session_id,
                "sequence": sequence,
                "conversation_session_id": self.conversation_session_id,
            }
        )
        if result.accepted:
            self.conversation_session_id = None
        return result

    def close(self) -> None:
        super().close()
        self.conversation_session_id = None
        self.semantic_events.clear()

    def _conversation_exchange(
        self,
        document: dict[str, object],
    ) -> ConversationWireResult:
        if self.channel is None:
            raise RuntimeError("Client Node is not connected")
        request_id = document["request_id"]
        write_frame(self.channel, document)
        result = read_conversation_result(self.channel)
        if result.request_id != request_id:
            raise NodeProtocolError("Conversation result correlation mismatch")
        self.semantic_events.extend(result.events)
        return result


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the development Client Node")
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args(arguments)
    if not options.check:
        parser.error("only --check is available; the E2E harness owns test-only TLS")
    print(
        json.dumps(
            {
                "node_id": CLIENT_NODE_ID,
                "capabilities": list(CLIENT_NODE_CAPABILITIES),
                "direction": "outbound_only",
                "mode": "development_test_only",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
