# Character Boundary

`CharacterViewport` hosts a `CharacterRenderer` implementation selected at the
composition boundary. Renderers consume semantic character state, emotion, and
future speech timing. They do not interpret policy or perform device actions.

Conversation state and emotion are separate inputs. Renderer-specific branching
must not escape this boundary.

`DomCharacterRenderer` is the dependency-free 2D/test fallback.
`VrmCharacterRenderer` contains all Three.js, `@pixiv/three-vrm`, and reviewed
VRM Animation runtime knowledge. Its close conversation camera and bounded
movement extents live together in `vrm-framing.ts`; these values remain
renderer-local rather than semantic event fields. Direct drag, wheel, pinch,
and keyboard framing adjustments are also bounded renderer-local state and
never become Node or Core commands. Windows and the Android/web client use the
same VRM renderer, so mouse-wheel and two-finger touch pinch share the same
face-close-up bounds. Near maximum zoom, drag sensitivity scales down with
camera distance so a face can be centered without large pointer movements.

Idle presentation now has two base-motion implementations. The preferred path
is `VrmBaseAnimationLayer`, which loads the pinned local AIRI `idle_loop.vrma`
through `@pixiv/three-vrm-animation` and a Three.js `AnimationMixer`. Only
humanoid rotation and hips-translation tracks enter that mixer. Expression and
look-at tracks are deliberately excluded so semantic emotion, gaze, blink and
lip-sync remain authoritative HearthGhost overlays. The hips translation track
is re-anchored to the current VRM and clamped to a small idle envelope, so an
idle animation cannot walk or pan the whole avatar across the stage.

`vrm-base-motion.ts` remains the fail-safe fallback. Its foot-planted procedural
idle shifts weight through pelvis, legs, spine, shoulders, neck, and head with
no root-position output. If the bundled VRMA is unavailable or malformed, the
renderer falls back to that procedural source without preventing the approved
VRM from loading. Only an explicit semantic `move` gesture may temporarily
translate the avatar scene root.

This layering follows the architectural separation used by AIRI: base/idle
animation is independent from blink, eye motion, expression, lip sync, and
other presentation overlays. HearthGhost keeps its own contracts and bounds.
The AIRI asset source, pinned identity, and MIT notice are recorded in
`THIRD_PARTY_PRESENTATION_ASSETS.md`; it is fetched only at build/development
asset time and is not downloaded from AIRI by a running application.

Invalid, combined, or renderer-specific events fail at the viewport boundary.
No renderer receives Node credentials, trust administration, Privacy Gateway
state, Tool proposals, or provider configuration.
