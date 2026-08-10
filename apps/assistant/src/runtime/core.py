"""Minimal executable HearthGhost Core composition and loopback status API."""

from __future__ import annotations

import argparse
import ipaddress
import json
import signal
from dataclasses import dataclass
from datetime import timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from apps.assistant.src.adapters.contract_catalog import ContractCatalog
from apps.assistant.src.adapters.in_memory_core import (
    DenyingAdministratorAuthorizer,
    InMemoryCredentialRepository,
    InMemoryNodeRegistry,
    InMemoryReplayProtector,
    InMemorySessionRepository,
    RejectingCredentialAuthenticator,
)
from apps.assistant.src.modules.node_administration import NodeAdministration
from apps.assistant.src.modules.node_security import NodeGatewaySecurity, SystemClock
from apps.assistant.src.modules.policy import UnconfiguredPolicyBoundary
from apps.assistant.src.ports.node_administration import AdministratorAuthorizer
from apps.assistant.src.ports.node_gateway import CredentialAuthenticator
from apps.assistant.src.ports.policy import PolicyBoundary


DEFAULT_BIND_ADDRESS = "127.0.0.1"
DEFAULT_STATUS_PORT = 8080
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class CoreComponents:
    """One-process composition of the initial Core logical boundaries."""

    node_gateway: NodeGatewaySecurity
    node_administration: NodeAdministration
    policy: PolicyBoundary
    registry: InMemoryNodeRegistry
    credentials: InMemoryCredentialRepository
    contracts: ContractCatalog
    transport_configured: bool
    administrator_authority_configured: bool
    policy_rules_configured: bool

    def liveness(self) -> dict[str, object]:
        return {
            "service": "hearthghost-core",
            "status": "alive",
        }

    def readiness(self) -> tuple[bool, dict[str, object]]:
        missing = []
        if not self.transport_configured:
            missing.append("node_transport_not_configured")
        if not self.administrator_authority_configured:
            missing.append("administrator_authority_not_configured")
        if not self.policy_rules_configured:
            missing.append("policy_rules_not_configured")
        ready = not missing
        return ready, {
            "service": "hearthghost-core",
            "status": "ready" if ready else "not_ready",
            "reasons": missing,
        }

    def status(self) -> dict[str, object]:
        ready, readiness = self.readiness()
        return {
            "service": "hearthghost-core",
            "status": "ready" if ready else "degraded",
            "storage": "ephemeral",
            "contracts_loaded": self.contracts.count,
            "boundaries": {
                "node_gateway": "loaded",
                "node_administration": "loaded",
                "registry": "loaded",
                "contract_catalog": "loaded",
                "node_transport": (
                    "configured" if self.transport_configured else "deny_only"
                ),
                "administrator_authority": (
                    "configured"
                    if self.administrator_authority_configured
                    else "deny_only"
                ),
                "policy": (
                    "configured" if self.policy_rules_configured else "deny_only"
                ),
            },
            "readiness_reasons": readiness["reasons"],
        }


def build_core(
    *,
    contracts_root: Path | None = None,
    authenticator: CredentialAuthenticator | None = None,
    administrator_authorizer: AdministratorAuthorizer | None = None,
    policy: PolicyBoundary | None = None,
) -> CoreComponents:
    """Build Core with explicit deny-only substitutes for missing authorities."""

    clock = SystemClock()
    registry = InMemoryNodeRegistry()
    credentials = InMemoryCredentialRepository()
    sessions = InMemorySessionRepository()
    replay = InMemoryReplayProtector()
    selected_authenticator = (
        authenticator
        if authenticator is not None
        else RejectingCredentialAuthenticator()
    )
    selected_authorizer = (
        administrator_authorizer
        if administrator_authorizer is not None
        else DenyingAdministratorAuthorizer()
    )
    selected_policy = policy if policy is not None else UnconfiguredPolicyBoundary()
    gateway = NodeGatewaySecurity(
        authenticator=selected_authenticator,
        credentials=credentials,
        nodes=registry,
        sessions=sessions,
        replay=replay,
        clock=clock,
        session_lifetime=timedelta(minutes=15),
    )
    administration = NodeAdministration(
        authorizer=selected_authorizer,
        store=registry,
        capabilities=registry,
        clock=clock,
    )
    return CoreComponents(
        node_gateway=gateway,
        node_administration=administration,
        policy=selected_policy,
        registry=registry,
        credentials=credentials,
        contracts=ContractCatalog(contracts_root or REPOSITORY_ROOT / "contracts"),
        transport_configured=authenticator is not None,
        administrator_authority_configured=administrator_authorizer is not None,
        policy_rules_configured=policy is not None,
    )


class CoreStatusServer(ThreadingHTTPServer):
    """Small loopback-only HTTP server for non-sensitive runtime status."""

    daemon_threads = True
    request_queue_size = 8
    allow_reuse_address = False

    def __init__(
        self,
        server_address: tuple[str, int],
        components: CoreComponents,
    ) -> None:
        _require_loopback(server_address[0])
        self.components = components
        super().__init__(server_address, _status_handler())


def _status_handler() -> type[BaseHTTPRequestHandler]:
    class StatusHandler(BaseHTTPRequestHandler):
        server: CoreStatusServer
        server_version = "HearthGhostCore"
        sys_version = ""

        def do_GET(self) -> None:
            path = self.path.partition("?")[0]
            if path == "/health/live":
                self._send(HTTPStatus.OK, self.server.components.liveness())
                return
            if path == "/health/ready":
                ready, body = self.server.components.readiness()
                self._send(
                    HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE,
                    body,
                )
                return
            if path == "/status":
                self._send(HTTPStatus.OK, self.server.components.status())
                return
            self._send(
                HTTPStatus.NOT_FOUND,
                {"status": "not_found"},
            )

        def do_POST(self) -> None:
            self._send(
                HTTPStatus.METHOD_NOT_ALLOWED,
                {"status": "method_not_allowed"},
            )

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, status: HTTPStatus, body: dict[str, object]) -> None:
            payload = json.dumps(
                body,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

    return StatusHandler


def serve(
    components: CoreComponents,
    *,
    bind_address: str = DEFAULT_BIND_ADDRESS,
    port: int = DEFAULT_STATUS_PORT,
    server_factory: Callable[
        [tuple[str, int], CoreComponents], CoreStatusServer
    ] = CoreStatusServer,
) -> None:
    _require_loopback(bind_address)
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError("status port must be between 1 and 65535")
    with server_factory((bind_address, port), components) as server:
        prior_sigterm_handler = None

        def terminate(signum: int, frame: object) -> None:
            raise SystemExit(0)

        try:
            prior_sigterm_handler = signal.signal(signal.SIGTERM, terminate)
        except ValueError:
            pass
        try:
            server.serve_forever(poll_interval=0.25)
        finally:
            if prior_sigterm_handler is not None:
                signal.signal(signal.SIGTERM, prior_sigterm_handler)


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the minimal HearthGhost Core")
    parser.add_argument("--bind", default=DEFAULT_BIND_ADDRESS)
    parser.add_argument("--port", type=int, default=DEFAULT_STATUS_PORT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="load Core boundaries and print status without starting a listener",
    )
    options = parser.parse_args(arguments)
    components = build_core()
    if options.check:
        print(json.dumps(components.status(), sort_keys=True))
        return 0
    serve(components, bind_address=options.bind, port=options.port)
    return 0


def _require_loopback(address: str) -> None:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as error:
        raise ValueError("status listener requires a literal loopback address") from error
    if not parsed.is_loopback:
        raise ValueError("status listener may bind only to loopback")


if __name__ == "__main__":
    raise SystemExit(main())
