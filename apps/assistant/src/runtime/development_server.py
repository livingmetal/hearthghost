"""Rootless development Core with one narrowly bound mTLS Node listener."""

from __future__ import annotations

import argparse
import ipaddress
import signal
import socket
import ssl
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from apps.assistant.src.adapters.conversation_protocol import ConversationProtocol
from apps.assistant.src.adapters.development_state import (
    DevelopmentStateFile,
    LocalDevelopmentAdministratorAuthorizer,
    PersistentCertificateIdentityResolver,
    PersistentCredentialRepository,
    PersistentNodeRegistry,
)
from apps.assistant.src.adapters.fake_llm import FakeLLMAdapter
from apps.assistant.src.adapters.node_gateway_protocol import NodeGatewayProtocol, NodeProtocolError, read_frame
from apps.assistant.src.adapters.node_tls_transport import MutualTlsCredentialAuthenticator, MutualTlsServerAdapter, create_node_server_context
from apps.assistant.src.adapters.postgres_behavior_preferences import PostgresBehaviorPreferenceRepository
from apps.assistant.src.adapters.postgres_memory import PostgresMemoryRepository
from apps.assistant.src.adapters.postgres_reminder import PostgresReminderRepository
from apps.assistant.src.adapters.postgres_todo import PostgresTodoRepository
from apps.assistant.src.adapters.reminder_sync_protocol import ReminderSyncProtocol
from apps.assistant.src.modules.node_security import SystemClock
from apps.assistant.src.modules.policy import UnconfiguredPolicyBoundary
from apps.assistant.src.runtime.admin_dashboard import AdminDashboardServer
from apps.assistant.src.runtime.core import CoreStatusServer, build_core
from apps.assistant.src.runtime.memory_configuration import parse_memory_principal_bindings
from apps.assistant.src.runtime.notification_configuration import parse_notification_target_bindings
from apps.assistant.src.runtime.postgres_configuration import DEFAULT_POSTGRES_DSN_FILE, read_postgres_dsn

DEFAULT_GATEWAY_BIND = "10.89.0.10"
DEFAULT_GATEWAY_PORT = 8443
DEFAULT_STATUS_BIND = "127.0.0.1"
DEFAULT_STATUS_PORT = 8080
DEFAULT_ADMIN_DASHBOARD_BIND = "127.0.0.1"
DEFAULT_SOCKET_TIMEOUT_SECONDS = 60.0
DEFAULT_HANDSHAKE_TIMEOUT_SECONDS = 5.0
MAX_CONNECTIONS = 8


