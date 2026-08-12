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
- replay protection is unavailable
- no reviewed adapter is configured

The default freshness window is 30 seconds.

A decision ID is consumed before the adapter call. This prevents retries after an uncertain adapter failure from accidentally duplicating an external or physical action.

## Durable decision replay

HG-056 adds PostgreSQL migration 8 and `PostgresDecisionReplayProtector`. The database owns a unique row per consumed Policy decision:

```text
tool_policy_decision_consumptions
  decision_id UUID PRIMARY KEY
  consumed_at TIMESTAMPTZ
```

Consumption uses `INSERT ... ON CONFLICT DO NOTHING ... RETURNING`, so multiple Core processes sharing one PostgreSQL database cannot both consume the same decision ID. A newly started Core instance sees the same ledger and therefore cannot reuse an old decision simply because process memory was reset.

The table intentionally does not store conversation text, Tool arguments, Home Assistant credentials, or provider payloads. It is a narrow security ledger rather than a dialogue log.

If the PostgreSQL replay boundary raises an error, `GuardedToolExecutor` returns `replay_protection_unavailable` and does not call the Tool adapter. Database availability therefore fails toward less execution authority.

`InMemoryDecisionReplayProtector` remains appropriate for isolated unit tests and development-only read paths. External writes and physical actions should use durable replay protection.

## Default composition remains deny-only

HG-053 does **not** make `build_core()` capable of controlling household devices. The existing default `UnconfiguredPolicyBoundary` remains deny-only, and no Home Assistant write credential or control adapter is added by this execution foundation.

A future composition must explicitly provide:

1. reviewed Tool definitions,
2. trusted actor/device/capability context,
3. a configured `ToolPolicyEngine`,
4. reviewed adapters,
5. durable confirmation and decision-replay state where required.

## Next Smart Home steps

The safe order is:

1. Device Registry and Capability Registry for approved household devices.
2. Read-only Home Assistant adapter and state tools.
3. Durable decision replay storage.
4. Persist Smart Home trust/capability administration state and add security audit records.
5. Add one low-risk explicit light-control Tool with end-to-end confirmation and adapter tests.
6. Broader Home Assistant capabilities only after each risk policy is reviewed.

Do not add a generic Home Assistant service-call tool. Expose narrow reviewed capabilities as individual Tool definitions instead.
