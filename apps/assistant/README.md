# Assistant Application

This directory contains the implementation boundary for the HearthGhost
server-side application runtime. HG-002 adds a dependency-free Python Node
Gateway security module; HG-003 adds the privileged Node enrollment and registry
administration boundary; HG-004 adds a standard-library TLS 1.3 adapter for
already-connected Node sockets. The domain ports do not select a web framework,
database, production PKI, listener, application protocol, or deployment stack.

Expected logical responsibilities include:

- conversation
- orchestration
- policy
- memory
- registry
- tools
- perception
- node gateway coordination
- privacy/audit integration

The initial implementation should remain a modular monolith. Logical module boundaries do not imply one microservice per module.

External provider implementations belong behind adapters. Core/domain logic must not directly import LLM, STT/TTS, Home Assistant, vision, or robot vendor implementations.

Security-sensitive device actions must pass through policy and authorization before execution.

Node Gateway authentication and request admission are narrower checks. They do
not grant device execution or bypass a node-local sensor gate.

Node administration is also narrower than action authorization. Enrollment,
trust, and capability grants mutate registry state but never constitute a Policy
allow or Tool execution permission.

The tracked module layout is documented under `src/`. Empty runtime stubs and
network listeners remain intentionally absent.

See:

- `../../AGENTS.md`
- `../../docs/architecture/overview.md`
- `../../docs/security/threat-model.md`
