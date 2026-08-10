# Assistant Application

This directory will contain the HearthGhost server-side application runtime.

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

See:

- `../../AGENTS.md`
- `../../docs/architecture/overview.md`
- `../../docs/security/threat-model.md`
