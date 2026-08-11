# HG-027 Ephemeral Session History Follow-up Actions

Status: bounded client-only conversation history is implemented for the active attention/conversation window. No browser persistence, server transcript store, or long-term conversation archive is added by this work.

## Implemented behavior

- [x] Adds a client `EphemeralSessionHistory` model with user/assistant roles only.
- [x] Keeps at most the most recent 20 entries.
- [x] Limits each displayed entry to 4,000 characters and rejects empty/NUL-containing text.
- [x] Adds a compact collapsible Conversation surface below the character response.
- [x] Records a text turn only after the conversation request succeeds and a non-empty final assistant response exists.
- [x] Records on-device voice input only from the final accepted STT transcript after the server round trip succeeds.
- [x] Does not record raw audio, partial transcripts, failed sends, transport errors, or rejected voice results.
- [x] Renders conversation text with `textContent`, not dynamic HTML injection.
- [x] Clears the client history on Node reconnect.
- [x] Clears the client history when attention times out and the conversation ends.
- [x] Clears the client history when the app becomes hidden/backgrounded.
- [x] Clears the client history on pagehide.
- [x] Uses no localStorage, sessionStorage, IndexedDB, serialization, save, or restore API.

## Privacy / authority invariants

- [x] Session history is a display convenience only and creates no Memory entry.
- [x] A displayed turn does not imply explicit "remember this" consent.
- [x] Session history cannot create TODOs, Reminders, Behavior Preferences, Policy decisions, or tool execution authority.
- [x] The UI does not reconstruct history from server Memory/TODO/Reminder data.
- [x] Raw microphone data remains outside the history model.
- [x] Backgrounding removes visible in-memory transcript state rather than preserving it for convenience.

## Physical Android validation

- [ ] Verify text turns appear only after successful real Android/Core responses.
- [ ] Verify final on-device STT text appears once, with no partial transcript duplication.
- [ ] Verify a failed mTLS/request/LLM turn adds no history entry.
- [ ] Verify history is cleared after the 20-second attention timeout.
- [ ] Verify pressing Home/backgrounding the app clears history before resume.
- [ ] Verify reconnecting a Node starts with an empty history.
- [ ] Verify portrait and landscape history expansion does not cover the character or input controls.
- [ ] Verify keyboard resize behavior remains usable with the history details open.
- [ ] Verify TalkBack announces role and text in a sensible reading order.
- [ ] Verify large-font mode does not make the expandable history unusable.

## Conversation UX follow-up

- [ ] Decide whether the default collapsed state is correct after physical-device testing.
- [ ] Replace the generic assistant role label `Ghost` with the validated current Persona name without duplicating profile authority.
- [ ] Consider a manual `Clear conversation` control only if it remains local and cannot delete unrelated server Memory/TODO data.
- [ ] Consider showing only the most recent few turns inline while keeping the character visually dominant.
- [ ] Do not evolve this surface into a generic permanent chat archive without an explicit retention/privacy design.

## Durable conversation-history decision gate

Do not add persistence until the product has answered all of the following:

- [ ] Is durable conversation history actually needed, or are explicit Memory/Notes/TODOs sufficient?
- [ ] Which principal owns a durable transcript: user, household, or Node?
- [ ] What is the retention period and deletion model?
- [ ] Is transcript text encrypted separately from ordinary application data?
- [ ] How are household/private conversations prevented from crossing scopes?
- [ ] Which turns, if any, may be sent back to an external LLM as context?
- [ ] How does the user inspect and erase stored conversation history?
- [ ] What audit metadata is retained after transcript deletion?

Until those questions are answered, keep the current history ephemeral and bounded.

## Recommended next development step

The next product step should not be another client transcript feature. Resume with one of these explicitly reviewed tracks:

1. **HG-014 physical Android validation**: real spare phone enrollment, mTLS, trust/capability grant, and first text E2E.
2. **Behavior Preference persistence**: scoped/versioned PostgreSQL persistence for Persona and behavior values from HG-026.
3. **Reminder scheduler/claiming**: consume the explicit routing/delivery boundaries from HG-023 only after idempotency and claim/lease design.
4. **Authenticated administrator surface**: only after separating admin authentication/authorization from the current read-only HG-025 dashboard.

Do not start any of these automatically from HG-027. Pick the track deliberately at the next work session.
