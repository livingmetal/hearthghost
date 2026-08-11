# HG-016 memory follow-up actions

Status: explicit scoped text memory foundation implemented; production-grade identity assurance, retention, encryption, and user management remain open.

## Implemented safeguards

- [x] Long-term memory accepts only explicitly requested addressed text.
- [x] Raw audio, images, video, sensor observations, and pre-attention material are not representable as memory candidates.
- [x] Node identity is not implicitly treated as human identity.
- [x] User memory requires an administrator-provisioned personal-Node binding.
- [x] Household memory requires an administrator-provisioned household-Node binding.
- [x] Unknown, shared-without-binding, ambiguous, or resolver-failure cases fail closed.
- [x] Explicit memory commands are intercepted locally before the LLM path.
- [x] A failed or unresolved explicit memory request is not forwarded to the cloud model.
- [x] SQLite retrieval and deletion are exact-scope operations.
- [x] Persistent memory DB requires an owner-only parent directory and a non-symlink DB path; DB file mode is forced to `0600`.
- [x] Development server enables persistence and Node-principal bindings only through explicit startup options.

## Required before sensitive household memory

- [ ] Decide at-rest encryption strategy. Current SQLite storage is permission-protected but not application-level encrypted. Prefer encrypted host volume or reviewed SQLCipher-equivalent design before storing sensitive material.
- [ ] Define retention policy and maximum record/count/storage limits per user and household.
- [ ] Define backup/restore behavior, including whether memory backups are encrypted separately and how deletion propagates to backups.
- [ ] Add an audit record for create/delete operations without copying memory plaintext into the audit log.
- [ ] Define export and complete-erasure flows for a user or household.
- [ ] Decide whether personal-Node binding is sufficient assurance for the owner's phone. It proves the device identity, not the current speaker. Shared devices must not receive a user binding without an additional human-authentication design.
- [ ] Add principal-binding administration through an authenticated local administrator path instead of relying only on development startup arguments.

## Product work after foundation

- [ ] Add deterministic user-facing list/forget commands within the resolved scope.
- [ ] Add note and todo types without broadening the memory capture rules.
- [ ] Add bounded lexical retrieval first; do not introduce embeddings until scope filtering occurs before embedding lookup and privacy implications are reviewed.
- [ ] Add memory context injection to the LLM only after retrieval is scope-bound, size-bounded, and clearly marked as untrusted historical data.
- [ ] Add conflict/update semantics so newer memories do not silently overwrite older facts.
- [ ] Add expiration for temporary memories and completed todos.

## Physical/integration validation

- [ ] Run the personal Android Node with an explicit `user` binding and confirm `기억해:` stores only in that user scope.
- [ ] Confirm the same command from an unbound Node receives a local failure response and produces no LLM request.
- [ ] Restart Core and verify SQLite-backed memory survives restart when `--memory-db` is configured.
- [ ] Verify DB and directory permissions on the actual WTR PRO host/container volume.
