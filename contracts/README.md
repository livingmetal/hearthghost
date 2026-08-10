# Contracts

This directory will contain shared, versionable HearthGhost schemas and protocol definitions.

Expected contract categories:

- node identity and registration
- node capabilities
- conversation state
- character state and emotion
- speech events
- tool definitions and proposals
- policy decisions
- behavior-preference updates
- device state
- audit events

Contracts should represent HearthGhost domain semantics rather than vendor/provider payloads.

Breaking contract changes require coordinated schema, test, and documentation updates.

See `../docs/architecture/contracts.md`.
