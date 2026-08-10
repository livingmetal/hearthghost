# Character Boundary

`CharacterViewport` hosts a `CharacterRenderer` implementation selected at the
composition boundary. Renderers consume semantic character state, emotion, and
future speech timing. They do not interpret policy or perform device actions.

Conversation state and emotion are separate inputs. Renderer-specific branching
must not escape this boundary.

Future sprite/2D and VRM/3D implementations live below this boundary and conform
to the same interface. HG-001 selects no graphics library, VRM version, runtime
asset format, or PNGAL export format.
