# Contracts

This directory owns shared, versioned HearthGhost domain contracts. The initial
contract format is JSON Schema Draft 2020-12 because it is language- and
transport-neutral and can be consumed by both server and client implementations.
It does not select a runtime language, web framework, or wire transport.

## Catalog

| Family | Schema | Purpose |
| --- | --- | --- |
| Events | `events/v1/conversation-state.schema.json` | Bounded conversation/session state |
| Events | `events/v1/character-state.schema.json` | Renderer-neutral character activity |
| Events | `events/v1/character-emotion.schema.json` | Emotion independent from activity state |
| Events | `events/v1/audit-event.schema.json` | Metadata-only security audit event |
| Tools | `tools/v1/tool-definition.schema.json` | Tool risk and execution requirements |
| Tools | `tools/v1/tool-proposal.schema.json` | Non-authoritative LLM/tool proposal |
| Policy | `policy/v1/policy-decision.schema.json` | Explicit allow/deny decision |
| Policy | `policy/v1/behavior-preference-update.schema.json` | Typed, non-Hard-Policy preference proposal |
| Node | `node/v1/node-identity.schema.json` | Preserved HG-001 identity/credential snapshot |
| Node | `node/v2/node-identity.schema.json` | Logical Node identity and trust, independent of credentials |
| Node | `node/v1/node-credential.schema.json` | Credential lifecycle and per-Node binding without secret material |
| Node | `node/v1/node-administration-command.schema.json` | Revisioned, idempotent privileged registry mutation |
| Node | `node/v1/node-administration-result.schema.json` | Mutation result without Policy or execution authority |
| Node | `node/v1/node-gateway-message.schema.json` | Framed technical-session and sequenced capability request |
| Node | `node/v1/node-gateway-result.schema.json` | Gateway result without Policy or execution authority |
| Node | `node/v1/node-capabilities.schema.json` | Preserved HG-001 capability/trust snapshot |
| Node | `node/v2/node-capabilities.schema.json` | Advertised and granted capabilities, independent of trust |

Every instance carries an explicit `contract_version`. The directory version
represents that contract's major family. Most foundation contracts remain at
`v1` / `1.0`; Node identity and capabilities v2 remove the v1 coupling among a
credential's status, the logical Node's trust state, and capability grants. The
immutable HG-001 Node identity and capability v1 schemas are retained for
traceability but must not be used by the HG-002 Node Gateway.
Unknown properties are rejected and consumers must explicitly support a
revision.

Node schemas are independently versioned, not one global Node protocol family.
For example, Node identity `v2.0` and Node credential `v1.0` are the current
contracts for different records; neither version number determines the other's
compatibility. See `VERSIONING.md`.

Contracts express HearthGhost semantics rather than vendor/provider payloads.
Binary audio, images, and video are intentionally absent; future media flows
must use dedicated binary transport or opaque references approved by policy.

Node Gateway message/result v1 is carried only after mutual TLS. Framing
success, transport authentication, or an `accepted` result never represents a
Policy Decision or device execution authority.

See `VERSIONING.md` and `../docs/architecture/contracts.md`.
