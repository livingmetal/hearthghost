# HG-024 Character Experience Follow-up Actions

Status: character-first mobile UX foundation. This work changes presentation only and does not grant new Core, Node, sensor, or tool authority.

## Implemented experience

- [x] Adds `noticing` as a renderer-neutral semantic character state.
- [x] Touch wake visibly transitions through `noticing` before `listening`.
- [x] On-device STT shows `listening` while capture is active.
- [x] In-flight text/voice requests show `thinking` before the response arrives.
- [x] Embedded local TTS shows `speaking` for the actual synthesis interval.
- [x] Attention timeout and app background return presentation to `sleeping`.
- [x] Success/error presentation cues use semantic emotion values rather than renderer-specific commands.
- [x] Server semantic events continue through the strict CharacterViewport parser.
- [x] DOM fallback is now an expressive animated character with state/emotion styling.
- [x] Mobile layout puts the character and response ahead of diagnostics/provisioning UI.
- [x] Quick Memo/Todo/Reminder templates only populate text input; they do not bypass wake, principal, or Core authorization.
- [x] Reduced-motion preference disables repeated character animations.

## Safety invariants

- [x] Character state is presentation metadata only.
- [x] Emotion cannot encode a tool or renderer command.
- [x] `CharacterViewport` still rejects unknown event types and renderer-specific payload fields.
- [x] A visually awake/concerned/happy character does not create an attention session or Node capability.
- [x] Touch wake remains the authority for client attention; presentation follows it rather than replacing it.
- [x] Character animation never wakes microphone, camera, or device tools.

## Physical Android validation

- [ ] Verify portrait layout on the designated phone at normal and large font scales.
- [ ] Verify landscape layout does not cover the character or send controls.
- [ ] Verify safe-area insets around cutout/status/navigation areas.
- [ ] Verify `noticing -> listening` is visible after touch without feeling sluggish.
- [ ] Verify thinking remains visible during a real Core/LLM round trip.
- [ ] Verify speaking begins and ends with embedded TTS, not merely when response text arrives.
- [ ] Verify backgrounding freezes renderer animation and returns to sleeping state.
- [ ] Verify reduced-motion Android/browser preference removes pulsing/talking animation.
- [ ] Verify TalkBack reads useful state without announcing decorative face parts.
- [ ] Verify keyboard appearance does not collapse the character viewport to unusable size.

## Character asset follow-up

- [ ] Decide the first production character identity and canonical name.
- [ ] Keep semantic states/emotions independent of the renderer asset format.
- [ ] If VRM is used, add an explicit reviewed asset URL/configuration path; do not let LLM text select arbitrary asset URLs.
- [ ] Map semantic emotions to a bounded allowlist of VRM expression presets.
- [ ] Map speaking to mouth/lip motion without microphone/raw-audio access in the renderer.
- [ ] Add idle blink/breath motion that is entirely local and non-authoritative.
- [ ] Add a renderer fallback when WebGL/VRM initialization fails.
- [ ] Record asset license/source before distribution.

## Product UX follow-up

- [ ] Add a compact conversation history surface without turning the character screen into a generic chat transcript.
- [ ] Add dedicated Notes/Todo views driven by scoped server data rather than parsing rendered response text.
- [ ] Add a Reminder view that distinguishes scheduled, cancelled, delivered, and failed attempts after delivery exists.
- [ ] Add a Persona/settings screen for name, humor, verbosity, formality, initiative, and follow-up timeout.
- [ ] Add an explicit privacy/security sheet that explains local STT/TTS and denied cloud media in user language.
- [ ] Move development enrollment controls behind a developer/admin mode before household distribution.

## Server UI follow-up

- [ ] Build a read-only server overview first: Core, PostgreSQL, LLM, Nodes, Memory, TODO, Reminder, Policy status.
- [ ] Add Node enrollment/trust/revocation only behind administrator authorization.
- [ ] Add principal bindings and notification routes as explicit administrator configuration.
- [ ] Add persona/behavior preference management separately from Hard Policy configuration.
- [ ] Never expose private keys, provider secrets, PostgreSQL DSNs, raw microphone data, or private reminder text in generic status pages.
