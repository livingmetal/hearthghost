"""Authenticated, capability-gated Windows client update distribution."""

from __future__ import annotations

import hashlib
import re
import ssl
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import UUID

from apps.assistant.src.adapters.node_gateway_protocol import (
    CONTRACT_VERSION,
    MAX_SEQUENCE,
    NodeProtocolError,
    write_frame,
)
from apps.assistant.src.modules.node_security import CapabilityRequest, IDENTIFIER_PATTERN
from apps.assistant.src.ports.node_gateway import NodeGatewaySecurityBoundary


UPDATE_CAPABILITY = "client.update"
PLATFORM = "win-x64"
MAX_FILES = 128
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_BUNDLE_BYTES = 256 * 1024 * 1024
RELEASE_PATTERN = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class UpdateFile:
    path: str
    size: int
    sha256: str
    source: Path

    def to_document(self) -> dict[str, object]:
        return {"path": self.path, "size": self.size, "sha256": self.sha256}


class ClientUpdateBundle:
    """Immutable metadata for one server-built client directory."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("client update root must be a directory")
        release_path = self.root / ".hearthghost-release"
        self.release_id = release_path.read_text(encoding="ascii").strip()
        if RELEASE_PATTERN.fullmatch(self.release_id) is None:
            raise ValueError("client update release id is invalid")

        files: list[UpdateFile] = []
        total = 0
        for source in sorted(self.root.rglob("*")):
            if source.is_symlink():
                raise ValueError("client update bundle must not contain symlinks")
            if not source.is_file():
                continue
            relative = source.relative_to(self.root).as_posix()
            _validate_relative_path(relative)
            size = source.stat().st_size
            if size > MAX_FILE_BYTES:
                raise ValueError("client update file exceeds size limit")
            total += size
            if total > MAX_BUNDLE_BYTES:
                raise ValueError("client update bundle exceeds size limit")
            digest = hashlib.sha256()
            with source.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            files.append(UpdateFile(relative, size, digest.hexdigest(), source))
        if not files or len(files) > MAX_FILES:
            raise ValueError("client update bundle file count is invalid")
        self.files = tuple(files)
        self._by_path = {item.path: item for item in self.files}

    def find(self, path: str) -> UpdateFile | None:
        return self._by_path.get(path)


class ClientUpdateProtocol:
    """Serve one pinned bundle only after per-request Gateway admission."""

    def __init__(self, gateway: NodeGatewaySecurityBoundary, bundle: ClientUpdateBundle) -> None:
        self._gateway = gateway
        self._bundle = bundle

    def handle_document(self, channel: ssl.SSLSocket, document: object) -> None:
        if not isinstance(channel, ssl.SSLSocket):
            raise NodeProtocolError("client update requires an authenticated TLS channel")
        command = _parse_command(document)
        admission = self._gateway.admit_request(
            channel,
            CapabilityRequest(
                request_id=command["request_id"],
                session_id=command["node_session_id"],
                sequence=command["sequence"],
                capability=UPDATE_CAPABILITY,
            ),
        )
        if not admission.admitted:
            self._write_result(channel, command, False, admission.reason.value)
            return
        if command["message_type"] == "client.update.check":
            available = command["current_release_id"] != self._bundle.release_id
            extra: dict[str, object] = {
                "available": available,
                "release_id": self._bundle.release_id,
            }
            if available:
                extra["files"] = [item.to_document() for item in self._bundle.files]
            self._write_result(channel, command, True, "update_available" if available else "update_current", extra)
            return

        if command["release_id"] != self._bundle.release_id:
            self._write_result(channel, command, False, "update_release_changed")
            return
        item = self._bundle.find(command["path"])
        if item is None:
            self._write_result(channel, command, False, "update_file_unknown")
            return
        self._write_result(
            channel,
            command,
            True,
            "update_file_ready",
            {"release_id": self._bundle.release_id, **item.to_document()},
        )
        with item.source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                channel.sendall(chunk)

    @staticmethod
    def _write_result(
        channel: ssl.SSLSocket,
        command: dict[str, object],
        accepted: bool,
        reason: str,
        extra: dict[str, object] | None = None,
    ) -> None:
        result: dict[str, object] = {
            "contract_version": CONTRACT_VERSION,
            "message_type": "client.update.result",
            "request_id": command["request_id"],
            "outcome": "accepted" if accepted else "denied",
            "reason_code": reason,
            "node_session_id": command["node_session_id"],
        }
        if extra:
            result.update(extra)
        write_frame(channel, result)


def _parse_command(document: object) -> dict[str, object]:
    if not isinstance(document, dict):
        raise NodeProtocolError("client update command must be an object")
    message_type = document.get("message_type")
    common = {"contract_version", "message_type", "request_id", "node_session_id", "sequence"}
    expected = common | (
        {"platform", "current_release_id"}
        if message_type == "client.update.check"
        else {"release_id", "path"}
    )
    if message_type not in {"client.update.check", "client.update.file"} or set(document) != expected:
        raise NodeProtocolError("invalid client update command fields")
    request_id = document.get("request_id")
    session_id = document.get("node_session_id")
    sequence = document.get("sequence")
    try:
        if not isinstance(request_id, str):
            raise ValueError
        UUID(request_id)
    except (ValueError, TypeError):
        raise NodeProtocolError("invalid client update command identity") from None
    if (
        document.get("contract_version") != CONTRACT_VERSION
        or not isinstance(session_id, str)
        or IDENTIFIER_PATTERN.fullmatch(session_id) is None
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not 1 <= sequence <= MAX_SEQUENCE
    ):
        raise NodeProtocolError("invalid client update command identity")
    if message_type == "client.update.check":
        current = document.get("current_release_id")
        if document.get("platform") != PLATFORM or not isinstance(current, str) or len(current) > 128:
            raise NodeProtocolError("invalid client update check")
    else:
        release = document.get("release_id")
        path = document.get("path")
        if not isinstance(release, str) or RELEASE_PATTERN.fullmatch(release) is None or not isinstance(path, str):
            raise NodeProtocolError("invalid client update file request")
        _validate_relative_path(path)
    return document


def _validate_relative_path(value: str) -> None:
    if not value or len(value) > 240 or "\\" in value or "\x00" in value:
        raise NodeProtocolError("invalid client update path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise NodeProtocolError("invalid client update path")
