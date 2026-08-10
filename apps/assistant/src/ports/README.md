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

`node_transport.py` defines the HG-004 mapping from a TLS-verified public Node
certificate to credential identity evidence. Certificate verification remains
in the adapter; lifecycle, revocation, trust, and capability authority remain
in the Node Gateway and registry boundaries.

`policy.py` defines the proposal-evaluation boundary used by the Core. Missing or
malformed Policy results must never be interpreted as allow; the HG-005 default
implementation explicitly denies every proposal until rules are configured.

`conversation.py` stores bounded text conversation state separately from Node
technical sessions. Repository or trusted-time failure rejects the transition;
it never ends or mutates a Node identity/session as a side effect.

`llm.py` defines provider-neutral text input, completion, failure, and inert
proposal types. It offers generation only and deliberately has no credential,
filesystem, Policy mutation, Tool execution, or device API.
