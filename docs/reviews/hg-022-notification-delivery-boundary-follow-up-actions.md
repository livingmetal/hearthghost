# HG-022 Notification Delivery Boundary Follow-up Actions

Status: security boundary and implementation checklist. No real Android notification transport is enabled by this work.

## Implemented boundary

- [x] Notification delivery is separate from reminder persistence and scheduler ownership.
- [x] Capability name is currently `notification.local`.
- [x] Every attempt creates a non-authoritative `ProposedAction` and requires Policy `allow` before adapter invocation.
- [x] Policy proposal binds `reminder_id`, `target_node_id`, exact timezone-aware `fire_at`, and `content_mode=redacted`.
- [x] Target Node must be present in the authoritative Node registry.
- [x] Target Node must be `trusted`.
- [x] Target Node must advertise `notification.local` exactly once.
- [x] The advertisement must declare `local_authorization_required=true`.
- [x] The authoritative grant set must contain `notification.local`.
- [x] Adapter request is hard-coded to redacted lock-screen-safe content: title `HearthGhost`, body `Reminder`.
- [x] Adapter request cannot weaken `content_mode` or local-authorization requirement.
- [x] A successful adapter result must explicitly assert `local_authorization_confirmed=true`.
- [x] Default Core adapter is deny-only; injecting no adapter cannot deliver anything.
- [x] Core status distinguishes reminder scheduling from notification delivery configuration.

## Deliberately NOT implemented

- [ ] No scheduler calls `NotificationDeliveryService` yet.
- [ ] No target Node resolver exists yet.
- [ ] No Android transport adapter exists yet.
- [ ] No Android notification channel is created.
- [ ] No `POST_NOTIFICATIONS` runtime permission is requested.
- [ ] No foreground service, exact alarm, WorkManager job, FCM push, or cloud messaging is enabled.
- [ ] No lock-screen private TODO text is sent.
- [ ] No retry, acknowledgement, delivery receipt, or delivery-attempt persistence is implemented.
- [ ] No household routing policy exists.
- [ ] No LLM can bypass the Policy/Node/local authorization chain.

## Capability model follow-up

- [ ] Review whether `notification.local` is the final capability name or whether `reminder.notify` better matches the domain.
- [ ] If the name is retained, add it to the reviewed contract/catalog only through the normal versioned contract process.
- [ ] Decide whether `notification.local` should be promoted into the global `SENSITIVE_LOCAL_CAPABILITIES` set after an Android implementation exists.
- [ ] Do not rely solely on that global set; retain the delivery-service check that `local_authorization_required` is exactly true.
- [ ] Define what constitutes Node-local authorization for Android: OS permission alone, app-level user grant, or both.
- [ ] Define a revocation path that immediately prevents future delivery attempts without deleting reminder records.

## Android implementation follow-up

- [ ] Add an Android `notification.local` capability advertisement only after the implementation is present.
- [ ] Ensure the capability advertisement is absent on builds/devices that cannot display notifications safely.
- [ ] Add Android 13+ `POST_NOTIFICATIONS` permission handling without requesting it before a user-visible reason exists.
- [ ] Use an app-owned notification channel with bounded importance; do not silently request maximum interruption level.
- [ ] Keep lock-screen visibility private/secret by default.
- [ ] Do not expose TODO text in notification extras, logs, crash reports, accessibility labels, or analytics by default.
- [ ] Require Node-local permission state immediately before display, not only at enrollment time.
- [ ] Return a typed delivery result that confirms whether local authorization was checked and whether display actually occurred.
- [ ] Verify notification delivery cannot wake microphone/STT/camera or start an attention session.
- [ ] Verify notification tap may open HearthGhost but must still require the normal attention/user-presence boundary before conversation input.

## Policy follow-up

- [ ] Define a reviewed Policy rule for `notification.local`; the current default Policy remains deny-only.
- [ ] Bind a delivery approval to reminder ID, target Node ID, `fire_at`, and redacted content mode.
- [ ] Decide whether per-reminder explicit approval is required or whether an administrator/user may grant a bounded class of future reminders.
- [ ] Keep household reminder delivery stricter than personal-node delivery until household presence/routing semantics are defined.
- [ ] Deny delivery if reminder ownership cannot be resolved to the same principal as the target routing decision.

## Scheduler integration follow-up

- [ ] Scheduler must fetch/claim only reminders that are still `scheduled` and due.
- [ ] Scheduler must re-read reminder state after claim before delivery.
- [ ] Scheduler must never infer a target Node from `created_by_node_id`; creation origin is audit metadata, not routing authority.
- [ ] Add a dedicated target resolver that maps a user/household principal to eligible notification Nodes.
- [ ] Target resolver must consider trust, capability grant, local-auth requirement, and current routing preference.
- [ ] Add delivery-attempt idempotency before retries are enabled.
- [ ] Persist delivery attempts separately from reminder records so schedule state and delivery history do not collapse into one field.

## Security tests still required

- [ ] Real Node registry test: revoke trust after schedule and confirm delivery is denied.
- [ ] Real Node registry test: revoke `notification.local` grant after schedule and confirm delivery is denied.
- [ ] Real Android test: remove OS notification permission immediately before fire time and confirm local delivery denies/fails closed.
- [ ] Real Android test: device offline at fire time must not cause a cloud fallback unless separately designed and authorized.
- [ ] Confirm duplicate capability advertisements fail closed rather than choosing one.
- [ ] Confirm malformed/forged adapter results cannot mark a reminder delivered.
- [ ] Confirm no private reminder/TODO content is emitted to INFO logs during successful or failed delivery.

## Operational record

- [ ] Before enabling any real adapter, update `/status` documentation so operators can distinguish `deny_adapter` from a configured delivery adapter.
- [ ] Document the exact Android version/device matrix used for notification validation.
- [ ] Record notification channel IDs and permission behavior without storing user notification content.
- [ ] Add an operator rollback procedure: revoke Node capability grant and disable the delivery adapter without deleting reminder data.
