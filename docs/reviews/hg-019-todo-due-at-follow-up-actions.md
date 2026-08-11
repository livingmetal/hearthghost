# HG-019 Todo Due-at Follow-up Actions

Status: implementation and operator validation checklist for explicit todo due timestamps.

## Operator actions

- [ ] Take and verify a PostgreSQL backup before the first production startup that applies schema migration v3 (`todo_due_at_v1`).
- [ ] Verify `hearthghost_schema_migrations` contains versions 1, 2, and 3 with the expected names after startup.
- [ ] Verify `todo_records.due_at` is `TIMESTAMPTZ` and that existing todo rows remain valid with `due_at IS NULL`.
- [ ] Verify the partial index for open due todos exists before relying on due-date queries at scale.
- [ ] Do not manually edit migration metadata to bypass a failed v3 migration; restore or repair the schema deliberately.

## Functional validation

- [ ] Android real-device: `할 일 [2026-08-12T09:00+09:00]: DB 백업 확인` creates a todo with the exact offset-aware due timestamp.
- [ ] Android real-device: `할 일 목록` displays the stored due timestamp and short reference.
- [ ] Android real-device: timezone-less input such as `할 일 [2026-08-12T09:00]: ...` is recognized locally and rejected with `todo_due_invalid`.
- [ ] Verify malformed bracketed due syntax never falls through to the cloud LLM and never creates a plain todo accidentally.
- [ ] Verify todo completion and deletion preserve the same principal scope rules when `due_at` is present.
- [ ] Verify restart persistence against the real PostgreSQL service and confirm the same instant is recovered as an aware timestamp.

## Product boundary

- [x] Due timestamps are metadata only. Creating a due todo does not schedule a notification, timer, wakeup, or calendar event.
- [x] Only explicit ISO-8601 timestamps with an offset/timezone are accepted in this foundation. Natural-language dates such as `내일 아침` are not interpreted locally.
- [ ] Define a separate reminder capability and authorization policy before any background notification is scheduled.
- [ ] Define a separate calendar-write capability and confirmation policy before a todo may create or modify an event.
- [ ] Decide whether user-facing output should preserve the original offset or normalize presentation to the user's configured timezone.
- [ ] Decide whether natural-language date interpretation should be local deterministic parsing, LLM-assisted proposal, or both. It must not silently change the stored due instant.

## Data engineering and security follow-up

- [ ] Add a real PostgreSQL v2-to-v3 migration integration test in CI.
- [ ] Add audit metadata for due-date creation/change without logging private todo text by default.
- [ ] Add an explicit due-date update/remove command before supporting reminder scheduling.
- [ ] Define retention/export behavior for due timestamps together with todo data.
- [ ] Measure due-date query patterns before adding more indexes or a connection pool.
