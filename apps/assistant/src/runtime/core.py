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
from apps.assistant.src.adapters.in_memory_conversation import InMemoryConversationRepository
from apps.assistant.src.adapters.in_memory_memory import InMemoryMemoryRepository
from apps.assistant.src.adapters.in_memory_todo import InMemoryTodoRepository
from apps.assistant.src.adapters.fake_llm import UnavailableLLMAdapter
from apps.assistant.src.modules.behavior_preference_interpreter import (
    BehaviorPreferenceInterpreter,
    BehaviorPreferenceService,
)
from apps.assistant.src.modules.behavior_preferences import BehaviorPreferenceManager
from apps.assistant.src.modules.conversation import ConversationManager
from apps.assistant.src.modules.conversation_principal import (
    ConversationPrincipalResolver,
    DenyingConversationPrincipalResolver,
)
from apps.assistant.src.modules.explicit_memory import ExplicitMemoryParser
from apps.assistant.src.modules.memory import MemoryManager
from apps.assistant.src.modules.memory_command import MemoryCommandService
from apps.assistant.src.modules.node_administration import NodeAdministration
from apps.assistant.src.modules.node_security import NodeGatewaySecurity, SystemClock
from apps.assistant.src.modules.policy import UnconfiguredPolicyBoundary
from apps.assistant.src.modules.orchestrator import ConversationOrchestrator
from apps.assistant.src.modules.privacy_gateway import DEFAULT_CLOUD_PRIVACY_POLICY, PrivacyGateway
from apps.assistant.src.modules.productivity_command import ProductivityCommandService
from apps.assistant.src.modules.todo import TodoManager
from apps.assistant.src.ports.node_administration import AdministratorAuthorizer
from apps.assistant.src.ports.conversation import ConversationRepository
from apps.assistant.src.ports.memory import MemoryRepository
from apps.assistant.src.ports.node_gateway import CredentialAuthenticator
from apps.assistant.src.ports.policy import PolicyBoundary
from apps.assistant.src.ports.llm import LLMPort
from apps.assistant.src.ports.todo import TodoRepository


DEFAULT_BIND_ADDRESS = "127.0.0.1"
DEFAULT_STATUS_PORT = 8080
DEFAULT_FOLLOW_UP_TIMEOUT = timedelta(seconds=45)
DEFAULT_LLM_TIMEOUT_SECONDS = 15.0
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class CoreComponents:
    """One-process composition of the initial Core logical boundaries."""

    node_gateway: NodeGatewaySecurity
    node_administration: NodeAdministration
    policy: PolicyBoundary
    conversation: ConversationManager
    privacy_gateway: PrivacyGateway
    orchestrator: ConversationOrchestrator
    behavior_preferences: BehaviorPreferenceManager
    preference_interpreter: BehaviorPreferenceInterpreter
    preference_service: BehaviorPreferenceService
    memory: MemoryManager
    memory_commands: MemoryCommandService
    memory_principals: ConversationPrincipalResolver
    todos: TodoManager
    productivity_commands: ProductivityCommandService
    registry: object
    credentials: object
    contracts: ContractCatalog
    transport_configured: bool
    administrator_authority_configured: bool
    policy_rules_configured: bool
    llm_configured: bool
    memory_principals_configured: bool
    storage_kind: str = "ephemeral"

    def liveness(self) -> dict[str, object]:
        return {"service": "hearthghost-core", "status": "alive"}

    def readiness(self) -> tuple[bool, dict[str, object]]:
        missing = []
        if not self.transport_configured:
            missing.append("node_transport_not_configured")
        if not self.administrator_authority_configured:
            missing.append("administrator_authority_not_configured")
        if not self.policy_rules_configured:
            missing.append("policy_rules_not_configured")
        if not self.llm_configured:
            missing.append("llm_adapter_not_configured")
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
            "storage": self.storage_kind,
            "contracts_loaded": self.contracts.count,
            "boundaries": {
                "node_gateway": "loaded",
                "node_administration": "loaded",
                "registry": "loaded",
                "contract_catalog": "loaded",
                "node_transport": "configured" if self.transport_configured else "deny_only",
                "administrator_authority": (
                    "configured" if self.administrator_authority_configured else "deny_only"
                ),
                "policy": "configured" if self.policy_rules_configured else "deny_only",
                "conversation": "text_only",
                "behavior_preferences": "internal_typed_boundary",
                "memory": "explicit_addressed_text_only",
                "productivity": "explicit_note_todo_only",
                "memory_principal": (
                    "configured" if self.memory_principals_configured else "deny_only"
                ),
                "privacy_gateway": "text_allow_media_deny",
                "llm": "configured" if self.llm_configured else "unavailable",
            },
            "readiness_reasons": readiness["reasons"],
        }


