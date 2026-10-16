## Why

Production hit a 500 when a host added a house dish: v0.5.0 dropped the legacy `allergens` and `dietary_flags` columns from the `dishes` `CREATE TABLE` without migrating existing databases, so every insert into an upgraded database violated a `NOT NULL` constraint. Investigating it also exposed input-validation gaps that can permanently break an event, and a missing way to fix a typo in a house dish. These belong together in one release, 0.6.0.

## What Changes

- Add a startup migration that removes the legacy `allergens` / `dietary_flags` columns from an existing `dishes` table, so databases created before v0.5.0 keep working.
- Reject whitespace-only names with HTTP 400 on event creation, event settings, guest dish submission, host item creation and dish editing. Today these either return 500 or, on event settings and the dish edit form, save an empty value that then crashes every later page load for that event.
- Add an **Edit** action for house dishes on the manage page. The house-dish edit form changes name, type and notes only; contributor and dietary tags are preserved.
- Renaming the host in event settings updates the contributor on the event's existing house dishes.
- Render `flash_success` / `flash_error` on the manage dashboard, and serve a readable HTML error page (status codes unchanged) to browsers instead of raw JSON.
- Make the proxy addresses trusted for `X-Forwarded-*` headers configurable (`--forwarded-allow-ips` / `FORWARDED_ALLOW_IPS`). The default stays `*`, so existing deployments are unaffected.
- Bump the version to 0.6.0 and add a changelog.
- Add a Ruff configuration and bring the codebase to a clean `ruff check` / `ruff format` (tooling only; no behavior change).

## Capabilities

### New Capabilities
- `schema-migration`: Startup upgrades of databases created by older DishList versions so they match the current schema without data loss to current features.
- `error-handling`: How HTTP errors are presented to browsers versus API-style clients.

### Modified Capabilities
- `host-management`: dashboard renders flash messages; host-item creation and dish editing reject blank names; house dishes are editable with a reduced form that preserves contributor and tags.
- `event-management`: event creation and settings reject whitespace-only names; renaming the host updates house dishes' contributor.
- `dish-submission`: whitespace-only contributor or dish name is rejected with HTTP 400.
- `cli-management`: `dishlist serve` accepts a configurable list of trusted proxy addresses.

## Impact

- **Code**: `app/main.py` (validation, error handler, host rename), `app/storage.py` (`init_db` migration, `update_event`), `app/cli.py` (serve option), templates `manage.html`, `manage_edit_dish.html`, new `error.html` and flash partial.
- **Data**: One-way migration drops two unused columns from `dishes` on first start of 0.6.0 against an old database. Operators should back up `data/dishlist.db` before upgrading.
- **Docs / release**: `docs/index.md` (+ rebuilt `index.html`), `CHANGELOG.md`, version in `pyproject.toml` and `uv.lock`.
- **Behavior compatibility**: HTTP status codes for existing validation failures are unchanged. Newly rejected inputs (whitespace-only names) previously produced 500s or corrupt data.
