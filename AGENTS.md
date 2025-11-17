# Agents

These agents describe how we operate and maintain DishList so everyone knows who
does what.

## Potluck Host Agent

- Owns the guest-facing experience: homepage, submission form, clever empty state,
  and dietary metadata.
- Keeps Bootstrap design cohesive and ensures templates stay accessible on mobile.
- Coordinates content updates, marketing blurbs, and copy tone to keep the potluck
  fun.

### Host Playbook

1. Run `uv sync` when dependencies change or after pulling from main.
2. Use `uv run python main.py` for manual QA; stop the server with `Ctrl+C`.
3. Update `app/templates/` or `app/static/` as needed, then refresh the browser to
   confirm.

## Admin Guardian Agent

- Protects `/pantry-admin` by maintaining the IP allowlist in `data/config.json`.
- Curates the list of dish types so submitters always have relevant options.
- Audits allergen labeling and dietary flags to ensure clarity for guests with
  restrictions.

### Admin Playbook

1. Confirm your IP is allowlisted before sharing the admin URL.
2. Adjust dish types/IPs in the admin UI; the JSON file updates automatically.
3. Commit config changes that should persist and document the motivation.

## Data Steward Agent

- Manages the `data/dishlist.db` store and verifies submissions deserialize into
  `DishEntry` without errors.
- Plans any future migration to a database or API integration.
- Monitors file growth and rotates archives if the list becomes unwieldy.

### Data Playbook

1. Back up the SQLite file with `cp data/dishlist.db data/dishlist.db.bak` before
   large edits.
2. Validate data by running `uv run python - <<'PY'` plus a short script that queries
   the database.
3. When pruning, never delete without exporting—archive first, then curate the live
   list.
