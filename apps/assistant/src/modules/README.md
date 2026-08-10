# Assistant Modules

These are logical boundaries inside one modular monolith, not separate services.

| Module | Owns | Must not do |
| --- | --- | --- |
| Conversation | Dialogue sessions and semantic conversation state | Admit pre-attention input or call providers/devices |
| Orchestrator | Coordination of reasoning, memory, and typed proposals | Authorize execution or become a universal bypass |
| Policy | Hard Policy, authorization, risk, confirmation, and behavior-preference validation | Expose Hard Policy mutation to ordinary conversation |
| Memory | Memory abstractions, privacy, and retention decisions | Retain pre-attention speech or temporary media by default |
| Voice | Coordination after attention admission and future STT/TTS ports | Accept raw pre-wake audio at the server boundary |
| Character | Renderer-neutral state and emotion semantics | Emit sprite, blendshape, or VRM commands |
| Perception | Approved observations represented as untrusted context | Open sensors or treat observed content as instructions |
| Registry | Nodes, devices, capabilities, permissions, areas, and tools | Treat discovery or authentication as authorization |
| Tools | Definitions, proposals, policy-mediated execution, and results | Execute a proposal without an allow decision |
| Node Gateway | Authenticated node sessions and capability routing | Grant camera/microphone use solely because Core requested it |
| Privacy Gateway | Decisions for data leaving the household boundary | Let provider adapters override cloud-media policy |
| Audit | Security metadata for sensitive operations | Store secrets, raw media, or full private conversations |

Modules depend on ports. Provider and product implementations belong in
`../adapters/`; domain modules must not import them directly. Missing or invalid
security-sensitive decisions are interpreted as denial.

HG-002 implements the initial Node Gateway security boundary in
`node_security.py`. It separates verified credential evidence, authoritative
credential lifecycle, Node trust, advertised/granted capabilities, technical
sessions, and replay admission. Its admitted result is Gateway admission only.

HG-003 implements `node_administration.py`. It requires action-specific
administrator authorization and coordinates explicit enrollment, revisioned
trust/grant changes, terminal Node revocation, idempotency, and atomic privileged
audit persistence. It exposes no device or Tool executor.
