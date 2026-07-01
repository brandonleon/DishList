# DishList Priority Tasks

## #34: Complete config migration — drop file-based config shim [DONE]
**Time:** 2-3h | **Priority:** 1 (blocker for future work)

Remove the dual-write shim that keeps `data/config.json` in sync with SQLite `config_entries` table.

### Work:
- [x] Remove `_load_config_from_file()` from `config.py`
- [x] Remove `_write_config_to_file()` from `config.py`
- [x] Remove `_get_file_updated_at()` from `config.py`
- [x] Remove timestamp arbitration logic from `load_config()` — DB is always source of truth
- [x] Update `save_config()` to write to DB only
- [x] Update tests that reference file-based config behaviour
- [x] Add one-time migration: if `config.json` exists and DB has no config entries, seed DB from file (then ignore file going forward)

**Reference:** ADR-0005

---

## #35: Management token recovery — add self-service or CLI guidance
**Time:** 45m–1.5h | **Priority:** 2 (UX gap)

If a Host loses their Management Token, there's no recovery flow. Implement Option A (CLI) first.

### Option A — Improve CLI recovery UX (45m):
- [ ] Add `dishlist admin events token <id>` subcommand
- [ ] Prints just the management URL for a specific event
- [ ] Makes recovery less error-prone than reading full events list

**Reference:** ADR-0004

---

## #30: Add health check endpoint
**Time:** 30m | **Priority:** 3 (nice-to-have)

Create `/health` endpoint for container orchestration.

### Work:
- [ ] Create `/health` route
- [ ] Returns 200 + JSON status
- [ ] Checks database connectivity
- [ ] Requires no authentication

**Milestone:** v1.0.0 - Stable Release

---

## Notes
- Start with #34 (technical debt, unblocks other work)
- Move to #35 Option A (quick UX win)
- Finish with #30 (makes Docker/K8s friendly)
