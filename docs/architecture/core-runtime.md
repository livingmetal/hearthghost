# Minimal Core Runtime

HG-005 turns the existing logical boundaries into one executable modular
monolith. It is a composition milestone, not a production deployment.

```text
Core process
  |-- Contract Catalog (read-only metadata)
  |-- Node Gateway
  |     |-- deny-only credential authenticator
  |     |-- ephemeral credential/session/replay stores
  |     `-- Node Registry read model
  |-- Node Administration
  |     |-- deny-only administrator authorizer
  |     `-- atomic ephemeral registry/audit store
  |-- Policy
  |     `-- deny-only until rules are configured
  `-- loopback status API
```

## Runtime states

Liveness means the process has loaded its boundaries and contract catalog.
Readiness additionally requires a configured Node transport authenticator,
administrator authority provider, and Policy implementation.

The default HG-005 composition therefore reports:

```text
liveness = alive
readiness = not_ready
overall status = degraded
```

This is expected. Missing security infrastructure is never converted into an
allow result merely to make a health indicator green.

## Container usage

Build and start the internal-only Core:

```text
docker compose --profile runtime up --build -d core
docker compose --profile runtime exec core \
  python -m apps.assistant.src.runtime.healthcheck
docker compose --profile runtime down
```

Inspect composition without starting a listener:

```text
docker compose --profile runtime run --rm core \
  python -m apps.assistant.src.runtime.core --check
```

The Compose Core uses no network, ports, volumes, devices, secrets, or Linux
capabilities. Its root filesystem is read-only and normal execution is non-root.

## Registry and contract boundaries

The in-memory registry implements the same atomic revision/idempotency/state/audit
port used by Node administration and presents a separate Gateway read model.
Capability advertisements remain separate from grants. The default authorizer
denies administration, so registry state cannot change through the runtime
until a real authorized administration path is supplied.

The contract catalog proves that schemas are loadable, uniquely identified, and
versioned. It deliberately does not claim full JSON Schema validation and must
not be treated as sufficient input validation for a security-sensitive handler.

## Not production-ready

Restarting loses all state and invalidates sessions. No Node listener, user
administration endpoint, Tool executor, database, production certificate, or
Policy allow path exists. HG-006 adds only bounded connected-socket framing and
a test-only Mock Node. These omissions remain visible through readiness rather
than hidden behind demo defaults.
