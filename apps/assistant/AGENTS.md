# Assistant AGENTS.md

These rules apply to work under `apps/assistant/` and supplement the repository root `AGENTS.md`.

## Module boundaries

Keep the initial server a modular monolith with explicit logical boundaries.

Expected domains include:

- conversation
- orchestration
- policy
- memory
- voice coordination
- registry
- tools
- perception
- audit
- adapters

Do not turn every logical module into a network service.

## LLM boundary

The LLM may interpret, reason, converse, plan, and propose typed tool or preference changes.

It must not directly:

- call Home Assistant
- access cameras or microphones
- operate robots
- modify Hard Policy
- access arbitrary secrets
- execute unrestricted shell commands

Physical or external actions follow:

```text
LLM proposal
 -> policy evaluation
 -> authorization / risk check
 -> executor
 -> adapter
 -> target
```

## Registry and capability model

Do not hard-code individual IoT brands or future robots into conversation logic.

Keep distinct concepts for:

- Device Registry
- Capability Registry
- Tool Registry
- Policy Engine

A new device should usually extend the system through an adapter and capability mapping.

## Behavior preferences

Values such as humor, verbosity, initiative, proactive frequency, and conversation timeout must be represented through policy/preference interfaces rather than scattered constants.

The LLM may propose typed preference updates. It must never directly rewrite runtime configuration files.

## Security-sensitive media

Camera, microphone, and household-media flows require explicit privacy and policy handling. Do not add an implementation shortcut that bypasses the Privacy Gateway or node-local security gate.

## Provider adapters

Keep provider-specific LLM, STT, TTS, Home Assistant, vision, and robot logic behind ports/adapters.

Do not leak provider response objects into stable domain contracts.

Read before relevant work:

- `../../docs/architecture/overview.md`
- `../../docs/architecture/contracts.md`
- `../../docs/security/threat-model.md`
- `../../docs/security/trust-boundaries.md`
- `../../docs/security/privacy-model.md`
