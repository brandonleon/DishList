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

## #35: Management token recovery — add self-service or CLI guidance [DONE]
**Time:** 45m–1.5h | **Priority:** 2 (UX gap)

If a Host loses their Management Token, there's no recovery flow. Implement Option A (CLI) first.

### Option A — Improve CLI recovery UX (45m):
- [x] Add `dishlist admin events token <id>` subcommand
- [x] Prints just the management URL for a specific event
- [x] Makes recovery less error-prone than reading full events list

**Reference:** ADR-0004

---

## #30: Add health check endpoint [DONE]
**Time:** 30m | **Priority:** 3 (nice-to-have)

Create `/health` endpoint for container orchestration.

### Work:
- [x] Create `/health` route
- [x] Returns 200 + JSON status
- [x] Checks database connectivity
- [x] Requires no authentication

**Milestone:** v1.0.0 - Stable Release

---

## Backlog: Guest self-editing
**Time:** 3-5h | **Priority:** Backlog (feature; needs a design decision first)

Let a guest fix or remove their own submission (typo, wrong category, changed plans) without asking the host. Today the guest form is submit-only and the docs tell guests to ask the host (`docs/index.md`, "Need to change your submission?").

### Why it is not a quick win
[ADR-0004](docs/adr/0004-no-user-accounts.md) says guests have no persistent identity and there are no accounts or sessions. Editing needs some way to prove "this is my dish". Any approach has to stay inside that decision or amend it.

### Options to weigh
- **Per-dish edit link (favoured):** issue an unguessable edit token when the dish is submitted, show it once as a link ("Bookmark this to edit your dish"), and optionally remember it in the browser. Same trust model as the Management Token; no accounts.
- **Name match:** allow editing when the contributor name matches. Rejected for now: anyone can type someone else's name.
- **Host-only (status quo):** keep editing with the host. Zero work; the current answer.

### Work (once an option is chosen):
- [ ] Decide the option and record it as an ADR (amend or extend ADR-0004)
- [ ] Propose it with OpenSpec (`/opsx:propose`) — new requirements in `dish-submission`, delta to `host-management` if the host should be able to revoke links
- [ ] Storage: per-dish edit token (migration in `init_db`, see `schema-migration` spec)
- [ ] Routes and templates: post-submit "edit link" panel; guest edit form (name, type, notes, tags; no contributor change); guest delete
- [ ] Respect closed events: decide whether editing is allowed after the host closes submissions
- [ ] Tests, docs update (remove the "ask the host" note), changelog entry

**Reference:** ADR-0004

---

## Notes
- Start with #34 (technical debt, unblocks other work)
- Move to #35 Option A (quick UX win)
- Finish with #30 (makes Docker/K8s friendly)
