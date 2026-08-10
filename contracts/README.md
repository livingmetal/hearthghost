# Contracts

This directory owns shared, versioned HearthGhost domain contracts. The initial
contract format is JSON Schema Draft 2020-12 because it is language- and
transport-neutral and can be consumed by both server and client implementations.
It does not select a runtime language, web framework, or wire transport.

## Catalog

| Family | Version 1 schema | Purpose |
| --- | --- | --- |
| Events | `events/v1/conversation-state.schema.json` | Bounded conversation/session state |
| Events | `events/v1/character-state.schema.json` | Renderer-neutral character activity |
| Events | `events/v1/character-emotion.schema.json` | Emotion independent from activity state |
| Events | `events/v1/audit-event.schema.json` | Metadata-only security audit event |
| Tools | `tools/v1/tool-definition.schema.json` | Tool risk and execution requirements |
| Tools | `tools/v1/tool-proposal.schema.json` | Non-authoritative LLM/tool proposal |
| Policy | `policy/v1/policy-decision.schema.json` | Explicit allow/deny decision |
| Policy | `policy/v1/behavior-preference-update.schema.json` | Typed, non-Hard-Policy preference proposal |
| Node | `node/v1/node-identity.schema.json` | Node identity and independently revocable status |
| Node | `node/v1/node-capabilities.schema.json` | Advertised capabilities and granted permissions |

Every instance carries `contract_version: "1.0"`. Directory version `v1`
represents the contract major family. Minor revisions are published alongside
the immutable 1.0 shape; breaking changes require a new major directory. Unknown
properties are rejected and consumers must explicitly support a revision.

Contracts express HearthGhost semantics rather than vendor/provider payloads.
Binary audio, images, and video are intentionally absent; future media flows
must use dedicated binary transport or opaque references approved by policy.

See `VERSIONING.md` and `../docs/architecture/contracts.md`.
