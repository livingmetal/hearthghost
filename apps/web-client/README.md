# Web / Mobile Client

This directory contains the implementation boundary for the first HearthGhost
client experience on Android phones and tablets. ADR-0005 selects a
TypeScript/Vite web surface with a future Capacitor Android shell.

The client is a presentation and I/O endpoint, not the AI brain.

Expected responsibilities:

- responsive portrait / landscape shell
- renderer-neutral `CharacterViewport`
- 2D sprite renderer support
- VRM renderer support
- conversation state presentation
- future audio capture/playback behind separately reviewed platform ports
- touch-to-wake fallback
- visible privacy/security indicators
- authenticated transport to the Node Gateway

The application shell must not depend directly on a specific renderer technology. Renderer-specific code must remain behind a CharacterRenderer abstraction.

The main screen should remain character-first and must not become a full Home Assistant dashboard.

The tracked boundaries under `src/` preserve one application shell, one semantic
session model, and one `CharacterViewport` abstraction across portrait and
landscape modes. The Node platform port exposes only an opaque credential
reference and authenticated public session metadata. The browser adapter fails
clearly because it cannot own the reviewed native mTLS/Keystore boundary; it
does not silently substitute plaintext. Tests use an explicitly constructed
fake adapter.

No camera or microphone permission is requested. No private Node key, LLM
provider credential, or Home Assistant credential belongs in this package.

See:

- `../../docs/architecture/character-presentation.md`
- `../../docs/product/mobile-ux.md`
- `../../docs/architecture/voice-attention.md`
- `../../docs/security/privacy-model.md`
