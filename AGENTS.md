# Agents

These agents describe how we operate and maintain DishList so everyone knows who
does what.

## Testing

Run the test suite with `uv run` (the project uses `uv` for dependency and environment management):

```bash
uv run pytest tests/
```

Common flags:
```bash
uv run pytest tests/ -v              # verbose output
uv run pytest tests/ -v --tb=short   # verbose with short tracebacks
uv run pytest tests/test_routes.py   # single file
uv run pytest tests/ -k "TestMetrics" # filter by test name
```

Do **not** invoke `python -m pytest` or a bare `pytest` directly — the system Python won't have project dependencies installed.

## Directory Structure

```
DishList/
├── app/
│   ├── main.py          # FastAPI app, route definitions, middleware
│   ├── cli.py           # `dishlist` CLI (serve + admin commands)
│   ├── models.py        # Pydantic models / domain types
│   ├── storage.py       # SQLite persistence layer
│   ├── config.py        # Config load/save (config.json in data/)
│   ├── metrics.py       # Prometheus metrics endpoint
│   ├── static/
│   │   ├── styles.css   # App stylesheet
│   │   ├── tag-picker.js# Dietary tag auto-suggest widget
│   │   └── favicon.ico
│   └── templates/
│       ├── base.html    # Shared layout (Bootstrap + HTMX imports)
│       ├── landing.html # Home page / event list
│       ├── create_event.html
│       ├── home.html    # Guest board (card/table view)
│       ├── add.html     # Guest dish submission form
│       ├── manage.html  # Host management dashboard
│       ├── manage_edit_dish.html
│       ├── admin.html   # Web admin panel (/pantry-admin)
│       ├── admin_tags.html
│       ├── admin_edit_dish.html
│       └── partials/    # HTMX partial responses
│           ├── card_grid.html
│           ├── table_rows.html
│           └── tag_picker.html
├── tests/
│   ├── conftest.py      # Shared fixtures (in-memory DB, test client)
│   ├── test_routes.py   # HTTP route integration tests
│   ├── test_storage_events.py
│   └── test_storage_tags.py
├── docs/
│   ├── index.md         # User guide (source)
│   ├── ci-cd.md         # CI/CD deploy setup
│   ├── build.py         # Renders .md → .html via _template.html
│   └── _template.html
├── data/                # Runtime data (gitignored)
│   ├── dishlist.db      # SQLite database
│   └── config.json      # App configuration
├── Justfile             # Dev/deploy tasks (just deploy, just logs, …)
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml       # Project metadata, dependencies, entry points
```

---

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
