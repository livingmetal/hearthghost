# Tests

This directory contains cross-module contract validation and the structure for
future integration, security-boundary, and end-to-end tests that do not naturally
belong beside a single module.

Security-sensitive functionality must test denial paths as well as success paths.

Important examples include:

```text
unauthorized camera request -> denied
revoked node credential -> denied
unknown device -> denied
LLM Hard Policy change request -> denied
critical tool without confirmation -> denied
cloud image upload under default policy -> denied
policy service unavailable -> sensitive action denied
```

The test suite must not use real household secrets, private media, addresses, access tokens, or production credentials.

Secure-transport integration tests generate short-lived, test-only certificates
inside an operating-system temporary directory. The fixtures are removed after
the tests and do not establish production certificate authority policy.

When a task changes a trust boundary, contract, or security policy, tests should demonstrate that the intended negative cases remain closed.

## Reproducible validation

The preferred CI-style path builds the repository test image and runs the suite
without network access or persistent state:

```text
docker compose build --pull test
docker compose run --rm test
```

The container command must return non-zero when any test fails. The image is a
development validation tool and does not decide the future Assistant or Web
Client runtime.

## Host validation

Run the dependency-free foundation suite from the repository root:

```text
python -m unittest discover -s tests -p "test_*.py"
```

`contracts/` verifies the structure and selected security invariants of the JSON
Schemas. `security/` records required denial cases and links `implemented`
entries to executable boundary tests. Deferred cases remain
`not_implemented`; planning entries never substitute for application behavior.
Each implementation task must promote only the cases it proves through the
public boundary.

`infrastructure/` verifies the dependency-free container development baseline,
including non-root execution, disabled networking, dropped capabilities,
read-only filesystems, and restricted build context.

`runtime/` verifies the Core composition, deny-only defaults, atomic ephemeral
registry adapter, contract catalog, loopback-only status listener, and separate
liveness/readiness semantics.

`integration/` runs the test-only Mock Node through ephemeral mutual TLS,
versioned framing, administration, technical session, replay, capability/trust
revocation, credential revocation, and reconnect behavior. It uses no real
credentials, media, listener, or physical capability.

See `../AGENTS.md` and `../docs/security/threat-model.md`.
