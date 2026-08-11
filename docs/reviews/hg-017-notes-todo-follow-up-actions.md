# HG-017 notes and todo follow-up actions

Status: explicit local note/todo foundation implemented on top of scoped memory principals. Human-friendly management, scheduling, notifications, and production storage policy remain open.

## Implemented safeguards

- [x] `메모해:` / `노트:` / `note:` commands are deterministic local commands, not LLM-extracted memories.
- [x] `할 일:` / `todo:` commands create todos only after a scoped principal is resolved.
- [x] Todo completion is explicit and UUID-addressed in this milestone.
- [x] Notes reuse scoped `MemoryKind.NOTE`; todos use a separate typed state model.
- [x] User/household scope is resolved before persistence and exact-scope checks are repeated in domain/repository layers.
- [x] Unbound or resolver-failure cases do not fall back to the LLM.
- [x] Note/todo commands are intercepted locally before the ordinary conversation model path.
- [x] Todo SQLite persistence rejects symlink paths, requires an owner-only parent, and forces the shared personal-data DB to mode `0600`.
- [x] Open/completed state consistency is checked when SQLite rows are decoded.
- [x] A versioned todo-record contract was added.

## Required product work

- [ ] Add local list commands such as `할 일 목록` and `메모 목록` with strict scope resolution and bounded output.
- [ ] Add a safer human-friendly completion selector. UUID is unambiguous but poor UX; consider short display IDs or numbered results with a revision token so stale numbering cannot mutate the wrong todo.
- [ ] Add explicit delete commands for notes/todos with the same stale-reference protection.
- [ ] Add due dates only after timezone semantics are defined. Store normalized instants plus the original/local timezone context where needed.
- [ ] Add reminders/notifications as a separate capability with explicit scheduling and cancellation semantics. Creating a todo must not silently create a notification.
- [ ] Decide completed-todo retention and purge policy.
- [ ] Define conflict/update semantics for editing existing todos and notes.
- [ ] Calendar integration must remain a separate authorization boundary; a todo must not become a calendar event without an explicit request and calendar permission.
- [ ] Add audit events for create/complete/delete without copying note/todo plaintext into audit logs.

## Storage and operations follow-up

- [ ] `--memory-db` now stores memory, notes, and todos. Keep it for compatibility for now, but consider a future `--personal-data-db` alias/migration so the name matches the broader purpose.
- [ ] Memory and todo repositories currently use separate SQLite connections/tables in the same file. Measure lock contention before increasing concurrency or adding background writers.
- [ ] At-rest encryption, backup/restore, erasure, and principal-administration requirements from HG-016 also apply to notes/todos.
- [ ] Rebase or otherwise clean stacked branch history after the lower PRs merge so copied synchronization commits do not become permanent history noise.

## Integration validation

- [ ] With a personal Node binding, verify `메모해:` creates only a user-scoped NOTE and survives restart when persistent storage is configured.
- [ ] Verify `할 일:` survives restart and `할 일 완료: <uuid>` changes only the matching scoped record.
- [ ] Verify another user/household scope cannot list, complete, or delete the todo even if the UUID is known.
- [ ] Verify unbound Node commands receive a local denial and generate no LLM request.
- [ ] Verify the existing ordinary conversation path is unchanged for non-command text.