def build_core(
    *,
    contracts_root: Path | None = None,
    authenticator: CredentialAuthenticator | None = None,
    administrator_authorizer: AdministratorAuthorizer | None = None,
    policy: PolicyBoundary | None = None,
    node_registry: object | None = None,
    credential_repository: object | None = None,
    conversation_repository: ConversationRepository | None = None,
    memory_repository: MemoryRepository | None = None,
    todo_repository: TodoRepository | None = None,
    conversation_principal_resolver: ConversationPrincipalResolver | None = None,
    follow_up_timeout: timedelta = DEFAULT_FOLLOW_UP_TIMEOUT,
    llm: LLMPort | None = None,
    llm_timeout_seconds: float = DEFAULT_LLM_TIMEOUT_SECONDS,
    storage_kind: str = "ephemeral",
) -> CoreComponents:
    """Build Core with explicit deny-only substitutes for missing authorities."""

    clock = SystemClock()
    registry = node_registry if node_registry is not None else InMemoryNodeRegistry()
    credentials = (
        credential_repository if credential_repository is not None else InMemoryCredentialRepository()
    )
    sessions = InMemorySessionRepository()
    replay = InMemoryReplayProtector()
    selected_authenticator = (
        authenticator if authenticator is not None else RejectingCredentialAuthenticator()
    )
    selected_authorizer = (
        administrator_authorizer
        if administrator_authorizer is not None
        else DenyingAdministratorAuthorizer()
    )
    selected_policy = policy if policy is not None else UnconfiguredPolicyBoundary()
    selected_conversation_repository = (
        conversation_repository
        if conversation_repository is not None
        else InMemoryConversationRepository()
    )
    selected_memory_repository = (
        memory_repository if memory_repository is not None else InMemoryMemoryRepository()
    )
    selected_todo_repository = (
        todo_repository if todo_repository is not None else InMemoryTodoRepository()
    )
    selected_memory_principals = (
        conversation_principal_resolver
        if conversation_principal_resolver is not None
        else DenyingConversationPrincipalResolver()
    )
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
    conversation = ConversationManager(
        repository=selected_conversation_repository,
        clock=clock,
        follow_up_timeout=follow_up_timeout,
    )
    privacy_gateway = PrivacyGateway(
        llm=llm if llm is not None else UnavailableLLMAdapter(),
        policy=DEFAULT_CLOUD_PRIVACY_POLICY,
    )
    orchestrator = ConversationOrchestrator(
        conversation=conversation,
        privacy_gateway=privacy_gateway,
        llm_timeout_seconds=llm_timeout_seconds,
    )
    behavior_preferences = BehaviorPreferenceManager(
        conversation=conversation,
        orchestrator=orchestrator,
    )
    preference_interpreter = BehaviorPreferenceInterpreter(
        privacy_gateway=privacy_gateway,
        timeout_seconds=llm_timeout_seconds,
    )
    preference_service = BehaviorPreferenceService(
        interpreter=preference_interpreter,
        manager=behavior_preferences,
    )
    memory = MemoryManager(
        repository=selected_memory_repository,
        clock=clock,
    )
    memory_commands = MemoryCommandService(
        parser=ExplicitMemoryParser(),
        memory=memory,
        principals=selected_memory_principals,
    )
    todos = TodoManager(
        repository=selected_todo_repository,
        clock=clock,
    )
    productivity_commands = ProductivityCommandService(
        memory=memory,
        todos=todos,
        principals=selected_memory_principals,
    )
    return CoreComponents(
        node_gateway=gateway,
        node_administration=administration,
        policy=selected_policy,
        conversation=conversation,
        privacy_gateway=privacy_gateway,
        orchestrator=orchestrator,
        behavior_preferences=behavior_preferences,
        preference_interpreter=preference_interpreter,
        preference_service=preference_service,
        memory=memory,
        memory_commands=memory_commands,
        memory_principals=selected_memory_principals,
        todos=todos,
        productivity_commands=productivity_commands,
        registry=registry,
        credentials=credentials,
        contracts=ContractCatalog(contracts_root or REPOSITORY_ROOT / "contracts"),
        transport_configured=authenticator is not None,
        administrator_authority_configured=administrator_authorizer is not None,
        policy_rules_configured=policy is not None,
        llm_configured=llm is not None,
        memory_principals_configured=conversation_principal_resolver is not None,
        storage_kind=storage_kind,
    )


class CoreStatusServer(ThreadingHTTPServer):
    """Small loopback-only HTTP server for non-sensitive runtime status."""

    daemon_threads = True
    request_queue_size = 8
    allow_reuse_address = False

    def __init__(self, server_address: tuple[str, int], components: CoreComponents) -> None:
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
                self._send(HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE, body)
                return
            if path == "/status":
                self._send(HTTPStatus.OK, self.server.components.status())
                return
            self._send(HTTPStatus.NOT_FOUND, {"status": "not_found"})

        def do_POST(self) -> None:
            self._send(HTTPStatus.METHOD_NOT_ALLOWED, {"status": "method_not_allowed"})

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, status: HTTPStatus, body: dict[str, object]) -> None:
            payload = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
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
    server_factory: Callable[[tuple[str, int], CoreComponents], CoreStatusServer] = CoreStatusServer,
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
