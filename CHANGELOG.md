# Changelog

All notable changes to DishList are recorded here. Versions follow
[Semantic Versioning](https://semver.org/).

## 0.6.0 — 2026-09-24

### Upgrade notes
- **BREAKING — PostgreSQL replaces SQLite.** DishList now stores everything in PostgreSQL,
  named by the required `DATABASE_URL` environment variable. `docker compose` provides a
  `postgres` service and sets it for you; FastAPI Cloud deployments use Neon.
- **BREAKING — existing data is not carried over.** `data/dishlist.db` is not imported:
  events, dishes, tags and settings start fresh. Keep a copy
  (`cp data/dishlist.db data/dishlist-0.5.db.bak`) if you may roll back to v0.5.0, and re-run
  your `dishlist admin` settings (web admin, networks, metrics) after upgrading.
- **BREAKING — schema migrations are an explicit step.** Run `dishlist db upgrade` before
  starting a new version; the server refuses to start on an outdated schema. The Docker image
  does this automatically on start.
- **BREAKING — `dishlist admin reload` is removed**, along with the `data/dishlist.pid` file
  and the `SIGUSR1` handler. Every server re-reads its configuration from the database every
  few seconds, so CLI changes apply without a reload.

### Added
- `dishlist db upgrade` applies versioned (Alembic) schema migrations.
- Deploying to **FastAPI Cloud** with a Neon database: `fastapi[standard]` dependency,
  `[tool.fastapi]` entrypoint, `.fastapicloudignore`, and deploy steps in the user guide.
- `dishlist admin …` commands work against any database named by `DATABASE_URL`, so a remote
  deployment can be managed from your own machine.
- Hosts can **edit house dishes** from the manage page (name, type, notes). Contributor and tags
  are kept as they are.
- `dishlist serve --forwarded-allow-ips` / `FORWARDED_ALLOW_IPS` to limit which proxies are
  trusted for `X-Forwarded-*` headers. The default is unchanged (`*`).
- Browsers now get a readable HTML error page (same HTTP status) instead of raw JSON; other
  clients still get JSON.
- The manage page now shows `flash_success` / `flash_error` messages.

### Changed
- Configuration changes (from the CLI, web admin, or another server instance) reach every
  running instance within about 5 seconds; **Reload config** in `/pantry-admin` applies them
  to that instance immediately.
- `docker-compose.yml` runs a `postgres` service with a `pgdata` volume instead of mounting
  `./data`, and its healthcheck uses `/health`.
- Python 3.13 is now required (`requires-python = "==3.13.*"`).
- Renaming the host in event settings also updates the contributor on the event's house dishes.

### Fixed
- Whitespace-only names are rejected with a 400 instead of a 500, on event creation, event
  settings, guest submissions, host items and dish edits. Previously a blank event name saved
  through settings, or a blank contributor saved through the edit form, made that event's pages
  crash on every load, and a blank name at creation left an unreadable event row that broke the
  admin events list.
- An over-long host name (more than 80 characters) is rejected up front instead of being saved
  and then failing on read.

### Tooling
- Added a Ruff configuration (`pyproject.toml`) and cleaned the codebase to pass `ruff check`
  and `ruff format`: modern type hints (`list[str]`, `str | None`), sorted imports,
  `contextlib.suppress`, exception chaining (`raise ... from None`), and `assert`-based
  narrowing replaced with explicit errors. No behavior changes intended.
- Run with `uvx ruff check app tests` and `uvx ruff format --check app tests`.

### Specs
- The OpenSpec baseline is archived into `openspec/specs/`, and this release is tracked as the
  `release-0-6-0-house-edit-and-hardening` change.
