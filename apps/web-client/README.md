# Web / Mobile Client

This directory contains the implementation boundary for the first HearthGhost
client experience on Android phones and tablets through a future web-capable
frontend or equivalent mobile shell. HG-001 does not choose that client stack.

The client is a presentation and I/O endpoint, not the AI brain.

Expected responsibilities:

- responsive portrait / landscape shell
- renderer-neutral `CharacterViewport`
- 2D sprite renderer support
- VRM renderer support
- conversation state presentation
- audio capture/playback
- touch-to-wake fallback
- visible privacy/security indicators
- authenticated transport to the Node Gateway

The application shell must not depend directly on a specific renderer technology. Renderer-specific code must remain behind a CharacterRenderer abstraction.

The main screen should remain character-first and must not become a full Home Assistant dashboard.

The tracked boundaries under `src/` preserve one application shell, one semantic
session model, and one `CharacterViewport` abstraction across portrait and
landscape modes. Renderer implementations remain deferred.

See:

- `../../docs/architecture/character-presentation.md`
- `../../docs/product/mobile-ux.md`
- `../../docs/architecture/voice-attention.md`
- `../../docs/security/privacy-model.md`
