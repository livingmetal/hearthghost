# Character Presentation Architecture

## Goal

HearthGhost must support a persistent character without coupling the application to one rendering technology.

The character's identity, persona, voice, memory, conversation state, and visual renderer are separate concerns.

```text
Ghost Identity
├─ Persona
├─ Voice
├─ Memory namespace
└─ Appearance / Renderer
```

## Appearance and persona selection

Client options keep appearance and persona independent:

- **Appearance** selects a bundled local VRM model and local voice profile. It
  is device-local presentation state and never changes the assistant's name or
  conversational behavior.
- **Persona** selects the assistant name plus the typed `humor`, `verbosity`,
  `formality`, and `initiative` preferences. Core is authoritative for the
  active values and persists them in the authenticated principal's scope. On
  every conversation open, the server returns all five typed fields and the
  client hydrates its options from that profile without writing local defaults
  back. A device may keep a small preset cache only as an editing convenience.

The persona UI cannot supply a system prompt, tool instructions, credentials,
policy, Node trust, capabilities, renderer commands, or arbitrary key/value
data. It sends one versioned deterministic command containing exactly the five
allowed string fields; Core rejects malformed, extra, or invalid fields before
calling an LLM or changing the stored profile.

## Renderer abstraction

The application shell and HearthGhost Core must not depend directly on VRM, PNGAL output, Live2D, or any future renderer.

```text
App Shell
   |
CharacterViewport
   |
CharacterRenderer abstraction
   |-------------------|
Sprite Renderer      VRM Renderer
   |                    |
PNGAL/2D assets       .vrm model
```

Renderer-specific dependencies, asset rules, animation code, blendshapes, and scene setup belong inside the renderer implementation.

## Initial renderer families

### Sprite / 2D

May consume PNG, animated WebP, WebM, sprite sheets, or assets generated through tools such as PNGAL. The exact runtime format is intentionally undecided until prototyping demonstrates the best option.

### VRM / 3D

May render a VRM avatar with expressions, gaze, body animation, and lip sync. The exact JavaScript/graphics library and VRM version support are intentionally undecided until implementation work begins.

## Semantic events

The server should emit semantic character events instead of renderer-specific animation instructions.

Example:

```json
{
  "type": "character.state",
  "payload": {
    "state": "speaking",
    "emotion": "amused"
  }
}
```

The renderer translates the semantic state into its own visual behavior.

Presentation-only gestures use a small typed allowlist. It includes bounded
screen-space movement (`forward`, `backward`, `left`, or `right`) but never raw
coordinates, distances, bone names, animation clips, or device commands. A VRM
renderer may combine that movement with local stepping and posture animation;
other renderers may reduce it to a simple translation while preserving the same
semantic boundary.

## State and emotion are separate

Conversation state and emotion must not be collapsed into one animation enum.

Conversation state examples:

```text
sleeping
listening
thinking
speaking
engaged
```

Emotion examples:

```text
neutral
happy
amused
curious
concerned
surprised
```

This avoids an animation matrix explosion such as `speaking_happy`, `speaking_sad`, `thinking_happy`, and so on becoming the domain model.

## Speech animation

Lip sync must also be renderer-agnostic. A future speech event may contain audio timing, phoneme/viseme timing, or simpler mouth-open envelopes. A sprite renderer may reduce this to open/closed mouth frames while a VRM renderer may drive detailed facial blendshapes.

## CharacterViewport

The mobile UI must reserve a renderer-neutral CharacterViewport. UI controls should not assume a fixed character silhouette, body size, or camera composition.

Preferred layout principle:

```text
Top/Edges  -> system state, privacy indicators
Center     -> CharacterViewport
Bottom     -> captions / primary interaction
Side       -> contextual information when space allows
```

The viewport must work in both portrait and landscape layouts.

## Deferred decisions

Do not prematurely standardize:

- a specific Three.js or VRM library
- exact PNGAL export format
- exact viseme set
- exact asset directory format
- exact percentage of screen occupied by the character
- required 3D camera framing

These should be chosen through prototype evidence while preserving the abstraction above.
