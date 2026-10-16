## Why

DishList stores everything in a SQLite file under `data/`, which only works with one long-lived process and a persistent disk. FastAPI Cloud provides neither: it scales to zero, autoscales to several instances, and overlaps old and new instances during a rollout, with Postgres offered through Neon. SQLite was always meant as a lightweight development store, so moving to Postgres everywhere (a local container in development and self-hosting, Neon in the cloud) lets the same code run in both places.

## What Changes

- **BREAKING** Replace the SQLite storage layer with PostgreSQL via psycopg 3 and a connection pool. SQLite support is removed entirely; `DATABASE_URL` becomes required.
- **BREAKING** No data is carried over from `data/dishlist.db`. Existing deployments start with an empty Postgres database; operators archive the old file.
- **BREAKING** Schema is managed by versioned Alembic migrations, applied by a new `dishlist db upgrade` command run before the app starts or deploys, instead of in-place upgrades inside `init_db()` on every startup. App startup checks the schema is current and refuses to serve if it is behind.
- **BREAKING** Configuration is no longer cached for the life of a process. Every instance re-reads it from the database on a short interval, so changes made by the CLI or by web admin on another instance take effect everywhere without a signal. `dishlist admin reload`, the PID file and the SIGUSR1 handler are removed.
- `dishlist admin …` commands work against any database named by `DATABASE_URL`, which is how an operator configures a FastAPI Cloud deployment (point it at Neon from a local machine).
- `docker-compose.yml` gains a `postgres` service with a named volume; the `dishlist` service runs `dishlist db upgrade` before serving and its healthcheck uses `/health`.
- FastAPI Cloud readiness: depend on `fastapi[standard]`, pin `requires-python` to `==3.13.*`, add `.fastapicloudignore` excluding `tests/`, `docs/`, `openspec/` and `data/`.
- The test suite runs against Postgres instead of temporary SQLite files.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `schema-migration`: Startup upgrades of SQLite files are replaced by versioned migrations applied by an explicit command; the SQLite-specific requirements (legacy column drop, SQLite version check) are removed. Ships in the same 0.6.0 release as `release-0-6-0-house-edit-and-hardening`, which introduces this capability; that change is archived first.
- `cli-management`: Adds `dishlist db upgrade`; admin commands target the database named by `DATABASE_URL`; removes the `dishlist admin reload` signal requirement.
- `web-admin`: Config changes propagate to all running instances automatically; `POST /pantry-admin/reload` refreshes only the serving instance's cache and is no longer needed for out-of-band changes.

## Impact

- **Code**: `app/storage.py` (rewritten for psycopg; `init_db()` becomes a schema check), `app/config.py` (drop `DATA_DIR`/`config.json` migration path, time-bounded cache), `app/main.py` (lifespan: pool open/close, no PID file or signal handler; config access), `app/cli.py` (`db upgrade`, remove `admin reload`), new `migrations/` Alembic environment and `alembic.ini`.
- **Dependencies**: add `psycopg[binary]`, `psycopg-pool`, `alembic`, `sqlalchemy` (used by Alembic only); swap `fastapi` + `uvicorn` for `fastapi[standard]`.
- **Tests**: `tests/conftest.py` moves to a Postgres test database (`TEST_DATABASE_URL`, defaulting to the compose service); `tests/test_migrations.py` is replaced with Alembic upgrade and current-schema tests.
- **Infra**: `docker-compose.yml`, `Dockerfile` (start command runs migrations), `Justfile`, new `.fastapicloudignore`; docs (`docs/index.md`, README, `AGENTS.md`/`CLAUDE.md` Data Steward playbook) updated for Postgres, backups via `pg_dump`, and FastAPI Cloud deploy steps.
- **Operators**: Self-hosters lose existing SQLite data on upgrade and must set `DATABASE_URL` (provided by compose). Ships as part of 0.6.0 together with `release-0-6-0-house-edit-and-hardening`, so the 0.6.0 SQLite legacy-column migration never reaches a release and is removed.
- **Open risk**: On FastAPI Cloud the app is launched by the platform, not `dishlist serve`, so the `FORWARDED_ALLOW_IPS` handling does not apply and the admin/metrics IP allowlists may see the platform proxy's address instead of the client's. To be verified after the first cloud deploy; not solved by this change.
