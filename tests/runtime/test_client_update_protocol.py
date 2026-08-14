from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from apps.assistant.src.adapters.client_update_protocol import (
    ClientUpdateBundle,
    ClientUpdateProtocol,
)
from apps.assistant.src.adapters.node_gateway_protocol import NodeProtocolError


RELEASE = "a" * 40


class FakeTlsChannel:
    def __init__(self) -> None:
        self.sent = bytearray()

    def sendall(self, value: bytes) -> None:
        self.sent.extend(value)


class FakeGateway:
    def __init__(self, admitted: bool) -> None:
        self.admitted = admitted
        self.requests = []

    def admit_request(self, channel, request):
        self.requests.append(request)
        return SimpleNamespace(
            admitted=self.admitted,
            reason=SimpleNamespace(value="request_admitted" if self.admitted else "capability_not_granted"),
        )


class ClientUpdateProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="hearthghost-update-")
        self.root = Path(self.temporary.name)
        (self.root / ".hearthghost-release").write_text(RELEASE + "\n", encoding="ascii")
        (self.root / "HearthGhost.WindowsClient.exe").write_bytes(b"verified-client")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_check_requires_client_update_capability_and_returns_hash_manifest(self):
        gateway = FakeGateway(True)
        channel = FakeTlsChannel()
        protocol = ClientUpdateProtocol(gateway, ClientUpdateBundle(self.root))
        with patch(
            "apps.assistant.src.adapters.client_update_protocol.ssl.SSLSocket",
            FakeTlsChannel,
        ):
            protocol.handle_document(channel, self._check("unversioned"))

        document, remainder = self._first_frame(channel.sent)
        self.assertEqual(remainder, b"")
        self.assertEqual(gateway.requests[0].capability, "client.update")
        self.assertEqual(document["outcome"], "accepted")
        self.assertTrue(document["available"])
        files = {item["path"]: item for item in document["files"]}
        self.assertEqual(files["HearthGhost.WindowsClient.exe"]["size"], 15)
        self.assertEqual(len(files["HearthGhost.WindowsClient.exe"]["sha256"]), 64)

    def test_denied_capability_never_exposes_manifest_or_file_bytes(self):
        gateway = FakeGateway(False)
        channel = FakeTlsChannel()
        protocol = ClientUpdateProtocol(gateway, ClientUpdateBundle(self.root))
        with patch(
            "apps.assistant.src.adapters.client_update_protocol.ssl.SSLSocket",
            FakeTlsChannel,
        ):
            protocol.handle_document(channel, self._check("unversioned"))

        document, remainder = self._first_frame(channel.sent)
        self.assertEqual(remainder, b"")
        self.assertEqual(document["outcome"], "denied")
        self.assertNotIn("files", document)
        self.assertNotIn("release_id", document)

    def test_file_request_streams_only_the_manifest_bound_file(self):
        gateway = FakeGateway(True)
        channel = FakeTlsChannel()
        protocol = ClientUpdateProtocol(gateway, ClientUpdateBundle(self.root))
        command = {
            "contract_version": "1.0",
            "message_type": "client.update.file",
            "request_id": str(uuid4()),
            "node_session_id": "session-1",
            "sequence": 2,
            "release_id": RELEASE,
            "path": "HearthGhost.WindowsClient.exe",
        }
        with patch(
            "apps.assistant.src.adapters.client_update_protocol.ssl.SSLSocket",
            FakeTlsChannel,
        ):
            protocol.handle_document(channel, command)

        document, remainder = self._first_frame(channel.sent)
        self.assertEqual(document["reason_code"], "update_file_ready")
        self.assertEqual(remainder, b"verified-client")

    def test_traversal_and_unknown_fields_fail_closed(self):
        invalid = {
            "contract_version": "1.0",
            "message_type": "client.update.file",
            "request_id": str(uuid4()),
            "node_session_id": "session-1",
            "sequence": 2,
            "release_id": RELEASE,
            "path": "../secret",
        }
        protocol = ClientUpdateProtocol(FakeGateway(True), ClientUpdateBundle(self.root))
        with patch(
            "apps.assistant.src.adapters.client_update_protocol.ssl.SSLSocket",
            FakeTlsChannel,
        ), self.assertRaises(NodeProtocolError):
            protocol.handle_document(FakeTlsChannel(), invalid)

    @staticmethod
    def _check(current_release: str) -> dict[str, object]:
        return {
            "contract_version": "1.0",
            "message_type": "client.update.check",
            "request_id": str(uuid4()),
            "node_session_id": "session-1",
            "sequence": 1,
            "platform": "win-x64",
            "current_release_id": current_release,
        }

    @staticmethod
    def _first_frame(payload: bytearray) -> tuple[dict[str, object], bytes]:
        length = struct.unpack("!I", payload[:4])[0]
        return json.loads(payload[4 : 4 + length]), bytes(payload[4 + length :])


if __name__ == "__main__":
    unittest.main()
