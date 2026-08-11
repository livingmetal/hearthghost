# HG-017 Notes and Todo Follow-up Actions

Status: implementation follow-up checklist. Checked implementation items still require real-device/real-PostgreSQL validation where called out separately.

## Operator actions

- [ ] Create or verify the dedicated `hearthghost` PostgreSQL database and unprivileged `hearthghost` role described in `docs/deployment/postgresql.md`.
- [ ] Mount the PostgreSQL DSN as `/run/secrets/hearthghost-postgres-dsn` (or another owner-readable secret path) rather than passing credentials on the command line.
- [ ] Configure explicit Node principal bindings for personal and/or household scopes. PostgreSQL connectivity alone must not authorize note/todo writes.
- [ ] Verify PostgreSQL is not exposed to the public Internet and use TLS for networked DB traffic. Prefer certificate verification with the local CA.
- [ ] Back up the HearthGhost PostgreSQL database and test restore before relying on notes/todos operationally.

## Functional validation

- [ ] Android real-device: `메모해:` creates a NOTE in the expected scope and does not invoke the LLM.
- [ ] Android real-device: `할 일:` creates an OPEN todo and returns its short reference.
- [ ] Android real-device: `할 일 목록` lists at most 10 open todos with short references.
- [ ] Android real-device: `할 일 완료: <short-ref>` changes only a todo in the caller's resolved scope.
- [ ] Android real-device: `할 일 삭제: <short-ref>` deletes only a todo in the caller's resolved scope.
- [ ] Verify a shared/unbound Node cannot write or list user-scoped notes or todos.
- [ ] Verify a todo reference from another scope cannot be completed or deleted.
- [ ] Verify restart persistence against the real PostgreSQL service.

## Product follow-up

- [x] Add `할 일 목록` / `todo list` local commands with bounded result count.
- [x] Add user-friendly short references so people do not need to speak a UUID; 8-hex prefixes are accepted only when unique inside the resolved scope.
- [x] Add explicit todo deletion with scope checks.
- [ ] Add explicit note listing/deletion commands with scope checks.
- [ ] Add due date and timezone fields only after an explicit date/time contract is defined.
- [ ] Treat reminders/notifications as a separate policy-controlled capability, not as an automatic consequence of a todo.
- [ ] Treat calendar writes as a separate authorization boundary. A todo must never silently create or modify a calendar event.

## Data engineering and security follow-up

- [ ] Add migrations/version tracking instead of relying indefinitely on `CREATE TABLE IF NOT EXISTS` startup DDL.
- [ ] Define retention, export, erasure, and household backup policy for personal data.
- [ ] Decide whether row-level security is useful in addition to application scope checks once multiple server processes/users exist.
- [ ] Add PostgreSQL integration tests against an ephemeral real server in CI; current repository tests use a fake connector to verify SQL shape and parameter binding.
- [ ] Add audit events for note/todo create/complete/delete without logging the full private text by default.
- [ ] Measure connection churn. Current adapters open short-lived connections; introduce a bounded pool only if real workload justifies it.
