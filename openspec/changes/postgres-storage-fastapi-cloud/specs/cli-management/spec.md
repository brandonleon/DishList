## ADDED Requirements

### Requirement: CLI applies database migrations
The `dishlist db upgrade` command SHALL apply pending schema migrations to the database named by `DATABASE_URL`, report the schema version before and after, and exit non-zero if any migration fails, leaving the database at the last version that applied cleanly.

#### Scenario: Migration failure
- **WHEN** a migration raises an error during `dishlist db upgrade`
- **THEN** the command reports the failing migration and exits non-zero, and the database's recorded version is the last one that completed

### Requirement: CLI commands target the database named by DATABASE_URL
Every `dishlist` command that reads or writes data SHALL connect to the Postgres database given by the `DATABASE_URL` environment variable, so an operator can manage a remote deployment (for example FastAPI Cloud with Neon) from their own machine. When `DATABASE_URL` is unset or empty, these commands SHALL fail with an error naming the variable instead of falling back to a local file.

#### Scenario: Managing a remote deployment
- **WHEN** an operator runs `DATABASE_URL=<remote url> dishlist admin web enable --network <cidr>`
- **THEN** the change is written to the remote database and every running instance of that deployment applies it within the config refresh interval

#### Scenario: DATABASE_URL missing
- **WHEN** an operator runs `dishlist admin status` with `DATABASE_URL` unset
- **THEN** the command exits non-zero with a message that `DATABASE_URL` must be set

## REMOVED Requirements

### Requirement: CLI can signal a running server to reload config live
**Reason**: Running instances now re-read configuration from the database on a short interval, which also works across several instances and remote deployments where a PID file and signal cannot reach the server.
**Migration**: No action needed; changes made with `dishlist admin` apply automatically within the refresh interval. To apply one immediately on a single instance, use `POST /pantry-admin/reload`.
