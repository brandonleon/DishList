## ADDED Requirements

### Requirement: Unauthenticated health check reports app and DB status
The system SHALL expose `GET /health` without any access gate, returning JSON with `status`, `version`, and `db` fields. It SHALL return HTTP 200 with `status: "ok"` when a database read succeeds, and HTTP 503 with `status: "degraded"` when it fails.

#### Scenario: Database unreachable
- **WHEN** the health check's database query raises an exception
- **THEN** the endpoint responds with HTTP 503 and `db: "error"` in the JSON body

### Requirement: Prometheus metrics endpoint is IP-gated and independently toggleable
The system SHALL reject `GET /metrics` with HTTP 404 whenever `metrics_enabled` is false, and with HTTP 403 when enabled but the caller's IP is outside the configured `metrics_networks` allowlist. This gate SHALL be independent of the `web_admin_enabled`/`admin_networks` gate used for `/pantry-admin`.

#### Scenario: Metrics disabled by default
- **WHEN** `metrics_enabled` is false (the default) and any client requests `/metrics`
- **THEN** the system responds with HTTP 404

### Requirement: Metrics endpoint exposes request and domain counters
When accessible, `/metrics` SHALL render Prometheus text-format output including a total-requests counter and a request-duration histogram labeled by HTTP method and matched route path, plus gauges for the current total number of events and dishes refreshed at scrape time.

#### Scenario: Metrics scraping is excluded from its own counters
- **WHEN** a client scrapes `/metrics`
- **THEN** that request itself is not recorded in `dishlist_http_requests_total` or the duration histogram
