## Context

- `app/storage.py` (~1,200 lines) is a hand-written `sqlite3` layer: one connection per call via `_get_connection()`, `?` placeholders, `sqlite3.Row`, `cursor.lastrowid`, `INTEGER PRIMARY KEY AUTOINCREMENT`, `PRAGMA foreign_keys`, timestamps and dates stored as ISO `TEXT`, booleans as `INTEGER`. Its header already lists the Postgres porting steps.
- `init_db()` creates tables with `IF NOT EXISTS`, runs ad-hoc in-place migrations, and seeds default dish types, tags and keywords. It runs in the app lifespan and in the test fixture.
- Config is loaded once into `app.state.config` at startup and refreshed only by SIGUSR1 (sent by `dishlist admin reload` via `data/dishlist.pid`) or `POST /pantry-admin/reload`. Web admin saves update only the instance that handled the request.
- Tests point `storage.DB_PATH` at a temp SQLite file per test and call `init_db()`.
- FastAPI Cloud launches the app itself, documents no pre-deploy hook, keeps the last good deployment live if a new one fails verification, and offers Neon for Postgres. Neon provides a pooled (PgBouncer, transaction mode) connection string and a direct one.

## Goals / Non-Goals

**Goals:**
- One storage implementation that runs unchanged against a local Postgres container and Neon.
- Schema changes that are explicit, versioned, and safe while old and new instances overlap.
- Config that stays consistent across instances without signals or shared files.
- Self-hosting via `docker compose up` keeps working with no manual database setup.

**Non-Goals:**
- An ORM. Queries stay hand-written SQL.
- Async database access. Route handlers and storage stay synchronous.
- Importing existing SQLite data.
- Fixing IP-allowlist behavior behind the FastAPI Cloud proxy (see Open Questions).

## Decisions

**1. psycopg 3 (sync) with `psycopg_pool.ConnectionPool`.**
`storage` keeps its public functions and signatures; only `_get_connection()` and the SQL change. The pool is created lazily on first use from `DATABASE_URL` (so the CLI and tests use it without the app lifespan) and closed in the lifespan shutdown. Rows use `dict_row`. Inserts use `RETURNING id` in place of `lastrowid`. Pool size stays small (min 1, max 5) because Neon's free tier caps connections and the app is low-traffic. Connections set `prepare_threshold=None` so they work through Neon's PgBouncer pooler, which doesn't support server-side prepared statements in transaction mode.
*Alternatives:* asyncpg would force every route and storage function async, a far larger change for no measured need. SQLAlchemy Core for queries would add an abstraction the code doesn't use elsewhere.

**2. Native Postgres types.**
Ids become `BIGINT GENERATED ALWAYS AS IDENTITY`; booleans `BOOLEAN`; `created_at`/`updated_at` `TIMESTAMPTZ`; event dates `DATE`. psycopg returns Python `datetime`/`date`/`bool`, so the `_row_to_*` helpers drop their string parsing. Foreign keys keep `ON DELETE CASCADE`. Any case-insensitive matching found while porting (`LIKE`, `lower()`) is ported explicitly; SQLite's ASCII-only case folding has no direct equivalent.
*Alternative:* keep `TEXT` timestamps to minimise model changes; rejected because a fresh schema with no data to preserve is the cheapest moment to fix types.

**3. Alembic with raw-SQL migrations, run by `dishlist db upgrade`.**
An `app/migrations/` package holds Alembic revisions written with `op.execute()` SQL. There are no SQLAlchemy models, so autogenerate is not used. Revision `0001_baseline` creates the full current schema and inserts the default dish types, tags and keywords as literal values frozen in the migration, so later edits to the defaults in `storage.py` can't silently change history. Alembic is configured in code (no `alembic.ini`), with the URL passed as a config attribute so a `%` in a password is never interpolated. `env.py` rewrites the scheme to `postgresql+psycopg://` and runs each revision in its own transaction. Living inside the `app` package, the migrations ship wherever the app does. SQLAlchemy is a dependency only because Alembic requires it.
*Alternative:* hand-rolled versioning in `init_db()` with an advisory lock; rejected (user decision) in favour of a standard tool and an explicit step.

**4. Startup checks the schema version but never migrates.**
`init_db()` becomes `check_schema()`: it reads `alembic_version` and compares it with the script directory's head. If behind or missing, the lifespan raises with a message to run `dishlist db upgrade`. On FastAPI Cloud this means a deploy whose migrations weren't applied fails verification and the previous deployment stays live, rather than serving errors.
Where migrations run:
- **Compose / Docker image:** the container command becomes `dishlist db upgrade && dishlist serve …`. A single self-hosted container makes this safe.
- **FastAPI Cloud:** the operator runs `DATABASE_URL=<neon direct url> uv run dishlist db upgrade` from their machine before `fastapi deploy`. Migrations use Neon's direct (non-pooler) URL; the app uses the pooled one.

