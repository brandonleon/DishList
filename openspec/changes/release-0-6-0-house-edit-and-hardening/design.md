## Context

See proposal.md for motivation. Relevant current state:

- `init_db()` (`app/storage.py`) uses `CREATE TABLE IF NOT EXISTS` and has no schema versioning. The only in-place migration is an `ALTER TABLE tags ADD COLUMN is_hidden` wrapped in try/except. v0.4.x created `dishes` with `allergens TEXT NOT NULL` and `dietary_flags TEXT NOT NULL`; v0.5.0 removed them from the `CREATE TABLE` and from every read and write path, but nothing removes them from existing files.
- `_get_connection()` opens every connection with `PRAGMA foreign_keys = ON`, and `dish_tags` references `dishes` with `ON DELETE CASCADE`.
- Route handlers validate with FastAPI `Form(min_length=…)` on the raw string, then `.strip()` and build a pydantic model whose fields also have `min_length=1`. A whitespace-only value passes the first check and fails the second — or, where the model is built with `model_copy(update=…)` (no validation), or where the row is inserted before the model is constructed (`create_event`), is persisted and then breaks every later read.
- HTTP errors are raised as `HTTPException` and rendered by FastAPI's default JSON handler.
- `dishlist serve` hard-codes `proxy_headers=True, forwarded_allow_ips="*"` in two places.

## Goals / Non-Goals

**Goals:**
- Any database created by any released version starts cleanly on 0.6.0 and accepts new dishes.
- No input can be saved that later makes a page for that event or the admin list crash.
- No change to existing HTTP status codes or to the default proxy-trust behavior.

**Non-Goals:**
- A general schema-versioning framework (`PRAGMA user_version`, numbered migrations). One targeted migration matches the existing pattern; revisit if a second is needed.
- Preserving the contents of `allergens` / `dietary_flags`. They have been unread since v0.5.0 and were superseded by tags in v0.4.0.
- Changing the default trusted-proxy setting, guest self-editing, or admin-panel behavior.

## Decisions

**1. Migrate with `ALTER TABLE … DROP COLUMN`, guarded by `PRAGMA table_info`.**
Inspect the `dishes` columns inside `init_db()`; for each legacy column present, drop it. Idempotent because the check runs every start. Requires SQLite ≥ 3.35.0 (production image ships 3.40; dev has 3.50); if older and columns are present, raise a clear error.
*Alternative rejected — table rebuild (create new, copy, drop, rename):* with `foreign_keys=ON`, dropping the old `dishes` table cascades and deletes every `dish_tags` row, and `PRAGMA foreign_keys` cannot be changed inside the connection's open transaction. Rebuilding safely needs a second connection or restructured transaction handling — more risk for no benefit here.
*Alternative rejected — give the columns defaults:* SQLite cannot alter an existing column's constraint.

**2. Strip first, then validate, at the route boundary.**
Each handler strips the submitted text and raises `HTTPException(400)` with a specific message if a required value is empty, *before* building any model or touching storage. For `create_event`, validate in the route before calling storage, so the row is never inserted. This keeps status codes identical to existing validation failures and avoids changing model definitions.
*Alternative rejected — a shared `StrippedStr` pydantic type / Form dependency:* cleaner long-term, but a larger refactor touching every route and model; the route-level checks are small and explicit for this release.

**3. House-dish editing reuses the existing edit route and template.**
`manage_edit_dish_submit` branches on `dish.is_host_item`: it keeps the stored contributor and tags, and `contributor` becomes optional in the form signature. The template hides the contributor field and tag picker for house dishes. No new route.
*Alternative rejected — a separate `/host-items/{id}` edit route:* duplicates validation and would leave two ways to edit the same row.

**4. Host rename updates house dishes inside `update_event`'s transaction.**
`UPDATE dishes SET contributor = ? WHERE event_id = ? AND is_host_item = 1` in the same connection as the event update, so both change or neither does. Guest rows are never touched.
*Alternative rejected — deriving the displayed contributor from `event.host_name` at read time:* would require changing every template and the JSON-ish read paths, and existing rows would still hold stale values.

**5. HTML error pages via an exception handler, not flash redirects.**
Register a handler for `StarletteHTTPException` that returns `error.html` when the `Accept` header prefers `text/html`, and defers to the default JSON handler otherwise. Status codes and `detail` text are unchanged, so existing tests and API-style callers keep working (the test client sends `Accept: */*`).
*Alternative rejected — redirect back with `?flash_error=…`:* would change 400 responses into 303s (breaking the existing contract) and reflect arbitrary query text into pages on public routes.
Separately, `manage.html` renders `flash_success` / `flash_error` through a small partial. Jinja autoescape is on, so injected markup is displayed as text.

**6. Trusted proxies configurable, default unchanged.**
`--forwarded-allow-ips` option, falling back to the `FORWARDED_ALLOW_IPS` environment variable (the same name uvicorn itself uses), falling back to `*`. The value is used in both `uvicorn.run` calls.
*Alternative rejected — default to loopback only:* would silently break the existing Nginx Proxy Manager / Docker-bridge deployments (scheme and client-IP detection), which is exactly what the reverse-proxy docs promise works.

## Risks / Trade-offs

- [The migration is one-way and drops data] → The dropped columns are unused by 0.5.x+ code; CHANGELOG and docs tell operators to back up `data/dishlist.db` first; migration only runs when the legacy columns exist.
- [Migration runs on startup against a possibly large or locked DB] → `DROP COLUMN` is a metadata-plus-rewrite operation on a small table; it runs inside the same connection/transaction as the rest of `init_db()`, so a failure rolls back.
- [Default `forwarded_allow_ips="*"` remains permissive] → If web admin or metrics are enabled behind a public endpoint, a client-supplied `X-Forwarded-For` may be honored. This change adds the knob and documents it; it does not change the default. Admin and metrics stay disabled by default (ADR-0002).
- [Route-level checks can be forgotten on future routes] → Regression tests cover each route touched here; consider the shared-type refactor later.
- [House-dish tags are hidden in the edit form] → House dishes never displayed tags on the manage page; existing tags on a house dish are preserved rather than dropped.

## Migration Plan

1. Back up: `cp data/dishlist.db data/dishlist.db.bak` (Data Playbook).
2. Deploy 0.6.0 (`just deploy`). On first start `init_db()` drops the legacy columns if present.
3. Verify: `docker compose logs dishlist` shows no errors; add a house dish on the manage page.
4. Rollback: restore the backup and redeploy the previous image. The 0.5.x code cannot insert into a database that still has the legacy columns, so rolling back to 0.5.x without restoring a backup is only safe for databases that were already migrated.
