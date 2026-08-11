# HG-028 Scoped Behavior Preferences Follow-up Actions

Status: implementation in progress. This review file is created at branch start so architectural findings and operator actions are not lost while the scoped persistence work is being developed.

## Problem being corrected

- [ ] Current Behavior Preference proposals carry `scope` and `scope_id`, but the runtime `BehaviorPreferenceManager` mutates one global Persona/follow-up timeout. This must not be presented as user/household-scoped behavior until the runtime also resolves preferences by principal scope.
- [ ] Persisting the existing global behavior directly to PostgreSQL would preserve the wrong authority model. Fix scope semantics before treating preferences as durable.

## Target invariants

- [ ] PostgreSQL stores behavior preferences by exact `(scope, scope_id)`.
- [ ] Behavior updates use optimistic revision control and atomic writes.
- [ ] Defaults remain code-defined when no scoped record exists.
- [ ] A Node must resolve to an approved conversation principal before reading or changing scoped preferences.
- [ ] A user-scoped preference never mutates another user or household record.
- [ ] Persona selection for an LLM turn uses the effective principal-scoped snapshot, not a mutable process-global Persona.
- [ ] Character display profile uses the same effective scoped snapshot as the LLM prompt.
- [ ] Follow-up timeout becomes a property of the conversation session rather than mutable process-global state.
- [ ] Hard Policy, Node trust, capabilities, credentials, provider configuration, and tool authority remain unrepresentable.

## Operator actions after implementation

- [ ] Back up the HearthGhost PostgreSQL database before the first schema migration containing behavior preference tables.
- [ ] Verify the migration version and table constraints on the real PostgreSQL instance.
- [ ] Bind only personal Nodes to `user` principals and deliberate shared Nodes to `household` principals.
- [ ] Test two distinct principals and prove that name/verbosity/follow-up changes do not cross scopes.
- [ ] Decide whether household defaults may be inherited by user scope in a later release. Initial implementation should avoid implicit inheritance.

## Physical Android checks

- [ ] Change a character name from the real Android Node and confirm only that principal sees the new display name.
- [ ] Restart Core and confirm the scoped name/behavior survives via PostgreSQL.
- [ ] Confirm an unbound Node cannot read or change the persisted profile.
- [ ] Confirm a reconnect/new conversation receives the same persisted display profile.

## Stop / rollback principle

If scoped resolution cannot be made consistent across prompt Persona, display profile, and conversation timeout, do not fall back to a global mutable preference. Keep defaults and deny scoped mutation until the model is consistent.
