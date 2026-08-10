# Ports

Ports define stable interfaces the domain needs from storage, external AI,
speech, node transport, devices, clocks, and audit sinks. Ports use HearthGhost
contracts and domain types, never provider response objects.

Security-sensitive ports must make authorization context explicit and must not
offer convenience methods that bypass Policy or Privacy Gateway evaluation.

`node_gateway.py` defines the HG-002 ports for credential authentication,
credential and Node repositories, technical session storage, atomic replay
tracking, trusted time, and the inbound Node Gateway security boundary. It
deliberately defines no HTTP, WebSocket, gRPC, MQTT, QUIC, TLS, certificate, or
persistence implementation.

`node_administration.py` defines the HG-003 ports for action-specific
administrator authorization, advertised-capability lookup, and an atomic
revision/idempotency/state/audit store. It deliberately selects no identity
provider, database, message broker, or audit backend.
