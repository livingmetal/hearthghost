# PostgreSQL production persistence

HearthGhost production persistence uses the existing PostgreSQL service. SQLite remains a development/test fallback only.

## Database and role

Run the following as a PostgreSQL administrator, substituting a generated password for the placeholder. Do not reuse the PostgreSQL superuser from HearthGhost.

```sql
CREATE ROLE hearthghost LOGIN PASSWORD '<GENERATE_A_LONG_RANDOM_PASSWORD>';
CREATE DATABASE hearthghost OWNER hearthghost TEMPLATE template0 ENCODING 'UTF8';
REVOKE ALL ON DATABASE hearthghost FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE hearthghost TO hearthghost;
```

After connecting to the `hearthghost` database as an administrator:

```sql
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO hearthghost;
```

The application role should own only the HearthGhost database/schema. Do not grant `CREATEDB`, `CREATEROLE`, `REPLICATION`, or superuser privileges.

## DSN secret

Store the connection string as a root-managed or Podman secret, not in the repository, image, command line, or environment value.

Example secret content:

```text
postgresql://hearthghost:<PASSWORD>@<POSTGRES_HOST>:5432/hearthghost?sslmode=require
```

The expected mounted path is `/run/secrets/hearthghost-postgres-dsn`. `sslmode=require` is the minimum for a networked database. If the PostgreSQL server has a locally trusted CA, prefer `sslmode=verify-full` with the CA mounted into the container.

## Schema bootstrap

The PostgreSQL repository creates its application tables and indexes with `CREATE TABLE/INDEX IF NOT EXISTS` while connected as the dedicated `hearthghost` role. This is acceptable for the current single-service MVP. Before multiple production instances or independent deployment lifecycles, replace startup DDL with versioned migrations.

Current memory table:

- `memory_records`: explicit addressed-text long-term memory only
- exact `(scope, scope_id)` reads
- PostgreSQL `TIMESTAMPTZ` for creation times
- UUID primary key

Notes and TODOs will use the same dedicated HearthGhost database but separate tables.

## Backup and restore

Include the `hearthghost` database in the existing PostgreSQL backup policy. Before enabling sensitive household memory, verify both backup encryption and restore testing. Memory deletion semantics must eventually account for retained backups; see the HG-016 follow-up review.

## Required operator actions

- Create the `hearthghost` role and database.
- Generate a unique password and store the DSN as a Podman secret.
- Confirm PostgreSQL TLS and prefer certificate verification when a trusted CA is available.
- Add the database to backup/restore checks.
- Do not expose PostgreSQL to the public Internet merely for HearthGhost.
