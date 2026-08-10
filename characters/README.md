# Characters

This directory will contain character definitions and renderer-specific assets without mixing them into the HearthGhost Core.

A character should conceptually separate:

```text
Persona
Voice
Appearance / Renderer
Memory namespace or identity reference
```

Possible renderer assets include:

- 2D sprite / animation assets, including outputs produced with tools such as PNGAL
- VRM 3D models
- future renderer formats

Character assets must not define security permissions or bypass behavior policy.

The runtime should consume character definitions through renderer-neutral contracts.

See `../docs/architecture/character-presentation.md`.