class DevelopmentGatewayServer:
    def __init__(
        self,
        *,
        bind_address: str,
        port: int,
        tls: MutualTlsServerAdapter,
        node_protocol: NodeGatewayProtocol,
        conversation_protocol: ConversationProtocol,
        reminder_sync_protocol: ReminderSyncProtocol | None = None,
        socket_timeout_seconds: float = DEFAULT_SOCKET_TIMEOUT_SECONDS,
    ) -> None:
        parsed = ipaddress.ip_address(bind_address)
        if parsed.is_unspecified or parsed.is_loopback or parsed.is_multicast:
            raise ValueError("Gateway requires one explicit non-loopback address")
        if not 1 <= port <= 65535:
            raise ValueError("Gateway port must be between 1 and 65535")
        if not 1 <= socket_timeout_seconds <= 300:
            raise ValueError("Gateway socket timeout must be between 1 and 300 seconds")
        self._address = (str(parsed), port)
        self._tls = tls
        self._node_protocol = node_protocol
        self._conversation_protocol = conversation_protocol
        self._reminder_sync_protocol = reminder_sync_protocol
        self._socket_timeout = socket_timeout_seconds
        self._stopping = threading.Event()
        self._listener: socket.socket | None = None
        self._connection_slots = threading.BoundedSemaphore(MAX_CONNECTIONS)

    def serve_forever(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            listener.bind(self._address)
            listener.listen(MAX_CONNECTIONS)
            listener.settimeout(0.5)
            self._listener = listener
            with ThreadPoolExecutor(max_workers=MAX_CONNECTIONS, thread_name_prefix="node-connection") as executor:
                while not self._stopping.is_set():
                    try:
                        connected, _ = listener.accept()
                    except TimeoutError:
                        continue
                    if not self._connection_slots.acquire(blocking=False):
                        connected.close()
                        continue
                    connected.settimeout(DEFAULT_HANDSHAKE_TIMEOUT_SECONDS)
                    executor.submit(self._handle_and_release, connected)
            self._listener = None

    def shutdown(self) -> None:
        self._stopping.set()

    def _handle_and_release(self, connected: socket.socket) -> None:
        try:
            self._handle_connection(connected)
        finally:
            self._connection_slots.release()

    def _handle_connection(self, connected: socket.socket) -> None:
        channel: ssl.SSLSocket | None = None
        open_session_id: str | None = None
        try:
            channel = self._tls.wrap_connected_socket(connected)
            channel.settimeout(self._socket_timeout)
            while not self._stopping.is_set():
                document = read_frame(channel)
                if not isinstance(document, dict):
                    raise NodeProtocolError("Node command must be an object")
                message_type = document.get("message_type")
                if message_type in {"session.open", "capability.request", "session.close"}:
                    if message_type == "session.open" and open_session_id is not None:
                        raise NodeProtocolError("connection already has a Node session")
                    result = self._node_protocol.handle_document(channel, document)
                    if message_type == "session.open" and result.accepted:
                        open_session_id = result.session_id
                    elif message_type == "session.close" and result.accepted:
                        open_session_id = None
                        return
                elif message_type in {"conversation.open", "conversation.text", "conversation.close"}:
                    self._conversation_protocol.handle_document(channel, document)
                elif message_type == "reminder.sync":
                    if self._reminder_sync_protocol is None:
                        raise NodeProtocolError("reminder sync is not configured")
                    self._reminder_sync_protocol.handle_document(channel, document)
                else:
                    raise NodeProtocolError("unsupported Node command type")
        except (OSError, ssl.SSLError, NodeProtocolError, ValueError):
            pass
        finally:
            if channel is not None and open_session_id is not None:
                try:
                    self._node_protocol.close_bound_session(channel, open_session_id)
                except Exception:
                    pass
            try:
                (channel if channel is not None else connected).close()
            except OSError:
                pass


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the development mTLS Gateway")
    parser.add_argument("--state", required=True)
    parser.add_argument("--certificate", required=True)
    parser.add_argument("--private-key", required=True)
    parser.add_argument("--client-ca", required=True)
    parser.add_argument("--bind", default=DEFAULT_GATEWAY_BIND)
    parser.add_argument("--port", type=int, default=DEFAULT_GATEWAY_PORT)
    parser.add_argument("--status-bind", default=DEFAULT_STATUS_BIND)
    parser.add_argument("--status-port", type=int, default=DEFAULT_STATUS_PORT)
    parser.add_argument(
        "--admin-dashboard-port",
        type=int,
        default=None,
        metavar="PORT",
        help="enable the read-only operator dashboard on 127.0.0.1 only; disabled by default",
    )
    parser.add_argument("--postgres-dsn-secret", default=None, metavar="PATH", help=f"PostgreSQL DSN secret file; production default is {DEFAULT_POSTGRES_DSN_FILE}")
    parser.add_argument("--memory-principal", action="append", default=[], metavar="NODE_ID=SCOPE:SCOPE_ID")
    parser.add_argument(
        "--notification-target",
        action="append",
        default=[],
        metavar="SCOPE:SCOPE_ID=NODE_ID",
        help="explicit principal-to-notification-Node route; no creator-origin inference",
    )
    options = parser.parse_args(arguments)
    if options.admin_dashboard_port is not None and not 1 <= options.admin_dashboard_port <= 65535:
        parser.error("--admin-dashboard-port must be between 1 and 65535")
    if (
        options.admin_dashboard_port is not None
        and options.status_bind == DEFAULT_ADMIN_DASHBOARD_BIND
        and options.admin_dashboard_port == options.status_port
    ):
        parser.error("--admin-dashboard-port must differ from --status-port on 127.0.0.1")

    state = DevelopmentStateFile(Path(options.state))
    registry = PersistentNodeRegistry(state)
    credentials = PersistentCredentialRepository(state)
    server_context = create_node_server_context(certificate_file=options.certificate, private_key_file=options.private_key, client_ca_file=options.client_ca)
    authenticator = MutualTlsCredentialAuthenticator(server_context=server_context, identities=PersistentCertificateIdentityResolver(state))

    behavior_preference_repository = None
    memory_repository = None
    todo_repository = None
    reminder_repository = None
    storage_kind = "persistent_development_file"
    if options.postgres_dsn_secret:
        dsn = read_postgres_dsn(options.postgres_dsn_secret)
        behavior_preference_repository = PostgresBehaviorPreferenceRepository(dsn)
        memory_repository = PostgresMemoryRepository(dsn)
        todo_repository = PostgresTodoRepository(dsn)
        reminder_repository = PostgresReminderRepository(dsn)
        storage_kind = "persistent_postgresql"
    memory_principals = parse_memory_principal_bindings(options.memory_principal) if options.memory_principal else None
    notification_targets = parse_notification_target_bindings(options.notification_target) if options.notification_target else None

    unreachable_admin_context = object()
    components = build_core(
        authenticator=authenticator,
        administrator_authorizer=LocalDevelopmentAdministratorAuthorizer(unreachable_admin_context, "local-development-cli"),
        policy=UnconfiguredPolicyBoundary(),
        node_registry=registry,
        credential_repository=credentials,
        behavior_preference_repository=behavior_preference_repository,
        memory_repository=memory_repository,
        todo_repository=todo_repository,
        reminder_repository=reminder_repository,
        notification_target_resolver=notification_targets,
        conversation_principal_resolver=memory_principals,
        llm=FakeLLMAdapter(),
        storage_kind=storage_kind,
    )
    node_protocol = NodeGatewayProtocol(components.node_gateway)
    conversation_protocol = ConversationProtocol(
        gateway=components.node_gateway,
        conversation=components.conversation,
        orchestrator=components.orchestrator,
        memory_commands=components.memory_commands,
        reminder_commands=components.reminder_commands,
        productivity_commands=components.productivity_commands,
        preference_commands=components.preference_commands,
        behavior_preferences=components.behavior_preferences,
        conversation_principals=components.memory_principals,
    )
    reminder_sync_protocol = ReminderSyncProtocol(
        gateway=components.node_gateway,
        reminders=components.reminders,
        principals=components.memory_principals,
        targets=components.notification_targets,
        clock=SystemClock(),
    )
    gateway_server = DevelopmentGatewayServer(
        bind_address=options.bind,
        port=options.port,
        tls=MutualTlsServerAdapter(server_context),
        node_protocol=node_protocol,
        conversation_protocol=conversation_protocol,
        reminder_sync_protocol=reminder_sync_protocol,
    )
    status_server = CoreStatusServer((options.status_bind, options.status_port), components)
    dashboard_server: AdminDashboardServer | None = None
    try:
        if options.admin_dashboard_port is not None:
            dashboard_server = AdminDashboardServer((DEFAULT_ADMIN_DASHBOARD_BIND, options.admin_dashboard_port), components)
    except Exception:
        status_server.server_close()
        raise

    status_thread = threading.Thread(target=status_server.serve_forever, kwargs={"poll_interval": 0.25}, name="loopback-status", daemon=True)
    status_thread.start()
    dashboard_thread: threading.Thread | None = None
    if dashboard_server is not None:
        dashboard_thread = threading.Thread(
            target=dashboard_server.serve_forever,
            kwargs={"poll_interval": 0.5},
            name="loopback-admin-dashboard",
            daemon=True,
        )
        dashboard_thread.start()

    prior_handlers: dict[int, object] = {}

    def stop(signum: int, frame: object) -> None:
        gateway_server.shutdown()

    for signum in (signal.SIGINT, signal.SIGTERM):
        prior_handlers[signum] = signal.signal(signum, stop)
    try:
        gateway_server.serve_forever()
    finally:
        status_server.shutdown()
        status_server.server_close()
        status_thread.join(timeout=2)
        if dashboard_server is not None:
            dashboard_server.shutdown()
            dashboard_server.server_close()
        if dashboard_thread is not None:
            dashboard_thread.join(timeout=2)
        for signum, handler in prior_handlers.items():
            signal.signal(signum, handler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
