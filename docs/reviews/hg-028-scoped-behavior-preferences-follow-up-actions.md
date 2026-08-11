# HG-028 Scoped Behavior Preferences Follow-up Actions

Status: software implementation complete and CI green. Real PostgreSQL migration and physical Android scope/restart checks remain operator actions.

## Corrected architectural issue

- [x] Removed the prior mismatch where proposals carried `scope`/`scope_id` but runtime mutation targeted one process-global Persona/follow-up timeout.
- [x] Scope semantics were corrected before durable PostgreSQL behavior was enabled.

## Implemented invariants

- [x] PostgreSQL stores behavior preferences by exact `(scope, scope_id)`.
- [x] Behavior updates use optimistic revision control and atomic writes.
- [x] Defaults remain code-defined when no scoped record exists.
- [x] A Node must resolve to an approved conversation principal before reading or changing scoped preferences.
- [x] A user-scoped preference never mutates another user or household record.
- [x] Persona selection for an LLM turn uses the effective principal-scoped snapshot, not a mutable process-global Persona.
- [x] Character display profile uses the same effective scoped snapshot as the LLM prompt.
- [x] Follow-up timeout is captured per conversation session rather than shared as mutable process-global state.
- [x] A successful timeout preference can update that principal's current active conversation without changing other sessions.
- [x] Hard Policy, Node trust, capabilities, credentials, provider configuration, and tool authority remain unrepresentable.
- [x] PostgreSQL migration v5 creates `behavior_preference_records` with exact-scope PK, revision, updater Node and timezone-aware audit time.
- [x] PostgreSQL access uses parameter binding and redacts DSNs from repository repr output.
- [x] CI run #48 passed Python security/runtime tests, TypeScript/client tests, and Android unit/lint/debug APK build.

## Operator actions on the home PostgreSQL instance

- [ ] Back up the HearthGhost PostgreSQL database before first applying migration v5 or later.
- [ ] Verify `hearthghost_schema_migrations` contains `5 / behavior_preference_records_v1` after deployment.
- [ ] Verify the `behavior_preference_records` constraints, PK `(scope, scope_id)`, revision and `TIMESTAMPTZ` audit column.
- [ ] Bind only personal Nodes to `user` principals and deliberate shared Nodes to `household` principals.
- [ ] Test two distinct principals and prove name/verbosity/follow-up changes do not cross scopes.
- [ ] Decide whether household defaults may ever be inherited by user scope. Current implementation intentionally has no implicit inheritance.

## Physical Android checks

- [ ] Change a character name from the real Android Node and confirm only that principal sees the new display name.
- [ ] Restart Core and confirm the scoped name/behavior survives via PostgreSQL.
- [ ] Confirm an unbound Node cannot read or change the persisted profile.
- [ ] Confirm reconnect/new conversation receives the same persisted display profile.
- [ ] Verify a 30-second follow-up preference affects the correct conversation only on two simultaneously connected test Nodes.

## Stop / rollback principle

If scoped resolution ever becomes inconsistent across LLM Persona, display profile, and conversation timeout, do not fall back to a global mutable preference. Use code defaults and deny scoped mutation until the exact-principal model is restored.
