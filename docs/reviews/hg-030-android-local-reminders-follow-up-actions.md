# HG-030 Android Local Reminder Follow-up Actions

Status: implementation in progress. The local-reminder path is designed around outbound Android mTLS sync rather than assuming Core can open an inbound connection to a sleeping phone.

## Architecture invariants

- [ ] Android requests reminder sync over the existing authenticated Node channel.
- [ ] Sync requires the exact `notification.local` Node capability, not merely `conversation.text`.
- [ ] Server resolves the authenticated Node to a principal and then confirms that the explicit principal-to-notification-Node route points back to the requesting Node.
- [ ] Server returns only `reminder_id` and `fire_at`; TODO text, Memory, Persona, credentials and policy data never enter the schedule payload.
- [ ] Android schedules only after local OS notification permission is granted.
- [ ] Notification title/body remain fixed redacted values (`HearthGhost` / `Reminder`).
- [ ] Local schedule reconciliation is idempotent by exact `(reminder_id, fire_at)` identity.
- [ ] Removed/cancelled server reminders are cancelled locally on the next successful sync.
- [ ] Local persisted schedule metadata contains no private reminder text.
- [ ] Reboot recovery restores only still-future redacted local alarms from local schedule metadata.
- [ ] Sync does not mark server delivery as completed; local scheduling and due-delivery accounting remain separate semantics.

## Android permission/timing choice

Initial implementation should use `POST_NOTIFICATIONS` runtime permission on Android 13+ and inexact `AlarmManager.setAndAllowWhileIdle()` rather than demanding exact-alarm special access. Physical testing must measure whether the timing tolerance is acceptable before considering exact-alarm permission.

## Physical Android checks

- [ ] Grant and deny notification permission and verify fail-closed behavior.
- [ ] Enroll/grant `notification.local` and prove an ungranted Node cannot sync schedules.
- [ ] Verify an authenticated but incorrectly routed Node receives no reminder list.
- [ ] Schedule a reminder, background/kill the app, and confirm the OS notification still appears.
- [ ] Reboot the phone and confirm future redacted alarms are restored.
- [ ] Cancel/change a reminder on Core, reconnect/sync, and confirm local alarm reconciliation.
- [ ] Confirm duplicate syncs do not produce duplicate notifications.
- [ ] Verify Samsung Wallet/vehicle apps remain unaffected by this local reminder path and split-tunnel configuration.
- [ ] Measure actual inexact alarm lateness with Doze/battery saver enabled.

## Future exact-alarm gate

Do not add `SCHEDULE_EXACT_ALARM`/`USE_EXACT_ALARM` solely for convenience. Add exact scheduling only if measured inexact timing is unacceptable for the intended reminder UX and the user explicitly accepts the additional special-access/policy surface.
