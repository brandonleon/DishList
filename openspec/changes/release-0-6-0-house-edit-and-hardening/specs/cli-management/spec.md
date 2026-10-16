## MODIFIED Requirements

### Requirement: CLI can start the web server
The `dishlist serve` command SHALL start the FastAPI app under uvicorn with configurable `--host`/`--port`, proxy headers enabled, and live reload on by default unless disabled via `--no-reload` or the `DISHLIST_RELOAD` environment variable. The set of proxy addresses whose `X-Forwarded-*` headers are trusted SHALL be configurable via the `--forwarded-allow-ips` option or the `FORWARDED_ALLOW_IPS` environment variable, with the option taking precedence, and SHALL default to trusting all addresses (`*`) when neither is set.

#### Scenario: Reload blocked by the platform
- **WHEN** live reload is requested but the platform raises a `PermissionError` on startup
- **THEN** the CLI logs a warning and restarts uvicorn without reload rather than crashing

#### Scenario: Default trusts all proxies
- **WHEN** `dishlist serve` is run with neither `--forwarded-allow-ips` nor `FORWARDED_ALLOW_IPS`
- **THEN** uvicorn is started with forwarded headers trusted from any address, matching behavior before this option existed

#### Scenario: Trusted proxies restricted by environment
- **WHEN** `FORWARDED_ALLOW_IPS=127.0.0.1` is set and no option is passed
- **THEN** uvicorn is started trusting forwarded headers only from 127.0.0.1

#### Scenario: Option overrides environment
- **WHEN** `FORWARDED_ALLOW_IPS=127.0.0.1` is set and `--forwarded-allow-ips 10.0.0.0/8` is passed
- **THEN** uvicorn is started trusting forwarded headers from `10.0.0.0/8`, including on the fallback restart without reload
