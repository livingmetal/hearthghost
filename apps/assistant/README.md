# Assistant Application

This directory contains the implementation boundary for the HearthGhost
server-side application runtime. HG-002 adds a dependency-free Python Node
Gateway security module; HG-003 adds the privileged Node enrollment and registry
administration boundary; HG-004 adds a standard-library TLS 1.3 adapter for
already-connected Node sockets; HG-005 composes the boundaries into a minimal
containerized Core with loopback-only status; HG-006 adds bounded Node Gateway
framing used by a test-only Mock Node. The domain ports do not select a web
framework, database, production PKI, network listener, or deployment stack.

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

The tracked module layout is documented under `src/`. Node network listeners
remain intentionally absent; the only HG-005 listener is read-only status on
literal loopback.

The OpenAI adapter remains opt-in. A synthetic provider smoke command lives in
`src/runtime/openai_smoke.py`; it uses the real Privacy Gateway and LLM Port,
accepts a server-only environment or secret-file credential, and is excluded
from normal tests. See `../../docs/architecture/llm-privacy.md` for the hardened
container invocation.

See:

- `../../AGENTS.md`
- `../../docs/architecture/overview.md`
- `../../docs/security/threat-model.md`
