# Character Boundary

`CharacterViewport` hosts a `CharacterRenderer` implementation selected at the
composition boundary. Renderers consume semantic character state, emotion, and
future speech timing. They do not interpret policy or perform device actions.

Conversation state and emotion are separate inputs. Renderer-specific branching
must not escape this boundary.

`DomCharacterRenderer` is the dependency-free 2D/test fallback.
`VrmCharacterRenderer` contains all Three.js and `@pixiv/three-vrm` knowledge.
The app can lazy-load that module when an approved VRM asset is configured; no
model or generated character asset is committed by HG-008. PixiJS remains
deferred until a real 2D asset pipeline demonstrates a need.

Invalid, combined, or renderer-specific events fail at the viewport boundary.
No renderer receives Node credentials, trust administration, Privacy Gateway
state, Tool proposals, or provider configuration.
