# HG-029 Reminder Scheduler / Claim Lease Follow-up Actions

Status: implementation in progress. This log is created before scheduler code so delivery idempotency and operational actions remain explicit.

## Design invariants

- [ ] A due `ReminderRecord` is still not notification authority.
- [ ] Scheduler must resolve the reminder principal through the explicit NotificationTargetResolver; never use `created_by_node_id` as a delivery target.
- [ ] Delivery must still pass NotificationDeliveryService Policy + trusted Node + advertised/granted `notification.local` + Node-local authorization checks.
- [ ] Multiple Core instances must not concurrently deliver the same reminder under normal lease operation.
- [ ] PostgreSQL claims must be atomic and bounded by a lease; no network delivery occurs while a DB transaction/row lock is held.
- [ ] An expired claim may be recovered by another scheduler instance.
- [ ] A successful delivery is terminal and cannot be claimed again.
- [ ] A denied/transient failure is retried only with bounded attempts/backoff; permanent configuration/authority failures must not become a hot loop.
- [ ] Cancellation/TODO lifecycle must prevent new claims.
- [ ] Scheduler never changes Policy, Node trust, capability grants, notification routing, or local Android permission.
- [ ] Notification payload remains redacted at this layer.

## PostgreSQL operator actions

- [ ] Back up the HearthGhost PostgreSQL database before first applying the scheduler migration.
- [ ] Verify migration version, delivery-state constraints, indexes, and lease columns on the real database.
- [ ] Run two scheduler processes against a test reminder and prove only one claim is active.
- [ ] Kill a scheduler after claim but before completion and confirm lease recovery after expiry.
- [ ] Confirm delivered reminders remain terminal after Core restart.
- [ ] Confirm cancelled reminders are never selected even if an old lease exists.

## Runtime / clock checks

- [ ] Confirm Core host time synchronization is healthy; scheduler relies on timezone-aware server time and PostgreSQL time semantics.
- [ ] Decide production poll cadence after measuring home-server load. Initial implementation should remain low-frequency and bounded.
- [ ] Decide retry classification after the real Android delivery adapter exists; do not retry a permanent permission denial aggressively.

## Android dependency

- [ ] Actual notification display remains dependent on a future native Android adapter and physical permission validation.
- [ ] Scheduler success must not be reported as notification delivery success until the native adapter returns confirmed local authorization evidence.

## Recovery principle

If claim state is malformed, repository data crosses scope, a route is ambiguous, or the delivery result is invalid, fail closed. Release/expire the lease according to bounded retry rules rather than inventing a target or marking the reminder delivered.
