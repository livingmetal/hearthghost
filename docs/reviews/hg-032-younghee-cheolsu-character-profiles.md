# HG-032 Younghee / Cheolsu Character Profiles

Status: software implementation complete pending final Android CI and physical model/voice validation.

> Later client options separate appearance from persona. The A/C selector now
> controls only the local VRM and voice; a distinct persona selector applies
> the principal-scoped name and behavior fields. The original exact
> `캐릭터: 영희/철수` protocol remains supported for older clients.

## Character mapping

- `영희` → local character id `younghee` → official asset slot `/models/AvatarSample_A.vrm`
- `철수` → local character id `cheolsu` → official asset slot `/models/AvatarSample_C.vrm`

The HearthGhost names are local fictional presentation/persona labels. They do not rename or claim authorship of the official VRoid sample assets.

## Implemented behavior

- [x] Android/WebView exposes an A/C character selector only while a trusted, awake `conversation.text` session may accept input.
- [x] Selector emits exact local commands `캐릭터: 영희` and `캐릭터: 철수`.
- [x] Exact A/C selection bypasses the LLM preference classifier and goes directly through typed `BehaviorPreferenceChange("character.name", ...)` and the existing principal-scoped manager/repository boundary.
- [x] Character selection cannot represent Hard Policy, Node trust, capability, credential, sensor, provider, or tool authority.
- [x] The server continues to transport only the display-safe `character_profile.name`; renderer URLs and voice configuration do not cross the server wire.
- [x] Client maps the validated server name to a fixed built-in local catalog. Arbitrary server names cannot inject asset URLs.
- [x] CharacterViewport can replace renderers while preserving semantic state/emotion.
- [x] VRM asset load failure preserves/falls back to the DOM character rather than fetching an untrusted remote model.
- [x] No runtime HTTP URL exists in the A/C character asset catalog.
- [x] 영희 and 철수 receive deliberately different strong, non-security Persona style anchors during ordinary LLM conversation.
- [x] Existing explicit humor/verbosity/formality/initiative preferences may tune those anchors without granting authority.
- [x] TTS remains embedded/local-only and rejects network-required or not-installed voices.
- [x] If Android exposes at least two suitable local Korean voices, 철수 selects the second stable candidate while 영희 selects the first.
- [x] Distinct pitch/rate tuning remains even when the device exposes only one suitable local voice: 영희 1.10/1.04, 철수 0.88/0.94.

## VRM asset prerequisite

The binary official sample VRM files are intentionally not sourced from unofficial mirrors. Obtain/export the official VRoid Studio sample assets through the official VRoid Studio/VRoid Hub flow, then place them at:

- `apps/web-client/public/models/AvatarSample_A.vrm`
- `apps/web-client/public/models/AvatarSample_C.vrm`

The current official VRoid sample terms state that AvatarSample A–Z are not CC0 but permit broad use including commercial use, modification, redistribution, and no mandatory attribution, subject to the current conditions. Re-check the official terms at release time.

## Physical Android checks

- [ ] Bundle official A and C VRM files and confirm both render on the target Galaxy device without network access.
- [ ] Confirm VRM 0.x orientation, camera framing, hair/clothing visibility, and acceptable frame rate.
- [ ] Switch 영희 → 철수 → 영희 repeatedly and confirm no WebGL context/resource leak or blank viewport.
- [ ] Confirm sleeping/listening/thinking/speaking state transitions remain visible on both VRM assets.
- [ ] Confirm `aa` mouth expression responds during local TTS on both models.
- [ ] Enumerate the actual installed `ko-KR` embedded voices on the target phone and record their names/quality/latency.
- [ ] Confirm 영희 and 철수 sound clearly different with the target TTS engine. Tune pitch/rate only after listening on the real device.
- [ ] Verify no TTS network traffic occurs in airplane/local-network test conditions.
- [ ] Confirm a different principal's selected character remains isolated after restart when PostgreSQL preference persistence is enabled.

## Voice-selection limitation

Android `TextToSpeech.Voice` does not provide a portable gender/character semantic field. HearthGhost must not infer gender from undocumented voice names. The current profile uses stable local candidate ordering plus pitch/rate differentiation. A later device-specific mapping may explicitly bind reviewed voice names after physical inspection.

## Future polish

- optional idle VRM animation and blink controller
- expression mapping for happy/amused/curious/concerned/surprised beyond the current mouth activity
- camera/framing calibration per model
- release-bundled asset checksums and provenance record
- optional explicit device-specific TTS voice binding stored as non-authoritative behavior configuration
