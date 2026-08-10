# ADR-0003: Minimal containerized Core runtime

## Status

Accepted

## Context

HG-005 needs one running process that composes the existing Node Gateway, Node
administration, Policy, Registry, and contract boundaries. It must provide
useful process health without pretending that unconfigured security authorities
are ready or exposing an unfinished Core service to the host or LAN.

The repository still has no production credential resolver, administrator
identity provider, Policy rule engine, persistent datastore, Node application
protocol, or production PKI. Creating permissive stand-ins for those components
would violate the fail-closed architecture.

## Decision

Run the initial Core as one Python 3.13 modular-monolith process in a dedicated
non-root container image stage.

The composition root loads:

- the Node Gateway security boundary;
- the Node administration boundary;
- an ephemeral Node Registry and atomic administration/audit store;
- ephemeral credential, technical-session, and replay stores;
- a read-only catalog of all versioned JSON Schema contracts;
- a Policy boundary.

Missing authorities receive explicit deny-only implementations:

- no Node transport authenticator -> every credential presentation is denied;
- no administrator authorizer -> every administration request is denied;
- no Policy rules -> every proposal receives `policy_not_configured` denial.

The Core exposes only read-only status endpoints on literal loopback:

```text
GET /health/live   -> process and composition are alive
GET /health/ready  -> 503 until all security authorities are configured
GET /status        -> non-sensitive subsystem state
```

The server rejects non-loopback bind addresses in code. The Compose service also
uses `network_mode: none`, publishes no ports, exposes no ports, mounts no
volumes, drops all capabilities, uses a read-only root filesystem, and runs as
UID/GID 10001. The liveness endpoint is used for the container health probe;
readiness remains a separate security/configuration signal.

The contract catalog validates that every tracked schema can be parsed, has a
unique `$id`, and has a fixed `contract_version`. It is routing metadata, not a
partial JSON Schema validator, and cannot authorize dispatch into a privileged
boundary.

## Consequences

Positive:

- the Core is executable and reproducible without inventing microservices;
- existing security boundaries share one explicit composition root;
- unconfigured identity and Policy dependencies fail closed and are visible in
  readiness;
- status cannot be accidentally bound to `0.0.0.0`;
- the runtime image contains only `apps/` and `contracts/`, not tests or the
  whole repository;
- no dependency, database, secret, persistent volume, or external network is
  added.

Costs and constraints:

- all registry, credential, session, replay, and audit state is volatile;
- the Core is intentionally not ready for Node traffic;
- the status listener is useful only from inside the container/network
  namespace;
- process health does not prove Policy or external dependency correctness.

## Alternatives considered

### One service per logical boundary

Rejected. It would add network trust, deployment, and failure complexity without
a current isolation requirement. The modular monolith preserves port boundaries
inside one process.

### Host-published health endpoint

Rejected for HG-005. Container-native health probing works over its own
loopback, so publishing a host/LAN port adds no necessary capability.

### Mark deny-only Core as ready

Rejected. Liveness and readiness answer different questions. A process can be
alive while it is unable to authenticate Nodes, authorize administrators, or
evaluate an allow decision.

### Add a database or schema-validation dependency

Deferred. No persistence requirements or migration lifecycle have been approved,
and full Draft 2020-12 validation should use a reviewed implementation rather
than a partial home-grown validator.

## Security / Privacy impact

The runtime accepts no Node or administration traffic over a network. Its only
listener is loopback-only and read-only, and status omits contract identifiers,
Node identifiers, credentials, audit content, filesystem paths, and secrets.
No camera, microphone, cloud, Home Assistant, Tool execution, or physical-device
path is present.

Ephemeral state is not a production durability claim. A restart invalidates all
technical sessions and replay state, which is fail closed. Production use must
not begin until persistent security state and restart behavior are reviewed.

## Deferred decisions

- secure Node listener and application framing;
- persistent registry, credential, audit, session, and replay stores;
- administrator identity provider and management interface;
- actual Policy rules and confirmation state;
- full JSON Schema validation and dispatch;
- production deployment, secrets, PKI, networking, and observability.
