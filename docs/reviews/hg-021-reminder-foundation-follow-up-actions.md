# HG-021 Reminder Foundation Follow-up Actions

Status: implementation and operator checklist. A checked code item is not evidence that Android notification delivery is enabled.

## Implemented foundation

- [x] Reminder scheduling is a separate domain from TODO `due_at` metadata.
- [x] Only an explicit local command can create a reminder record.
- [x] Reminder scheduling requires an OPEN TODO with a timezone-aware future `due_at`.
- [x] Scheduling horizon is bounded to 366 days.
- [x] One active reminder per `(scope, scope_id, todo_id)` is enforced in application code and PostgreSQL.
- [x] Reminder commands resolve the same user/household principal boundary used by memory and TODOs.
- [x] `할 일 알림: <ref>`, `할 일 알림 취소: <ref>`, and `알림 목록` are deterministic local commands and do not call the LLM.
- [x] TODO due changes resynchronize an existing reminder; due removal/completion cancels it.
- [x] PostgreSQL v4 adds `reminder_records` and due/scope indexes.
- [x] PostgreSQL validates reminder scope against the referenced TODO before write.
- [x] PostgreSQL synchronizes reminder fire time/state in the same transaction as TODO due/state updates.
- [x] PostgreSQL deletes reminder rows when their TODO is deleted (`ON DELETE CASCADE`).
- [x] Core status explicitly reports `explicit_schedule_only_delivery_disabled`.

## Deliberately NOT implemented yet

- [ ] No scheduler loop polls or claims due reminders.
- [ ] No Android notification is displayed.
- [ ] No vibration, sound, wakeup, foreground service, exact alarm, push notification, FCM, or cloud delivery is enabled.
- [ ] No LLM-created reminder proposal is accepted.
- [ ] No natural-language time phrase such as `내일 아침` is interpreted as a reminder time.
- [ ] No TODO automatically creates a reminder merely because it has `due_at`.
- [ ] Reminder persistence is not notification authority. Delivery requires a separate reviewed capability and Node/local authorization.

## Operator actions before PostgreSQL v4

- [ ] Verify PRs for PostgreSQL migrations and TODO due support are merged/applied in order before v4.
- [ ] Take and verify a PostgreSQL backup before first startup that applies migration v4.
- [ ] Confirm the HearthGhost PostgreSQL role can create the v4 table, functions, triggers, indexes, and foreign key in its own database.
- [ ] After migration, verify `hearthghost_schema_migrations` contains version 4 / `reminder_records_v1` exactly once.
- [ ] Inspect `reminder_records`, `hearthghost_validate_reminder_scope_trigger`, and `hearthghost_sync_todo_reminder_trigger` in the real PostgreSQL service.
- [ ] Verify PostgreSQL remains private and TLS-protected as documented in `docs/deployment/postgresql.md`.

## Real PostgreSQL validation

- [ ] Schedule one reminder and restart Core; confirm the same reminder remains scheduled.
- [ ] Attempt a direct SQL insert whose reminder scope differs from its TODO scope; confirm PostgreSQL rejects it.
- [ ] Change a scheduled TODO due time; confirm `reminder_records.fire_at` changes in the same transaction.
- [ ] Clear the due time; confirm the scheduled reminder becomes `cancelled` with `cancelled_at` set.
- [ ] Complete the TODO; confirm an active reminder is cancelled.
- [ ] Delete the TODO; confirm its reminder row is deleted by FK cascade.
- [ ] Attempt two active reminders for the same scoped TODO; confirm the unique partial index rejects the second.
- [ ] Confirm a reminder in another user/household scope cannot be listed or cancelled through the application API.

## Android / Node delivery follow-up

- [ ] Define a Node capability for local notification delivery; do not treat generic text capability as notification authority.
- [ ] Decide whether the capability is named `notification.local`, `reminder.notify`, or another reviewed namespaced form.
- [ ] Require local Android notification permission where the Android version requires it.
- [ ] Decide whether notification delivery may occur while HearthGhost is backgrounded and document the Android lifecycle implications.
- [ ] Keep notification content bounded and avoid exposing private TODO text on a locked screen by default.
- [ ] Define a redacted notification mode such as `HearthGhost reminder` for lock-screen privacy.
- [ ] Define delivery acknowledgement and retry semantics before adding a scheduler loop.
- [ ] Define what happens when the target personal Node is offline at `fire_at`.
- [ ] Decide household reminder routing independently from personal reminder routing.

## Scheduler / reliability follow-up

- [ ] Add a claim/lease model before more than one Core process can poll reminders.
- [ ] Use PostgreSQL locking (`FOR UPDATE SKIP LOCKED` or an equivalent reviewed design) before multi-worker delivery.
- [ ] Define idempotency key and at-most-once / at-least-once delivery behavior.
- [ ] Store delivery attempts separately from the reminder schedule record rather than overwriting history.
- [ ] Bound retry count and retry horizon so a stale reminder cannot interrupt the user indefinitely.
- [ ] Ensure system clock jumps and DST do not reinterpret stored `TIMESTAMPTZ` values.
- [ ] Add an ephemeral real-PostgreSQL CI integration test for migrations, triggers, FK cascade, and concurrent scheduling.

## Privacy / audit follow-up

- [ ] Add audit events for schedule/cancel/reschedule without recording full private TODO text by default.
- [ ] Define retention and erasure semantics for cancelled reminders.
- [ ] Decide whether TODO deletion should permanently erase reminder history or move delivery/audit metadata to a text-free audit table first.
- [ ] Never send reminder text to an LLM merely to decide whether a reminder is due.
- [ ] Never log PostgreSQL DSNs, reminder text, or notification payloads at INFO level.
