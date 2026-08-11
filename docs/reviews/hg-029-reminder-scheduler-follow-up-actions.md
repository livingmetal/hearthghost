# HG-029 Reminder Scheduler / Claim Lease Follow-up Actions

Status: software claim/lease scheduler foundation complete and CI green. Real PostgreSQL concurrency/crash recovery and Android delivery remain environment-dependent checks.

## Implemented design invariants

- [x] A due `ReminderRecord` remains separate from notification authority.
- [x] Scheduler resolves the reminder principal through the explicit NotificationTargetResolver and never uses `created_by_node_id` as a delivery target.
- [x] Delivery still passes NotificationDeliveryService Policy + trusted Node + advertised/granted `notification.local` + Node-local authorization checks.
- [x] PostgreSQL claims use an atomic `FOR UPDATE SKIP LOCKED` selection plus a token/owner lease CAS.
- [x] No network delivery occurs while the claim transaction/row lock is held.
- [x] Expired claims are eligible for recovery by another scheduler instance.
- [x] A successfully committed delivery is terminal and is no longer claimable.
- [x] Denied/transient failures use exponential bounded backoff and exhaust after 8 attempts rather than hot-looping.
- [x] Cancellation/TODO lifecycle prevents new claims; due changes reset the active reminder delivery schedule.
- [x] Scheduler never changes Policy, Node trust, capability grants, notification routing, or local Android permission.
- [x] Notification payload remains redacted at this layer.
- [x] CI run #49 passed Python security/runtime, TypeScript/client, and Android unit/lint/debug APK jobs.

## Delivery semantic limitation

A DB lease prevents normal concurrent delivery, but cannot provide strict exactly-once semantics across an external Android side effect. If a phone displays an alert and Core dies before `mark_delivered`, the lease can later be recovered. The eventual Android adapter must therefore deduplicate the same reminder schedule, preferably by stable `(reminder_id, fire_at)` identity.

## PostgreSQL operator actions

- [ ] Back up the HearthGhost PostgreSQL database before first applying migration v6.
- [ ] Verify `hearthghost_schema_migrations` contains `6 / reminder_delivery_lease_v1`.
- [ ] Verify delivery-state constraints, pending/claim-expiry indexes, attempt counters and lease columns on the real database.
- [ ] Run two scheduler processes against a test reminder and prove only one claim is active.
- [ ] Kill a scheduler after claim but before completion and confirm lease recovery after expiry.
- [ ] Confirm delivered reminders remain terminal after Core restart.
- [ ] Confirm cancelled reminders are never selected even if an old lease existed.

## Runtime / clock checks

- [ ] Confirm Core host time synchronization is healthy; scheduler relies on timezone-aware server time and PostgreSQL time semantics.
- [ ] Decide production poll cadence after measuring home-server load.
- [ ] Revisit retry classification after the real Android delivery path exists; persistent local permission denial should not consume retries aggressively.

## Android dependency

- [ ] Implement and validate a local Android reminder scheduler/notification surface.
- [ ] Confirm local Android permission rather than server state determines whether a notification may actually be displayed.
- [ ] Prove duplicate `(reminder_id, fire_at)` schedules do not create duplicate notifications.
- [ ] Scheduler success must not be reported as Android display success until a real adapter returns confirmed local authorization evidence.

## Recovery principle

If claim state is malformed, repository data crosses scope, a route is ambiguous, or the delivery result is invalid, fail closed. Release/expire the lease according to bounded retry rules rather than inventing a target or marking the reminder delivered.