**5. Config cache with a 5-second refresh.**
`app.state.config` is replaced by a small cache holding the config and the time it was loaded. The existing `get_config()` accessor in `main.py` reloads from the database when the entry is older than 5 seconds, which sits inside the spec's 10-second bound with margin. Saving through web admin writes to the database and replaces the cache immediately. `POST /pantry-admin/reload` invalidates it. The SIGUSR1 handler, PID file, `dishlist admin reload`, `DATA_DIR`, and the one-time `config.json` import are deleted.
*Alternatives:* reading config on every request costs one extra query per request, which is acceptable but unnecessary. Postgres `LISTEN/NOTIFY` gives instant propagation but needs a dedicated connection per instance and doesn't survive PgBouncer transaction pooling.

**6. Tests use a migrated template database, cloned per test.**
A session fixture connects to the server in `TEST_DATABASE_URL` (default `postgresql://dishlist:dishlist@localhost:5432/postgres`, the compose service), creates `dishlist_test_template`, and runs `dishlist db upgrade` against it once. The per-test `isolated_db` fixture runs `CREATE DATABASE dishlist_test_<n> TEMPLATE dishlist_test_template`, points `DATABASE_URL` at it, resets the storage pool, and drops the database afterwards. This gives every test the exact migrated and seeded schema with no shared state. If the suite becomes slow, switch to `TRUNCATE … RESTART IDENTITY` plus re-seeding. Tests are skipped with a clear message, not failed, when no Postgres is reachable.
*Alternative:* testcontainers; it adds a Docker-in-test dependency when the compose service already exists.

**7. Compose layout.**
A `postgres` service (`postgres:17-alpine`) with a named `pgdata` volume, a `pg_isready` healthcheck, and port 5432 published on `127.0.0.1` only, so `uv run dishlist serve` and `uv run pytest` on the host can use it. The `dishlist` service sets `DATABASE_URL=postgresql://dishlist:dishlist@postgres:5432/dishlist`, uses `depends_on: condition: service_healthy`, and its healthcheck calls `/health`. Credentials come from a `POSTGRES_PASSWORD` variable with a development default. The `./data` volume is removed.

**8. FastAPI Cloud packaging.**
`fastapi[standard]` replaces `fastapi` + `uvicorn`, which provides `fastapi deploy` and uvicorn. `requires-python = "==3.13.*"` matches the Docker base image. `.fastapicloudignore` excludes `tests/`, `docs/`, `openspec/`, `data/`, `Dockerfile` and `docker-compose.yml`, and un-ignores nothing. The entrypoint `app/main.py:app` is auto-detected. `DATABASE_URL` is set with `fastapi cloud env set --secret`.

## Risks / Trade-offs

- [Self-hosters lose their existing data] → Called out as **BREAKING** in the CHANGELOG and docs; the upgrade steps say to archive `data/dishlist.db` first. Ships in 0.6.0; the SQLite legacy-column migration drafted for 0.6.0 is dropped before release.
- [Forgetting `dishlist db upgrade` before a cloud deploy] → The startup check fails the deploy and the previous one stays live; the docs' deploy steps list the upgrade first.
- [A migration breaks the previous release during rollout] → The schema-migration spec requires expand/contract; reviewers check new migrations against it.
- [Tests now need a running Postgres] → One command (`docker compose up -d postgres`) in the testing docs; tests skip with an explicit message when it's absent.
- [Neon cold starts add latency after idle] → Acceptable for a potluck app; the pool's `check` callback reconnects stale connections after Neon suspends compute.
- [Config can be up to ~5 s stale on other instances] → Within the specified bound; the saving instance updates immediately.
- [Literal seed values in the baseline migration drift from `DEFAULT_TAG_GROUPS`] → Intentional: the migration is history. `tags reset` keeps using the code constants, so later default changes go out through a new migration or the reset command.

## Migration Plan

Self-hosted (`just deploy`):
1. Stop the app and archive the old database: `cp data/dishlist.db data/dishlist-0.5.db.bak`.
2. Deploy 0.6.0. Compose starts Postgres, then the app container runs `dishlist db upgrade` and serves.
3. Re-apply admin config: `docker compose exec dishlist dishlist admin web enable --network <cidr>`.
4. Rollback: check out v0.5.0 and `just deploy`; the untouched `data/dishlist.db` is used again. Data entered on 0.6.0 is not carried back, and v0.5.0 still has the add-dish 500 on databases created before v0.5.0.

FastAPI Cloud (first deploy):
1. Create a Neon project; note the pooled and direct connection strings.
2. `DATABASE_URL=<direct url> uv run dishlist db upgrade`.
3. `fastapi cloud env set --secret DATABASE_URL "<pooled url>"`.
4. `fastapi deploy`.
5. `DATABASE_URL=<direct url> uv run dishlist admin web enable --network <cidr>` if web admin is wanted; verify the allowlist behaviour (see Open Questions).

## Open Questions

- Which client address does the app see behind FastAPI Cloud's proxy? If it's the proxy's, the admin and metrics allowlists need either trusted forwarded headers or a different gate. That's a follow-up change once observed on a real deploy; it doesn't affect this design.
- Neon region and plan: an operational choice, made at setup time.
