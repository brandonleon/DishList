# ADR-0008: PostgreSQL via DATABASE_URL, SQLite stays the default

**Status:** Accepted  
**Date:** 2026-10-29

## Context

[ADR-0003](./0003-sqlite-as-primary-datastore.md) chose SQLite because DishList is a single-instance, self-hosted app. That assumes a persistent local disk. On platforms that rebuild the container filesystem on every deploy (FastAPI Cloud was the first), the SQLite file is deleted on each deploy, taking every event and management link with it. The code and `docker-compose.yml` had mentioned a future `DATABASE_URL` for PostgreSQL, but the variable was never read.

## Decision

- If `DATABASE_URL` starts with `postgresql://` or `postgres://`, DishList uses PostgreSQL. Anything else (unset, `sqlite:///...`) uses the SQLite file as before. The choice is read on each connection, not frozen at import.
- One set of queries serves both backends. `app/storage.py` keeps SQL written with `?` placeholders and passes it through a small `_Conn` wrapper that, for PostgreSQL, rewrites placeholders, maps `INTEGER PRIMARY KEY AUTOINCREMENT` to `SERIAL`, and fetches new ids with `RETURNING id`. The few dialect differences (timestamp ordering, "add column if missing", the email-retention cutoffs) are handled explicitly; retention now compares ISO date strings computed in Python so it needs no date functions.
- PostgreSQL connections come from a `psycopg_pool` pool. Connections are checked on checkout (serverless Postgres drops idle ones), prepared statements are disabled (poolers like Neon's PgBouncer endpoint may not support them), and `client_encoding` is forced to UTF-8.
- Tables live in a dedicated PostgreSQL schema, `dishlist` by default (`DATABASE_SCHEMA` overrides it), selected per transaction with `SET LOCAL search_path` (safe behind transaction poolers). `CREATE TABLE IF NOT EXISTS` silently adopts any same-named table, so using `public` would break, or worse corrupt, on a database that already had an `events` or `dishes` table; the first production deploy hit exactly that (`operator does not exist: boolean = integer`). A dedicated schema means DishList only ever touches what it created.
- The email-retention purge at startup is best effort: a failure is logged and never prevents the app from starting.
- Schema setup runs under a PostgreSQL advisory lock so several instances starting at once cannot race.
- The same test suite runs against either backend. `TEST_DATABASE_URL` selects PostgreSQL and drops the `dishlist` schema per test, so it must be a throwaway database.

## Consequences

- Hosts without persistent disks keep their data across deploys by setting one environment variable.
- Schema is still created and extended by `init_db` (`CREATE TABLE IF NOT EXISTS` plus additive `ALTER TABLE`). There is no migration framework; destructive schema changes would need one.
- Existing SQLite data is not migrated automatically. Moving an existing SQLite deployment to PostgreSQL needs a one-off export.
- Two SQL dialects must keep working. New queries should use the portable subset and be exercised by the PostgreSQL test run.
- The app depends on `psycopg` and `psycopg-pool` even when only SQLite is used.
- Rate-limit counters are still per process and in memory ([ADR-0007](./0007-optional-email-via-resend.md)); only persistent data moved to PostgreSQL.
