# ADR-0005: Dual-write config as a migration shim toward DB-only storage

**Status:** Accepted — migration in progress  
**Date:** 2026-05-18

## Context

DishList originally stored all application configuration (dish types, admin networks, web admin toggle) in `data/config.json`. A later version added a `config_entries` table in SQLite to centralise all persistent state in one place (the database) and simplify Docker deployments.

To avoid breaking existing deployments that relied on `config.json`, a dual-write shim was introduced in `config.py`. On every load, both sources are read and the **newest wins by file/DB timestamp**, with the loser synced to match. On every save, both sources are written simultaneously.

## Decision

The dual-write shim is explicitly a migration aid, not a permanent architecture. The intended end state is **DB-only config storage** — `config.json` becomes optional/ignored.

The shim is kept until all known deployments have transitioned and the file-based path can be safely removed without data loss risk.

## Consequences

- Existing deployments that manage config by editing `config.json` directly continue to work — the file wins if it is newer than the DB entry.
- Split-brain risk: editing `config.json` while the app is running will overwrite DB changes made since the file was last touched (last-writer-wins by timestamp). This is acceptable during the migration window.
- When removing the shim: drop `_load_config_from_file`, `_write_config_to_file`, `_get_file_updated_at`, and the timestamp arbitration logic in `load_config`. `save_config` should write to DB only. `config.json` can be left in place as an ignored artefact or deleted.
- Do not add new config keys to `config.json` — add them to the DB schema only.
