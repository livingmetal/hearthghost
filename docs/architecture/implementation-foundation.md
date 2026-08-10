# Implementation Foundation

## Scope

HG-001 translates the documented architecture into tracked repository
boundaries. It provides versioned contracts, server/client ownership boundaries,
and test scaffolding. It does not implement the assistant, open a network
listener, select an AI provider, or deploy anything.

## Repository boundaries

```text
apps/assistant/src/
  modules/      domain ownership inside one modular monolith
  ports/        domain-facing interfaces
  adapters/     future provider/product translations

apps/web-client/src/
  README.md            shell, session, layout, and privacy boundaries
  character/README.md  renderer-neutral CharacterViewport boundary

contracts/
  events/v1/  policy/v1/  tools/v1/  node/v1/

tests/
  contracts/   executable schema-structure validation
  security/    explicitly unimplemented denial-case plan
```

## Contract format decision

Decision required: choose a language-neutral format for the first public
contracts.

Options considered:

1. JSON Schema Draft 2020-12: human-readable, transport-neutral, directly
   describes JSON payloads, and requires no application-language choice.
2. Protocol Buffers: strong code generation and compact binary transport, but
   would select tooling and push transport assumptions earlier.
3. OpenAPI: strong HTTP API description, but HG-001 intentionally does not
   select HTTP endpoints or introduce a listener.

Recommended and selected for the foundation: JSON Schema Draft 2020-12.

Tradeoff: JSON Schema does not itself provide generated transport clients or
runtime authorization. Application implementations must validate inputs and
preserve policy semantics. The decision is reversible before implementation,
but published contract changes still follow `contracts/VERSIONING.md`.

## Validation tooling decision

The foundation uses a small Python standard-library `unittest` suite to verify
JSON parsing, contract catalog completeness, version markers, regular-expression
syntax, and selected security constraints. This is development tooling only and
does not select Python for the assistant runtime. A full JSON Schema validator
can be added with the eventual project toolchain.

Alternatives were a shell-specific script or introducing a schema-validation
package now. Standard-library Python is portable across the target Linux host
and developer environments without adding a speculative dependency. This choice
is safely replaceable.

## Intentionally deferred technology decisions

- assistant implementation language and runtime framework
- client framework and Android packaging approach
- dependency/workspace/build system
- authenticated node transport and concrete certificate profile/PKI operations
- production authentication and user identity model
- database and persistence technology
- LLM, STT, TTS, vision, Home Assistant, and robot providers
- JSON event transport versus another authenticated channel
- binary media transport and reference lifecycle
- sprite runtime format, PNGAL export format, VRM library/version, and graphics stack
- deployment process/container layout and network enforcement technology

Each choice remains behind an established port, adapter, contract, or module
boundary and can be made by a later scoped task.

## Open architecture questions

- How will the proposed per-Node mTLS approach be provisioned and recovered on
  Android and embedded Nodes?
- Which persistent store will implement authoritative session-to-Node binding
  and atomic replay state?
- How are policy versions distributed to node-local camera/microphone gates?
- What binary media reference format provides bounded lifetime, integrity, and
  authorization without putting media in generic events?
- Which behavior-preference scopes and ranges need per-user versus household
  conflict resolution?
- What is the minimum runtime boundary needed to give Policy and Privacy Gateway
  meaningful isolation inside the initial single-host deployment?

These questions do not block the repository foundation and must not be answered
through temporary bypasses.
