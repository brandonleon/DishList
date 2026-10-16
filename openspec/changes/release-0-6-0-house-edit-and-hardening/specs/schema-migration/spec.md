## Purpose

Keeps databases created by older DishList releases working after an upgrade by bringing their schema in line with the current one at startup, so an upgrade never requires the operator to hand-edit or recreate the database.

## ADDED Requirements

### Requirement: Legacy dish columns are removed at startup
When the application initializes its database and the `dishes` table still contains the legacy `allergens` or `dietary_flags` columns, the system SHALL remove those columns while preserving every existing dish row and every dish's tag associations. Initialization SHALL be idempotent: running it again on an already-current database SHALL make no schema change.

#### Scenario: Old database is upgraded in place
- **WHEN** the application starts against a database whose `dishes` table has `allergens` and `dietary_flags` columns (both `NOT NULL` with no default) and contains dishes with tag associations
- **THEN** both columns are removed, all dishes keep their id, event, contributor, name, type, notes, host flag and timestamp, and all tag associations remain

#### Scenario: New dishes can be added after the upgrade
- **WHEN** a dish is added to an upgraded database
- **THEN** the insert succeeds and the dish appears on the event's pages

#### Scenario: Current database is untouched
- **WHEN** the application starts against a database that has no legacy dish columns
- **THEN** initialization changes nothing in the `dishes` table

### Requirement: Unsupported SQLite versions fail loudly
If the legacy columns must be removed but the SQLite library does not support dropping columns, the system SHALL stop startup with an error that names the required SQLite version, rather than continuing with a schema that rejects every new dish.

#### Scenario: SQLite too old to drop columns
- **WHEN** legacy columns are present and the SQLite library version is older than 3.35.0
- **THEN** startup fails with a message stating that SQLite 3.35.0 or newer is required
