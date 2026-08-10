# Web / Mobile Client

This directory will contain the first HearthGhost client experience for Android phones and tablets through a web-capable frontend or equivalent mobile shell.

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

See:

- `../../docs/architecture/character-presentation.md`
- `../../docs/product/mobile-ux.md`
- `../../docs/architecture/voice-attention.md`
- `../../docs/security/privacy-model.md`
