# Guarded Tool Execution

HG-053 establishes the server-side safety boundary that must exist before a real Home Assistant or other external-control adapter is enabled.

## Execution path

```text
LLM or UI
  -> inert ProposedAction
  -> ToolProposal (pending_policy)
  -> Tool Registry lookup
  -> ToolPolicyEngine
  -> complete PolicyEvaluationResult
  -> GuardedToolExecutor
  -> server-owned ToolAdapter
  -> external service or device
```

No proposal contains an adapter, callable, credential, Policy rule, risk override, or renderer/device primitive.

## Registry ownership

`ToolRegistry` is a server-owned allow-list of reviewed `ToolDefinition` objects. A Tool definition owns:

- effect (`informational`, `external_read`, `external_write`, `physical_action`)
- risk level
- required actor roles
- required interaction context
- confirmation policy
- audit level
- allowed capabilities and devices
- a bounded argument schema

Unknown tools fail closed. Duplicate names are rejected.

HG-053 intentionally accepts only a conservative JSON Schema subset for arguments. Unsupported schema keywords reject registration instead of being ignored. This prevents a reviewed constraint from silently becoming unenforced at runtime.

## Proposal boundary

`ToolProposal.from_llm_action()` converts the provider-neutral `ProposedAction` into the v1.0 proposal shape while preserving `authorization_status=pending_policy`.

The proposal can carry request/session/node/actor correlation and an optional confirmation identifier, but those values are not treated as authority. Policy compares them with a separately supplied trusted `PolicyEvaluationContext`.

The LLM cannot provide:

- `allowed=true`
- risk level
- required role
- capability grant
- trusted-device state
- Policy version
- adapter identity

## Runtime Hard Policy floors

Configured Tool metadata may be stricter than these rules, never weaker.

| Risk/effect | Minimum runtime confirmation |
| --- | --- |
| low | definition policy |
| medium | contextual |
| high | explicit |
| critical | explicit |
| physical action | contextual |

Contextual confirmation requires the same trusted request to be an explicit user request. Explicit confirmation additionally requires a confirmation ID that appears in trusted server-side confirmation state.

Policy also checks actor/request/session/node correlation, roles, argument schema, granted capabilities, allowed devices, and trusted-device state.

## Executor revalidation

An allow decision is necessary but not sufficient. `GuardedToolExecutor` rejects execution when:

- the Policy decision is incomplete or deny
- proposal IDs differ
- Policy versions differ
- the decision risk does not match the registered definition
- confirmation was downgraded
- argument validation no longer matches
- the decision is from the future or older than the configured freshness window
- the decision ID was already consumed
- no reviewed adapter is configured

The default freshness window is 30 seconds.

A decision ID is consumed before the adapter call. This prevents retries after an uncertain adapter failure from accidentally duplicating an external or physical action.

## Default composition remains deny-only

HG-053 does **not** make `build_core()` capable of controlling household devices. The existing default `UnconfiguredPolicyBoundary` remains deny-only, and no Home Assistant adapter or credential is added.

A future composition must explicitly provide:

1. reviewed Tool definitions,
2. trusted actor/device/capability context,
3. a configured `ToolPolicyEngine`,
4. reviewed adapters,
5. durable confirmation and decision-replay state where required.

The included in-memory replay protector is for development and tests. Production external writes must use durable replay protection so a Core restart cannot make an old allow decision reusable.

## Next Smart Home steps

The safe order after HG-053 is:

1. Device Registry and Capability Registry for approved household devices.
2. Read-only Home Assistant adapter and state tools.
3. Durable audit/decision replay storage.
4. Low-risk explicit light-control tool with end-to-end confirmation and adapter tests.
5. Broader Home Assistant capabilities only after each risk policy is reviewed.

Do not add a generic Home Assistant service-call tool. Expose narrow reviewed capabilities as individual Tool definitions instead.
