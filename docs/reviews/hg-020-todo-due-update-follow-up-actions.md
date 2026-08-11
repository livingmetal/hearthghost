# HG-020 Todo Due Update Follow-up Actions

Status: implementation and validation checklist for explicit due-date mutation.

## Implemented boundary

- [x] `할 일 기한: <short-ref|UUID> [<offset-aware ISO-8601>]` updates due metadata on an open todo only.
- [x] `할 일 기한 삭제: <short-ref|UUID>` clears due metadata on an open todo only.
- [x] Short references are resolved only inside the caller's principal scope and ambiguous prefixes fail closed.
- [x] Timezone-less or malformed due updates return `todo_due_invalid` locally and do not reach the LLM.
- [x] Completed todos reject due-date mutation.
- [x] Due-date mutation does not schedule reminders, notifications, timers, or calendar writes.

## Real-device and PostgreSQL validation

- [ ] Android real-device: create a todo, set a due timestamp using the returned short reference, then verify `할 일 목록` shows the new timestamp.
- [ ] Android real-device: clear the due timestamp and verify the list no longer displays it.
- [ ] Verify a short reference from another principal scope cannot be updated or cleared.
- [ ] Verify a completed todo cannot have its due timestamp changed through the command path.
- [ ] Verify PostgreSQL `UPDATE todo_records` preserves `scope` and `scope_id` checks and persists the changed `due_at` across restart.

## Product follow-up

- [ ] Decide whether to expose a dedicated `할 일 보기: <ref>` command before reminders are introduced.
- [ ] Decide how user-configured timezone presentation should work without changing the stored instant.
- [ ] Design reminder scheduling as a separate capability with explicit policy evaluation and revocation.
- [ ] Design notification delivery targets separately from todo storage; a due todo must not imply a device push destination.
- [ ] Keep calendar synchronization opt-in and separately authorized.
