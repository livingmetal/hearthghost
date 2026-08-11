# HG-026 Persona Display Profile Follow-up Actions

Status: server persona name, scoped natural-language preference handling, and a name-only client display profile are implemented. Behavior preference persistence and an administrator settings UI remain unfinished.

## Implemented behavior

- [x] `character.name` is a typed Behavior Preference path.
- [x] Persona names are limited to 1-80 trimmed characters.
- [x] Unicode display names are supported.
- [x] Unicode control/format/surrogate/private-use/unassigned categories are rejected server-side.
- [x] Natural-language preference handling is now actually connected to the real conversation protocol.
- [x] A conservative local cue filter avoids invoking a second preference-classification LLM request for ordinary conversation.
- [x] Recognized preference requests require the same explicit Node-to-user/household principal resolver used by scoped Memory/TODO operations.
- [x] A successful preference request is completed locally after the typed preference service applies it; it does not then call the normal conversation LLM again.
- [x] Memory, Reminder, and Productivity local commands are evaluated before preference interpretation.
- [x] `ConversationWireResult` carries a non-authoritative `character_profile` containing only `name`.
- [x] Accepted conversation open/text/close results refresh the display profile from the current server Persona.
- [x] Android native transport requires the exact `character_profile = {name}` shape.
- [x] Android native transport independently rejects unsafe name characters.
- [x] WebView TypeScript independently validates the name-only profile again.
- [x] TextConversationController retains the latest validated display profile.
- [x] Character UI updates the visible character name without changing the HearthGhost product brand.

## Authority / privacy invariants

- [x] `character.name` remains behavior/display metadata only.
- [x] Persona name changes cannot alter Hard Policy, Node trust, capability grants, credentials, providers, tools, renderer asset URLs, or local sensor authorization.
- [x] Internal security instructions and persona prompt instructions are not sent in `character_profile`.
- [x] The Android bridge rejects extra profile fields such as instructions, capabilities, tools, or asset URLs.
- [x] Display-profile validation is repeated at server parsing, Android native parsing, and WebView parsing boundaries.
- [x] An unbound Node cannot change user/household persona preferences through the natural-language command path.
- [x] A visual name update creates no attention session and grants no device authority.

## Important unfinished persistence work

- [ ] Behavior preferences are currently runtime state and are not yet persisted in the HearthGhost PostgreSQL database.
- [ ] Restarting Core therefore returns the Persona/behavior values to configured defaults unless another configuration layer reapplies them.
- [ ] Design a versioned PostgreSQL preference table keyed by scope/scope_id before treating natural-language settings as durable household configuration.
- [ ] Persist only typed preference values, never synthesized prompts or model reasoning.
- [ ] Add optimistic revision/version checks so two clients cannot silently overwrite one another's preference update.
- [ ] Record preference audit metadata without storing unnecessary full conversation text.
- [ ] Define reset-to-default and erasure operations.

## Natural-language interpreter follow-up

- [ ] Replace the small deterministic fake-model name recognizer with real-provider integration tests before relying on broader natural-language naming phrases.
- [ ] Expand the local cue filter only with regression tests so ordinary discussion of names/humor/style does not unexpectedly enter settings mode.
- [ ] Decide how the user explicitly distinguishes "talk about your name" from "change your name" when the model is uncertain.
- [ ] Keep ambiguous interpretation fail-closed and avoid silently mutating settings.
- [ ] Add localization tests for Korean and English settings language.
- [ ] Do not allow an LLM-generated name to smuggle URLs, credentials, Node IDs, capability identifiers, or renderer commands into another subsystem.

## Client / physical Android validation

- [ ] Verify a real Android conversation open receives the default name.
- [ ] Say/type a name-change request and verify the same response updates the visible name without reconnecting.
- [ ] Verify the HearthGhost product brand stays unchanged when the character is renamed.
- [ ] Verify Korean, Latin, mixed-script, emoji, apostrophe, and space-containing names render acceptably.
- [ ] Verify bidi/control characters are rejected consistently across server/native/WebView boundaries.
- [ ] Verify TalkBack announces the updated character name without exposing internal system text.
- [ ] Verify large-font mode does not obscure the character or conversation controls.
- [ ] Import and visually validate the dedicated character-identity styling before release packaging.

## Character/profile expansion follow-up

- [ ] Keep the wire display profile deliberately small. Any future avatar/theme/voice fields require separate typed validation.
- [ ] Do not put raw prompt fragments into a display profile.
- [ ] If a future renderer asset identifier is exposed, use a reviewed server-side allowlist identifier rather than arbitrary URLs.
- [ ] TTS voice selection remains independent from the Persona name. A name change must not silently download or select a network voice.
- [ ] Emotion/state remain semantic presentation channels and must not be encoded into Persona name strings.

## Server/admin UI follow-up

- [ ] Add read-only Persona summary to the authenticated future administrator surface, not by exposing raw prompts.
- [ ] Add explicit administrator reset/update APIs only after administrator authentication and audit are designed.
- [ ] Keep Hard Policy editing physically/logically separate from Persona/Behavior Preference editing.
- [ ] If preferences become household-scoped, show the exact scope being edited to avoid accidental personal/household crossover.
