"""Outbound-only Mock Node using the public mTLS and Node Gateway protocol."""

from __future__ import annotations

import argparse
import json
import socket
import ssl
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from apps.assistant.src.adapters.node_gateway_protocol import (
    CONTRACT_VERSION,
    GatewayResult,
    NodeProtocolError,
    read_gateway_result,
    write_frame,
)
from apps.assistant.src.adapters.node_tls_transport import (
    MutualTlsClientAdapter,
    create_node_client_context,
)


MOCK_NODE_ID = "mock-node-01"
MOCK_NODE_CAPABILITIES = ("display", "speaker", "test.echo")


@dataclass
class MockNode:
    """Harmless Node client; administration remains outside this object."""

    node_id: str = MOCK_NODE_ID
    declared_capabilities: tuple[str, ...] = MOCK_NODE_CAPABILITIES
    channel: ssl.SSLSocket | None = None
    session_id: str | None = None

    def connect(
        self,
        connected_socket: socket.socket,
        *,
        context: ssl.SSLContext,
        server_hostname: str,
    ) -> None:
        if self.channel is not None:
            raise RuntimeError("Mock Node is already connected")
        self.channel = MutualTlsClientAdapter(context).wrap_connected_socket(
            connected_socket,
            server_hostname=server_hostname,
        )

    def open_session(self) -> GatewayResult:
        result = self._exchange(
            {
                "contract_version": CONTRACT_VERSION,
                "message_type": "session.open",
                "request_id": str(uuid4()),
                "node_id": self.node_id,
            }
        )
        self.session_id = result.session_id if result.accepted else None
        return result

    def request_capability(
        self,
        capability: str,
        *,
        sequence: int,
    ) -> GatewayResult:
        if capability not in self.declared_capabilities:
            raise ValueError("Mock Node cannot request an undeclared capability")
        if self.session_id is None:
            raise RuntimeError("Mock Node has no authenticated technical session")
        return self._exchange(
            {
                "contract_version": CONTRACT_VERSION,
                "message_type": "capability.request",
                "request_id": str(uuid4()),
                "session_id": self.session_id,
                "sequence": sequence,
                "capability": capability,
            }
        )

    def close_session(self) -> GatewayResult:
        if self.session_id is None:
            raise RuntimeError("Mock Node has no authenticated technical session")
        result = self._exchange(
            {
                "contract_version": CONTRACT_VERSION,
                "message_type": "session.close",
                "request_id": str(uuid4()),
                "session_id": self.session_id,
            }
        )
        if result.accepted:
            self.session_id = None
        return result

    def close(self) -> None:
        if self.channel is not None:
            self.channel.close()
            self.channel = None
        self.session_id = None

    def _exchange(self, document: dict[str, object]) -> GatewayResult:
        if self.channel is None:
            raise RuntimeError("Mock Node is not connected")
        request_id = document["request_id"]
        write_frame(self.channel, document)
        result = read_gateway_result(self.channel)
        if result.request_id != request_id:
            raise NodeProtocolError("Node result correlation mismatch")
        return result


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the HearthGhost Mock Node")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--server-name")
    parser.add_argument("--certificate", type=Path)
    parser.add_argument("--private-key", type=Path)
    parser.add_argument("--ca", type=Path)
    options = parser.parse_args(arguments)
    if options.check:
        print(
            json.dumps(
                {
                    "node_id": MOCK_NODE_ID,
                    "capabilities": list(MOCK_NODE_CAPABILITIES),
                    "mode": "test_only",
                },
                sort_keys=True,
            )
        )
        return 0

    required = {
        "host": options.host,
        "port": options.port,
        "server_name": options.server_name,
        "certificate": options.certificate,
        "private_key": options.private_key,
        "ca": options.ca,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        parser.error("connection mode requires: " + ", ".join(missing))

    context = create_node_client_context(
        certificate_file=options.certificate,
        private_key_file=options.private_key,
        server_ca_file=options.ca,
    )
    node = MockNode()
    plain_socket = socket.create_connection(
        (options.host, options.port),
        timeout=5,
    )
    try:
        node.connect(
            plain_socket,
            context=context,
            server_hostname=options.server_name,
        )
        session = node.open_session()
        print(json.dumps(session.to_document(), sort_keys=True))
        if not session.accepted:
            return 1
        result = node.request_capability("test.echo", sequence=1)
        print(json.dumps(result.to_document(), sort_keys=True))
        return 0 if result.accepted else 1
    finally:
        node.close()
        plain_socket.close()


if __name__ == "__main__":
    raise SystemExit(main())
