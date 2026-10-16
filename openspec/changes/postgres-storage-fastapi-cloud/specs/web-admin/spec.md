## ADDED Requirements

### Requirement: Configuration changes reach every running instance
Each running instance SHALL serve requests using configuration that is at most 10 seconds older than the configuration persisted in the database. A change saved through web admin SHALL take effect immediately on the instance that saved it and within that bound on every other instance, without a restart or manual reload.

#### Scenario: Change saved on another instance
- **WHEN** an admin disables web admin through one instance while a second instance is also serving
- **THEN** within 10 seconds the second instance responds to `/pantry-admin` as disabled

#### Scenario: Change made from the CLI
- **WHEN** an operator changes the admin network allowlist with `dishlist admin networks add` against the deployment's database
- **THEN** within 10 seconds every running instance enforces the new allowlist

## MODIFIED Requirements

### Requirement: Admin panel can force a live config reload
The system SHALL let an authorized admin re-read the persisted configuration into the serving instance's in-memory state via `POST /pantry-admin/reload`, without restarting the process and without waiting for the regular refresh interval.

#### Scenario: Reload picks up out-of-band changes
- **WHEN** the configuration was changed directly in the database (e.g. by the CLI) and an admin then triggers `/pantry-admin/reload`
- **THEN** subsequent requests to that instance use the newly persisted configuration immediately
