## 1. Dependencies and local Postgres

- [x] 1.1 `pyproject.toml`: replace `fastapi` + `uvicorn` with `fastapi[standard]`; add `psycopg[binary]`, `psycopg-pool`, `alembic`, `sqlalchemy`; set `requires-python = "==3.13.*"`; `uv lock`
- [x] 1.2 `docker-compose.yml`: add `postgres` service (`postgres:17-alpine`, `pgdata` volume, `pg_isready` healthcheck, `127.0.0.1:5432` published, `POSTGRES_PASSWORD` with dev default); `dishlist` service gets `DATABASE_URL`, `depends_on: service_healthy`, `/health` healthcheck; remove the `./data` volume
- [x] 1.3 Verify `docker compose up -d postgres` and `psql` connectivity from the host

## 2. Alembic baseline

- [x] 2.1 Add `app/migrations/` (env.py reading the URL, rewriting to `postgresql+psycopg://`), configured in code (no `alembic.ini`) so it ships inside the `app` package
- [x] 2.2 Write revision `0001_baseline`: all current tables with native types (identity ids, `BOOLEAN`, `TIMESTAMPTZ`, `DATE`, cascading FKs) plus literal seed rows for default dish types, config defaults, tags and keywords
- [x] 2.3 Add `dishlist db upgrade` CLI command (programmatic `command.upgrade`, prints before/after version, non-zero exit on failure)
- [x] 2.4 Tests: upgrade on an empty DB creates tables and seeds; second run is a no-op and exits zero; failing migration exits non-zero

## 3. Test harness on Postgres

- [x] 3.1 Rewrite `tests/conftest.py`: session fixture builds `dishlist_test_template` via `dishlist db upgrade`; per-test fixture clones it, points `DATABASE_URL` at the clone, resets the storage pool, drops it after; skip with a clear message when Postgres is unreachable
- [x] 3.2 Replace `tests/test_migrations.py` SQLite legacy-column tests with Alembic tests (2.4) and startup schema-check tests (4.3)

## 4. Storage layer port

- [x] 4.1 Replace `_get_connection()` with a lazily created `psycopg_pool.ConnectionPool` (`dict_row`, `prepare_threshold=None`, min 1 / max 5, stale-connection check) and a `close_pool()`/`reset_pool()` pair; fail with a clear error when `DATABASE_URL` is unset
- [x] 4.2 Port every query: `?` → `%s`, `lastrowid` → `RETURNING id`, drop `PRAGMA`s, `INSERT OR …` → `ON CONFLICT`, audit `LIKE`/case-insensitive matching; update `_row_to_*` for native types
- [x] 4.3 Replace `init_db()` with `check_schema()` that compares `alembic_version` to head and raises with a `dishlist db upgrade` message; remove the SQLite migration helpers and `_seed_or_migrate_*` startup seeding
- [x] 4.4 Run the full suite green against Postgres (`uv run pytest tests/`)

## 5. Config and lifespan

- [x] 5.1 `app/config.py`: remove `DATA_DIR`, `CONFIG_PATH` and the `config.json` import path
- [x] 5.2 `app/main.py`: config cache with 5 s refresh behind `get_config()`; web admin save replaces the cache; `POST /pantry-admin/reload` invalidates it
- [x] 5.3 Lifespan: call `check_schema()`, close the pool on shutdown; remove the PID file and SIGUSR1 handler
- [x] 5.4 Remove `dishlist admin reload` from `app/cli.py`; every data-touching command errors clearly when `DATABASE_URL` is unset
- [x] 5.5 Tests: config change via a second "instance" (direct DB write) is picked up after the refresh interval; reload invalidates immediately; startup fails on a behind/missing schema; CLI fails without `DATABASE_URL`

## 6. Packaging and deploy

- [x] 6.1 `Dockerfile`: CMD runs `dishlist db upgrade && dishlist serve …`
- [x] 6.2 Add `.fastapicloudignore` (`tests/`, `docs/`, `openspec/`, `data/`, `Dockerfile`, `docker-compose.yml`)
- [x] 6.3 Verify `uv run fastapi dev` starts with no path against the compose Postgres
- [x] 6.4 `just deploy` path: bring the full compose stack up from scratch and smoke-test create event → add dish → manage page → `/health`

## 7. Docs and release

- [x] 7.1 `docs/index.md`: Postgres setup, `dishlist db upgrade`, FastAPI Cloud + Neon deploy steps (pooled vs direct URL), self-host upgrade with archived SQLite file; run `uv run docs/build.py`
- [x] 7.2 Update README, `AGENTS.md`/`CLAUDE.md` (Testing needs Postgres; Data Steward playbook uses `pg_dump`; schema changes go through Alembic, not `init_db()`)
- [x] 7.3 Rewrite the CHANGELOG 0.6.0 entry: replace the SQLite backup/legacy-column upgrade notes with **BREAKING** Postgres notes (fresh database, `DATABASE_URL`, `dishlist db upgrade`, `dishlist admin reload` removed); keep the version at 0.6.0
- [x] 7.4 `uvx ruff check app tests migrations` and `uvx ruff format --check app tests migrations` clean; `openspec validate --strict`
- [ ] 7.5 Archive `release-0-6-0-house-edit-and-hardening` first, then this change, after deploy verification (`/opsx:archive`)
