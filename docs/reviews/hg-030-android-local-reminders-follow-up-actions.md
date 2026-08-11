# HG-030 Android Local Reminder Follow-up Actions

Status: software implementation complete and CI build/test steps are green. Physical Android notification timing, permission, reboot, routing and split-tunnel behavior remain device checks.

## Implemented architecture invariants

- [x] Android requests reminder sync over a dedicated one-shot outbound mTLS Node session using the existing Android Keystore identity.
- [x] Sync requires the exact `notification.local` Node capability, not merely `conversation.text`.
- [x] Server resolves the authenticated Node to a principal and then confirms that the explicit principal-to-notification-Node route points back to the requesting Node.
- [x] Server returns only `reminder_id` and `fire_at`; TODO text, Memory, Persona, credentials and policy data never enter the schedule payload.
- [x] Android schedules only after local OS notification permission is granted.
- [x] Notification permission is requested only after a recent foreground user interaction; it is never auto-prompted at startup/foreground sync.
- [x] Notification title/body remain fixed redacted values (`HearthGhost` / `Reminder`).
- [x] Local schedule reconciliation is idempotent by exact reminder identity/time and removes changed/cancelled schedules on successful sync.
- [x] Local persisted schedule metadata contains only reminder UUID and due epoch time, not private reminder text.
- [x] Reboot recovery restores only still-future redacted local alarms from local schedule metadata.
- [x] Sync does not mark server delivery as completed; local scheduling and server claim/delivery accounting remain separate semantics.
- [x] Initial OS scheduling uses `AlarmManager.setAndAllowWhileIdle()` and does not request exact-alarm special access.
- [x] Android 13+ notification permission and reboot receiver permissions are explicitly allowlisted by security tests.
- [x] Alarm/boot receivers are not exported.
- [x] Server and Android static/privacy tests cover redaction, exact protocol fields, route mismatch, permission gate and no exact-alarm permission.
- [x] CI run #52 Python and TypeScript/client jobs passed. Android build, lint, debug APK and offline image verification steps also completed successfully; GitHub job finalization was still being reported as in-progress at the last connector poll despite all job steps being successful.

## Operational prerequisite discovered during implementation

`notification.local` cannot be granted through the normal NodeAdministration path until the Node registry contains a matching capability advertisement. The current Node transport has no client capability-advertisement command. HG-031 must therefore provide an authenticated administrator-controlled advertisement registration path (or a later attested Node advertisement protocol) before treating `notification.local` enrollment as operationally complete.

## Android permission/timing choice

The initial implementation uses `POST_NOTIFICATIONS` runtime permission on Android 13+ and inexact `AlarmManager.setAndAllowWhileIdle()` rather than demanding exact-alarm special access. Physical testing must measure whether the timing tolerance is acceptable before considering exact-alarm permission.

## Physical Android checks

- [ ] Grant and deny notification permission and verify fail-closed behavior.
- [ ] Register/grant `notification.local` through the reviewed administrator path and prove an ungranted Node cannot sync schedules.
- [ ] Verify an authenticated but incorrectly routed Node receives no reminder list.
- [ ] Schedule a reminder, background/kill the app, and confirm the OS notification still appears.
- [ ] Reboot the phone and confirm future redacted alarms are restored.
- [ ] Cancel/change a reminder on Core, reconnect/sync, and confirm local alarm reconciliation.
- [ ] Confirm duplicate syncs do not produce duplicate notifications.
- [ ] Verify Samsung Wallet/vehicle apps remain unaffected by this local reminder path and split-tunnel configuration.
- [ ] Measure actual inexact alarm lateness with Doze/battery saver enabled.
- [ ] Confirm the one-shot reminder sync does not disturb an active text conversation Node session.

## Future exact-alarm gate

Do not add `SCHEDULE_EXACT_ALARM`/`USE_EXACT_ALARM` solely for convenience. Add exact scheduling only if measured inexact timing is unacceptable for the intended reminder UX and the user explicitly accepts the additional special-access/policy surface.
