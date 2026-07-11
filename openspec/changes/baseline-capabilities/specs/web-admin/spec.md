## ADDED Requirements

### Requirement: Web admin panel is disabled by default and IP-gated
The system SHALL reject all requests to `/pantry-admin` and its sub-paths with HTTP 404 whenever `web_admin_enabled` is false, regardless of caller IP. When enabled, the system SHALL additionally require the caller's IP to fall within one of the configured `admin_networks` CIDR ranges, responding HTTP 403 otherwise.

#### Scenario: Disabled panel hides its existence
- **WHEN** `web_admin_enabled` is false and any client requests `/pantry-admin`
- **THEN** the system responds with HTTP 404, not 403

#### Scenario: Enabled panel blocks disallowed IPs
- **WHEN** `web_admin_enabled` is true and the requesting IP is not within any configured admin network
- **THEN** the system responds with HTTP 403

### Requirement: Admin panel manages dish types and network allowlists
The system SHALL let an authorized admin update, via `POST /pantry-admin`, the default dish-type list, the admin IP allowlist, and the metrics IP allowlist. At least one dish type and one admin network SHALL be required; submitting neither SHALL be rejected with HTTP 400.

#### Scenario: Empty network list rejected
- **WHEN** an authorized admin submits the settings form with no admin networks listed
- **THEN** the system responds with HTTP 400 and leaves the stored configuration unchanged

### Requirement: Admin panel manages the dietary tag library
The system SHALL expose tag management at `GET /pantry-admin/tags` and support add, update, delete, visibility-toggle, and reset-to-defaults actions under `/pantry-admin/tags`, all subject to the same access gate as the main admin panel.

#### Scenario: Tag actions blocked when panel disabled
- **WHEN** `web_admin_enabled` is false and a request is made to any `/pantry-admin/tags` action
- **THEN** the system responds with HTTP 404, the same as the main admin panel

### Requirement: Admin panel can delete events
The system SHALL let an authorized admin permanently delete any event, including all of its dishes, via `POST /pantry-admin/events/{event_id}/delete`.

#### Scenario: Deleting an event removes its dishes
- **WHEN** an authorized admin deletes an event that has guest and host dishes attached
- **THEN** the event and all of its dishes are removed and are no longer reachable via `/e/{slug}` or `/manage/{token}`

### Requirement: Admin panel can force a live config reload
The system SHALL let an authorized admin re-read the persisted configuration into the running server's in-memory state via `POST /pantry-admin/reload`, without restarting the process.

#### Scenario: Reload picks up out-of-band changes
- **WHEN** the configuration was changed directly in the database (e.g. by the CLI) and an admin then triggers `/pantry-admin/reload`
- **THEN** subsequent requests use the newly persisted configuration
