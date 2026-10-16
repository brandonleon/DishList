# cli-management Specification

## Purpose
Lets an operator run the server and manage configuration, dietary tags, events and metrics from the command line, without needing the web admin panel enabled.
## Requirements
### Requirement: CLI can start the web server
The `dishlist serve` command SHALL start the FastAPI app under uvicorn with configurable `--host`/`--port`, proxy headers enabled, and live reload on by default unless disabled via `--no-reload` or the `DISHLIST_RELOAD` environment variable.

#### Scenario: Reload blocked by the platform
- **WHEN** live reload is requested but the platform raises a `PermissionError` on startup
- **THEN** the CLI logs a warning and restarts uvicorn without reload rather than crashing

### Requirement: CLI manages the same configuration as web admin, without requiring it enabled
The `dishlist admin` command group SHALL let an operator view status and manage the admin network allowlist, default dish types, dietary tag library, events, and metrics settings entirely from the command line, independent of whether `web_admin_enabled` is true.

#### Scenario: Enabling web admin from the CLI
- **WHEN** an operator runs `dishlist admin web enable --network <cidr>`
- **THEN** the network is added to the allowlist (if not already present) and `web_admin_enabled` is set to true; if no networks are configured and none is supplied, the command SHALL fail instead of enabling an inaccessible panel

### Requirement: CLI can signal a running server to reload config live
The `dishlist admin reload` command SHALL send `SIGUSR1` to the server process identified by the PID recorded in `data/dishlist.pid`, causing that process to reload its in-memory config from the persisted store.

#### Scenario: No server running
- **WHEN** `dishlist admin reload` is run and no PID file exists, or the recorded PID is no longer a live process
- **THEN** the command reports the failure and exits non-zero rather than silently doing nothing

### Requirement: CLI can recover a lost management link
The `dishlist admin events token <event_id>` command SHALL print the management path (`/manage/{token}`) for a given event ID so a host who lost their link can be given a new one.

#### Scenario: Unknown event ID
- **WHEN** the supplied event ID does not exist
- **THEN** the command reports an error and exits non-zero

### Requirement: Destructive CLI tag and event operations require confirmation
The `dishlist admin tags reset` and `dishlist admin events delete <id>` commands SHALL require explicit interactive confirmation before executing, since both are irreversible (clearing all tag associations, or deleting an event and its dishes, respectively).

#### Scenario: Confirmation declined
- **WHEN** an operator runs `dishlist admin tags reset` or `dishlist admin events delete <id>` and declines the confirmation prompt
- **THEN** the command aborts without modifying any data

