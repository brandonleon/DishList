# ADR-0003: SQLite as the primary datastore

**Status:** Accepted  
**Date:** 2026-05-18

## Context

DishList is a self-hosted, single-instance web application. It needs a persistence layer for Events, Submissions, Tags, and configuration. Options considered:

1. **SQLite** — embedded, file-based, zero external dependencies.
2. **PostgreSQL** — full client-server RDBMS, requires a separate process and connection management.
3. **Other** — MySQL, MongoDB, flat files, etc.

The target deployment is a single server (or Docker container) operated by one person. There is no multi-writer concurrency requirement — one web process serves all traffic. Backup simplicity and zero-ops overhead are first-class concerns.

## Decision

SQLite is the primary datastore. The entire database is a single file (`data/dishlist.db`) that can be backed up with a file copy. No external database process is required — the app is self-contained.

A PostgreSQL migration path is documented in `storage.py` as a comment block. This exists to leave the door open for future hosted or multi-instance deployments without committing to that complexity now.

## Consequences

- Zero ops overhead: no database server to install, configure, or monitor.
- Trivial backup: copy one file.
- Works out of the box in Docker with a single volume mount.
- SQLite's write concurrency is sufficient for the expected load (one potluck's worth of submissions, not thousands of concurrent writers).
- If DishList is ever offered as a hosted multi-tenant service with high write concurrency, SQLite becomes a bottleneck and this decision should be revisited. The migration path in `storage.py` documents the key changes needed.
- Do not migrate to PostgreSQL for a single-instance self-hosted deployment — the operational complexity is not justified.
