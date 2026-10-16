## 1. Schema migration

- [x] 1.1 Add a failing test that builds a legacy `dishes` table (with `allergens`, `dietary_flags`, rows and tag associations), runs `init_db()`, and asserts columns removed, rows and `dish_tags` preserved, and `add_dish` succeeds
- [x] 1.2 Implement the guarded `DROP COLUMN` migration in `init_db()` with the SQLite ≥ 3.35 check and clear error
- [x] 1.3 Add tests for idempotence (second `init_db()` is a no-op) and for the unsupported-SQLite error path (monkeypatched version)

## 2. Input validation

- [x] 2.1 Host item add: reject whitespace-only dish name with 400
- [x] 2.2 Dish edit: reject whitespace-only dish name and (for guest dishes) missing or whitespace-only contributor with 400, before any write
- [x] 2.3 Guest add (`/e/{slug}/add`): reject whitespace-only contributor or dish name with 400
- [x] 2.4 Event settings: reject whitespace-only event name with 400 before any write
- [x] 2.5 Event create: reject whitespace-only event name with 400 before the event row is inserted
- [x] 2.6 Regression tests for 2.3–2.5, including that the manage page and `load_events()` still work afterwards

## 3. House dish editing

- [x] 3.1 Edit button on house rows in `manage.html`
- [x] 3.2 House-dish variant of the edit form (no contributor field, no tag picker) and route branch preserving contributor and tags
- [x] 3.3 Tests: Edit link present, form variants, house edit updates name/type/notes only, contributor override ignored

## 4. Host rename

- [x] 4.1 Update `update_event` to set `contributor` on the event's host dishes when the host name changes, in the same transaction
- [x] 4.2 Tests: rename updates house dishes only and leaves guest dishes alone; rename to the same name is a no-op

## 5. Error presentation

- [x] 5.1 Add `error.html` and a `StarletteHTTPException` handler returning HTML for `Accept: text/html` and default JSON otherwise
- [x] 5.2 Add a flash partial and render `flash_success` / `flash_error` in `manage.html`
- [x] 5.3 Tests: browser Accept header gets HTML with the message escaped and the original status; default Accept keeps JSON; manage page shows an escaped flash message

## 6. Trusted proxies

- [x] 6.1 Add `--forwarded-allow-ips` option with `FORWARDED_ALLOW_IPS` fallback and default `*`; use it in both `uvicorn.run` calls
- [x] 6.2 Tests for option/env/default precedence (mock `uvicorn.run`), including the no-reload fallback call
- [x] 6.3 Document the setting in `docs/index.md` reverse-proxy section and `docker-compose.yml` comments

## 7. Lint and tooling

- [x] 7.1 Add `[tool.ruff]` configuration (rules, per-file ignores, FastAPI immutable calls)
- [x] 7.2 Apply safe autofixes and resolve the remaining findings by hand (helper for lastrowid, shared event-date parser, narrowed excepts, exception chaining)
- [x] 7.3 Document `uvx ruff check` / `uvx ruff format --check` in `AGENTS.md`

## 8. Release

- [x] 8.1 Bump version to 0.6.0 in `pyproject.toml` and `uv.lock`
- [x] 8.2 Update `docs/index.md` for house-dish editing (rebuilt `docs/index.html`)
- [x] 8.3 Add `CHANGELOG.md` with the 0.6.0 entry, including the back-up-before-upgrade note
- [x] 8.4 Fill in the `Purpose` section of the eight archived baseline specs
- [x] 8.5 Add "Guest self-editing" to `dishlist-todos.md`
- [ ] 8.6 Run the full suite, `openspec validate --strict`, rebuild docs, and archive this change after deploy verification
