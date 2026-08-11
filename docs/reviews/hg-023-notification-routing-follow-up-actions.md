# HG-023 Notification Routing Follow-up Actions

Status: explicit routing configuration is implemented; no scheduler or Android notification transport is enabled by this work.

## Implemented boundary

- [x] Reminder creation origin is not used as notification routing authority.
- [x] Notification routing uses an explicit `(scope, scope_id) -> node_id` mapping.
- [x] Default resolver is deny-only.
- [x] Development startup accepts repeatable `--notification-target SCOPE:SCOPE_ID=NODE_ID` bindings.
- [x] Only `user` and `household` scopes are accepted.
- [x] Duplicate principal routes are rejected at startup.
- [x] One Node cannot currently be assigned to more than one principal route.
- [x] Invalid Node identifiers fail startup configuration parsing.
- [x] Core status distinguishes configured routing from deny-only routing.
- [x] Routing does not imply Node trust, capability grant, Policy allow, or Android local authorization.

## Deliberately NOT implemented

- [ ] No automatic inference from `created_by_node_id`, IP address, mTLS identity, last active Node, presence sensor, or conversation origin.
- [ ] No fan-out to multiple personal devices.
- [ ] No household presence-based routing.
- [ ] No fallback route when an explicitly configured Node is unavailable.
- [ ] No scheduler consumes this resolver yet.
- [ ] No routing preference is writable by an LLM.
- [ ] No Android notification transport is enabled.

## Operator actions

- [ ] Decide the stable production Node IDs before enabling routes.
- [ ] For a personal phone, configure a route only after the Node is enrolled, trusted, and later granted the reviewed notification capability.
- [ ] For household routes, do not reuse a personal Node until household ownership/privacy semantics are explicitly reviewed.
- [ ] Keep routing values in deployment configuration, not prompts or application logs.
- [ ] Verify `/status` reports `notification_routing=explicit_principal_to_node` only when routes were intentionally supplied.

## Scheduler integration follow-up

- [ ] Resolve the reminder owner principal from the persisted reminder itself, then call the target resolver.
- [ ] Re-read authoritative Node trust/capability state immediately before delivery.
- [ ] If no target exists, leave a delivery-attempt reason such as `notification_target_unconfigured`; do not infer another device.
- [ ] Never use `created_by_node_id` as an implicit target, even if it matches a configured route today.
- [ ] Add claim/lease and idempotency before multiple Core instances may schedule delivery.

## Future routing product work

- [ ] Add an administrator/server UI for viewing and changing routes without exposing private reminder content.
- [ ] Consider multi-device fan-out only with explicit ordering/fallback semantics.
- [ ] Define household routing based on administrator configuration first; presence-aware routing requires a separate privacy review.
- [ ] Add audit events for route changes without recording reminder text.
- [ ] Add immediate route revocation that prevents future delivery without deleting reminder schedules.
