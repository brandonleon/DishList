# Agents

These agents describe how we operate and maintain DishList so everyone knows who
does what.

## Docs Build

Whenever `docs/index.md` is updated, run the build script to regenerate the
rendered HTML:

```bash
uv run docs/build.py
```

This produces `docs/index.html` from the Markdown source and the
`docs/_template.html` layout. Always commit both `index.md` **and**
`index.html` together.

---

## Potluck Host Agent

- Owns the guest-facing experience: homepage, submission form, clever empty state,
  and dietary metadata.
- Keeps Bootstrap design cohesive and ensures templates stay accessible on mobile.
- Coordinates content updates, marketing blurbs, and copy tone to keep the potluck
  fun.

### Host Playbook

1. Run `uv sync` when dependencies change or after pulling from main.
2. Use `uv run dishlist serve` for manual QA; stop the server with `Ctrl+C`.
3. Update `app/templates/` or `app/static/` as needed, then refresh the browser to
   confirm.

## Admin Guardian Agent

- Manages the IP allowlist and web admin toggle via `dishlist admin` CLI.
- Curates the list of dish types so submitters always have relevant options.
- Audits allergen labeling and dietary flags to ensure clarity for guests with
  restrictions.
- Uses the management table to edit or delete dishes when updates are needed.

### Admin Playbook

1. Web admin is **disabled by default**. Enable it with:
   `dishlist admin web enable --network <your-ip>`
2. Manage dish types, networks, and tags via `dishlist admin` subcommands.
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
