# HearthGhost Documentation

This directory is the design record for HearthGhost. The root `README.md` states the project mission and security-first product requirements. `AGENTS.md` contains mandatory implementation rules for coding agents. The documents here explain the architecture, security model, user experience, and development roadmap in more detail.

## Documentation map

```text
docs/
├─ README.md
├─ roadmap.md
├─ architecture/
│  ├─ overview.md
│  ├─ character-presentation.md
│  ├─ node-architecture.md
│  ├─ voice-attention.md
│  └─ contracts.md
├─ security/
│  ├─ threat-model.md
│  ├─ trust-boundaries.md
│  └─ privacy-model.md
├─ product/
│  ├─ interaction-principles.md
│  └─ mobile-ux.md
└─ adr/
   └─ README.md
```

## Reading order

For a new contributor or coding agent:

1. Read `/README.md` for the product mission and security posture.
2. Read `/AGENTS.md` for mandatory implementation constraints.
3. Read `architecture/overview.md` for system boundaries and dependency direction.
4. Read the relevant architecture document for the task being changed.
5. For camera, microphone, memory, networking, cloud, device-control, or robot work, also read the relevant documents under `security/`.
6. For user-facing behavior, read the documents under `product/`.
7. Record decisions that intentionally change architecture or trust boundaries under `adr/`.

For Node authentication, credential rotation/revocation, technical sessions, or
replay behavior, read `security/node-identity-and-replay.md` and
`adr/0001-per-node-mutual-authentication.md`.

For Node enrollment, trust administration, capability grants, registry
revisions, idempotency, or privileged audit, read
`security/node-administration.md`.

`architecture/implementation-foundation.md` records the reversible HG-001
foundation choices and the technology decisions deliberately left open.

## Documentation rule

Do not duplicate the entire specification across multiple files. Put durable implementation invariants in `AGENTS.md`; put rationale and system design here; put individual irreversible or high-impact decisions in ADRs.
