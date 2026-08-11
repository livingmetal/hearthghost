# HG-018 PostgreSQL Migration Follow-up Actions

Status: schema-versioning implementation and operator validation checklist.

## Before production adoption

- [ ] Take a verified backup of the existing `hearthghost` PostgreSQL database before first startup with the migration-enabled build.
- [ ] Confirm the existing `memory_records` and `todo_records` tables match the v1/v2 definitions before allowing the migration table to adopt them.
- [ ] Run the migration-enabled build against a staging/restored copy first and verify `hearthghost_schema_migrations` contains exactly:
  - `1 / memory_records_v1`
  - `2 / todo_records_v1`
- [ ] Verify a second startup performs no schema changes and reports the same latest version.
- [ ] Verify simultaneous startup of two HearthGhost processes serializes through the PostgreSQL advisory transaction lock.

## Operational rules

- [ ] Do not edit rows in `hearthghost_schema_migrations` manually to make a failed deployment appear current.
- [ ] Do not downgrade an application build after a newer schema version has been applied unless a documented backward-compatible path exists.
- [ ] If the database reports a schema version newer than the application understands, keep the application stopped and deploy a compatible build rather than deleting migration metadata.
- [ ] Treat failed DDL as a failed deployment. Restore/fix forward from a verified backup rather than partially editing tables by hand.

## Engineering follow-up

- [x] Serialize migrations with `pg_advisory_xact_lock` inside the migration transaction.
- [x] Reject known-version/name mismatches, gaps, malformed metadata, and future schema versions.
- [x] Make current memory/todo table creation idempotent so an existing MVP database can be adopted non-destructively.
- [ ] Add a real PostgreSQL migration integration test in CI; current migration tests use a fake connector to validate ordering and fail-closed behavior.
- [ ] Add a read-only startup/status field that exposes only the current schema version, never the DSN or database credentials.
- [ ] Define whether future destructive migrations require an explicit maintenance-mode flag.
- [ ] Add release documentation for every new migration before adding due-date/reminder/calendar columns.
