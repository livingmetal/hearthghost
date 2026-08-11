# HG-016 follow-up actions

## Operator actions required

- [ ] Create dedicated PostgreSQL role `hearthghost` without superuser, CREATEDB, CREATEROLE, or REPLICATION privileges.
- [ ] Create dedicated database `hearthghost` owned by that role.
- [ ] Generate a unique long random password and store the full DSN as a Podman secret mounted at `/run/secrets/hearthghost-postgres-dsn`.
- [ ] Keep PostgreSQL off the public Internet. Permit only the HearthGhost host/network path that is actually required.
- [ ] Use PostgreSQL TLS. Minimum is `sslmode=require`; prefer `verify-full` when the local PostgreSQL CA is available to the container.
- [ ] Add the `hearthghost` database to the existing backup policy and perform an actual restore test.
- [ ] Provision explicit memory principals for personal/household Nodes. A trusted Node is not automatically a human identity.

See `docs/deployment/postgresql.md` for bootstrap SQL and deployment guidance.

## Engineering follow-ups

- [ ] Replace startup `CREATE TABLE IF NOT EXISTS` DDL with versioned migrations before multi-instance production deployment.
- [ ] Add PostgreSQL integration CI against an ephemeral PostgreSQL service; current adapter unit tests must not require a live household database.
- [ ] Define retention, export, delete, and backup-erasure semantics for household memory.
- [ ] Decide whether sensitive memory requires application-level encryption in addition to PostgreSQL/storage encryption.
- [ ] Add audit events for memory create/read/delete without logging memory plaintext.
- [ ] Add connection pooling only after concurrency measurements justify it; do not add a pool merely because Psycopg supports one.
- [ ] Keep SQLite only as an offline development/test fallback. PostgreSQL is the production backend for this deployment.
