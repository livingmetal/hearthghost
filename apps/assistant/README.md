# Assistant Application

This directory contains the implementation boundary for the HearthGhost
server-side application runtime. HG-002 adds a dependency-free Python Node
Gateway security module and technology-neutral ports. It does not select a web
framework, network transport, database, PKI implementation, or deployment stack.

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

The tracked module layout is documented under `src/`. Empty runtime stubs and
network listeners are intentionally absent until an implementation technology is
chosen.

See:

- `../../AGENTS.md`
- `../../docs/architecture/overview.md`
- `../../docs/security/threat-model.md`
