# Web Client AGENTS.md

These rules apply to work under `apps/web-client/` and supplement the repository root `AGENTS.md`.

## Character presentation invariants

1. The application shell must be renderer-agnostic.
2. Character rendering must occur through a `CharacterViewport` and a common renderer abstraction.
3. Renderer-specific implementation must remain inside its renderer module/adapter.
4. The architecture must permit at least:
   - 2D sprite/animation renderers, including PNGAL-produced assets
   - VRM 3D renderers
   - future renderer types without redesigning conversation/core logic
5. Do not scatter `if (vrm)` / `if (sprite)` branches throughout unrelated UI code.
6. Conversation state and character emotion are separate concepts.
7. Server/domain events should be semantic (`speaking`, `thinking`, `amused`) rather than renderer-specific animation commands.

## Mobile UX invariants

1. Portrait and landscape are both supported product layouts.
2. Portrait is character-first and optimized for handheld conversation.
3. Landscape supports docked use with character plus selected context.
4. Both layouts use the same CharacterViewport and semantic event model.
5. UI controls should stay near edges where practical and avoid covering the avatar's important visual area.
6. Do not assume a fixed avatar silhouette, body framing, or 2D/3D geometry.
7. Touch-to-wake remains available as a fallback to voice activation.
8. The primary screen must not become a full Home Assistant dashboard.

## Privacy UI invariants

Security-sensitive state must be understandable from the client UI.

Do not hide all of these only in deep settings:

- camera active / denied state
- microphone local-only / active session state
- cloud media policy state when relevant
- node trust/authentication state when relevant

Visual animation alone is not sufficient to communicate a security state.

## Client trust boundary

The client must not make itself an execution authority.

- no direct Home Assistant credentials
- no direct LLM provider secrets in browser/client code
- no bypass of node-local camera/microphone policy
- no assumption that server authentication alone authorizes camera use

Read before major UI work:

- `../../docs/product/mobile-ux.md`
- `../../docs/architecture/character-presentation.md`
- `../../docs/architecture/voice-attention.md`
- `../../docs/security/privacy-model.md`
