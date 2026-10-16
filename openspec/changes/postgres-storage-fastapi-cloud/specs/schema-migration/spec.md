## ADDED Requirements

### Requirement: Schema is upgraded by an explicit, versioned migration step
The database schema SHALL be defined by an ordered series of versioned migrations. The `dishlist db upgrade` command SHALL apply every migration the target database has not yet received, in order, and record the resulting schema version in the database. Running it against an already-current database SHALL make no change and exit successfully.

#### Scenario: Empty database is brought to the current schema
- **WHEN** an operator runs `dishlist db upgrade` against an empty Postgres database
- **THEN** every table the application needs is created, the default dish types, tags and keywords are seeded, and the recorded schema version is the latest

#### Scenario: Upgrade is idempotent
- **WHEN** `dishlist db upgrade` is run a second time against the same database
- **THEN** it reports the database is already current, changes nothing, and exits zero

### Requirement: The server refuses to start against an outdated schema
On startup the application SHALL compare the database's recorded schema version with the latest version it ships. It SHALL NOT apply migrations itself. If the database is behind, or has never been migrated, startup SHALL fail with an error telling the operator to run `dishlist db upgrade`.

#### Scenario: Server started before migrations were applied
- **WHEN** the application starts against a database whose schema version is older than the latest, or that has no schema version
- **THEN** startup fails with a message naming `dishlist db upgrade`, and no request is served

#### Scenario: Server started against a current schema
- **WHEN** the application starts against a database at the latest schema version
- **THEN** startup proceeds normally

### Requirement: Migrations stay compatible with the previous release during rollout
Each migration SHALL leave the schema usable by the previous released version of the application, so that old and new instances can serve requests against the same database while a rollout is in progress. Removing or renaming a column or table that the previous release reads or writes SHALL be split across two releases: the code stops using it in one release, and the schema change follows in a later one.

#### Scenario: Old instance keeps working after an upgrade
- **WHEN** `dishlist db upgrade` for release N has been applied and an instance of release N-1 is still serving
- **THEN** that instance's reads and writes continue to succeed

## REMOVED Requirements

### Requirement: Legacy dish columns are removed at startup
**Reason**: SQLite is no longer supported and existing SQLite data is not carried over, so no database with the legacy `allergens` / `dietary_flags` columns can exist. The schema is no longer changed at startup.
**Migration**: Archive `data/dishlist.db`, set `DATABASE_URL` to a Postgres database, and run `dishlist db upgrade`.

### Requirement: Unsupported SQLite versions fail loudly
**Reason**: SQLite is no longer a supported database.
**Migration**: Use Postgres via `DATABASE_URL`; the compose file provides one for local and self-hosted use.
