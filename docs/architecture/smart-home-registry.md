# Smart Home Device and Capability Registry

HG-054 separates smart-home discovery from trust and Tool exposure.

## Why this is separate from the Node Registry

HearthGhost Nodes are phones, tablets, and future sensing/interaction endpoints that authenticate to Core. Smart-home devices are external targets reached through an adapter such as Home Assistant. They have different identities and trust lifecycles.

```text
Node Registry
  -> Who may connect to HearthGhost and which Node capabilities are granted?

Smart Home Device Registry
  -> Which external household devices are known, trusted, and approved for which reviewed capabilities?
```

Neither registry implies the other.

## Discovery is not onboarding

An adapter may report a `DeviceObservation`, but observation creates an `UNTRUSTED` record with zero approved capabilities.

```text
Home Assistant discovery
  -> DeviceObservation
  -> UNTRUSTED device
  -> zero approved capabilities
```

A discovered device does not become Tool-visible because it is on the LAN, because Home Assistant knows it, or because it advertises a familiar entity class.

## Reviewed Capability Registry

The global `CapabilityRegistry` is a server-owned catalog of capabilities HearthGhost understands and has reviewed, for example:

```text
home.light.read
home.light.write
sensor.temperature.read
```

A device may advertise unknown capability strings. They remain observations only and cannot be granted until a matching reviewed `CapabilityDefinition` exists.

This lets discovery retain useful evidence without treating new adapter metadata as authority.

## Administrator lifecycle

Smart-home administration is action-specific:

1. `device.trust`
2. `device.capability.grant`
3. `device.capability.revoke`
4. `device.revoke`

Every mutation requires a `DeviceAdministratorAuthorizer` to return evidence bound to the exact action and device ID. The default authorizer denies everything.

Trust and capability grant are intentionally separate. Trusting a device grants zero capabilities.

Capability grant requires all of:

- the device is trusted,
- the capability is currently advertised,
- the capability exists in the reviewed Capability Registry,
- the administrative request has the current revision,
- the administrator is authorized for the exact mutation.

Administration uses operation IDs and optimistic revisions to reject ambiguous replay and concurrent stale mutations.

## Rediscovery safety

Rediscovery may update display/area metadata and advertised capabilities, but it cannot add trust or approval.

If a new capability appears on an already trusted device, it is not automatically approved.

If an approved capability disappears from the device advertisement, the approval is removed automatically. Loss of capability fails toward less authority.

A revoked device stays revoked across rediscovery and cannot be restored by the ordinary trust action. Future restoration, if needed, should be a distinct reviewed administrator workflow.

## Policy integration

`SmartHomePolicyContextResolver` combines trusted user/session facts with Device Registry facts. It is the bridge into HG-053 Policy evaluation.

For a proposal containing `device_id`, only a trusted registry record contributes:

- that device ID to `trusted_device_ids`,
- its explicitly approved capabilities to `granted_capabilities`.

An untrusted, unknown, or revoked target contributes neither.

The resulting path is:

```text
LLM ProposedAction
  -> pending ToolProposal
  -> trusted user/session context
  + Smart Home Device Registry facts
  -> ToolPolicyEngine
  -> GuardedToolExecutor
  -> reviewed adapter
```

## Home Assistant next step

A Home Assistant adapter should initially provide discovery and **read-only state access**. It should not receive a generic unrestricted service-call Tool.

Recommended first capabilities:

```text
home.entity.read
home.light.read
sensor.temperature.read
sensor.humidity.read
```

Only after discovery/trust/audit behavior is proven should a narrow `home.light.write` Tool be enabled for explicitly approved devices.
