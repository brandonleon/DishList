# Agents

These agents describe how we operate and maintain DishList so everyone knows who
does what.

## Testing

Run the test suite with `uv run` (the project uses `uv` for dependency and environment management).
Tests run against PostgreSQL, so start the compose database first:

```bash
docker compose up -d postgres
uv run pytest tests/
```

Each test gets its own clone of a migrated template database. Point the suite at
another server with `TEST_DATABASE_URL` (default
`postgresql://dishlist:dishlist@127.0.0.1:5432/postgres`); if no server is reachable,
database tests are skipped with a message saying so.

Common flags:
```bash
uv run pytest tests/ -v              # verbose output
uv run pytest tests/ -v --tb=short   # verbose with short tracebacks
uv run pytest tests/test_routes.py   # single file
uv run pytest tests/ -k "TestMetrics" # filter by test name
```

Do **not** invoke `python -m pytest` or a bare `pytest` directly — the system Python won't have project dependencies installed.

## Linting

Ruff is configured in `pyproject.toml` (`[tool.ruff]`). It is not a project dependency;
run it with `uvx`. Keep both clean before committing:

```bash
uvx ruff check app tests            # lint (add --fix for safe autofixes)
uvx ruff format --check app tests   # formatting (drop --check to apply)
```

Prefer fixing a finding over suppressing it. When a `# noqa` is genuinely right, name the
rule and give the reason on the same line, and never put it inside a multi-line SQL string.

## Directory Structure

```
DishList/
├── app/
│   ├── main.py          # FastAPI app, route definitions, middleware
│   ├── cli.py           # `dishlist` CLI (serve, db upgrade, admin commands)
│   ├── models.py        # Pydantic models / domain types
│   ├── storage.py       # PostgreSQL persistence layer (psycopg pool)
│   ├── config.py        # AppConfig model, DATABASE_URL, config load/save
│   ├── migrations/      # Alembic env + versions/ (schema history)
│   ├── metrics.py       # Prometheus metrics endpoint
│   ├── static/
│   │   ├── styles.css   # App stylesheet
│   │   ├── tag-picker.js# Dietary tag auto-suggest widget
│   │   └── favicon.ico
│   └── templates/
│       ├── base.html    # Shared layout (Bootstrap + HTMX imports)
│       ├── error.html   # Browser-facing HTTP error page
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
│           ├── flash.html
│           ├── table_rows.html
│           └── tag_picker.html
├── tests/
│   ├── conftest.py      # Shared fixtures (in-memory DB, test client)
│   ├── test_routes.py   # HTTP route integration tests
│   ├── test_cli_serve.py     # `dishlist serve` proxy-trust options
│   ├── test_migrations.py    # `dishlist db upgrade` and the startup schema check
│   ├── test_storage_events.py
│   └── test_storage_tags.py
├── docs/
│   ├── index.md         # User guide (source)
│   ├── ci-cd.md         # CI/CD deploy setup
│   ├── build.py         # Renders .md → .html via _template.html
│   └── _template.html
├── openspec/            # Behavior specs (specs/) and in-flight changes (changes/)
├── CHANGELOG.md         # Release notes
├── Justfile             # Dev/deploy tasks (just deploy, just logs, …)
├── Dockerfile
├── docker-compose.yml   # postgres + dishlist services
├── .fastapicloudignore  # Paths left out of FastAPI Cloud deploys
└── pyproject.toml       # Project metadata, dependencies, entry points
```

---

## Specs (OpenSpec)

`openspec/specs/` is the source of truth for what the app does. Behavior changes go
through an OpenSpec change (`/opsx:propose`, then `/opsx:apply`), which records the
delta against those specs; when a change ships, archive it (`/opsx:archive`) so
`openspec/specs/` stays current. Check with `openspec validate --strict`. Pure
refactors and docs-only changes don't need a spec delta.

Schema changes need a new Alembic revision in `app/migrations/versions/`, written as
raw SQL with `op.execute()` — databases are upgraded with `dishlist db upgrade`, never
recreated, and the server refuses to start on an outdated schema. Each revision must
keep the previous release working while old and new instances overlap: drop or rename
a column only in a later release than the one that stops using it (see
`schema-migration`). Never edit a revision that has shipped.

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

- Manages the PostgreSQL database (local compose `postgres` service, or Neon on
  FastAPI Cloud) and verifies submissions deserialize into `DishEntry` without errors.
- Owns schema migrations (`app/migrations/`) and runs `dishlist db upgrade` before
  deploys.
- Monitors table growth and archives old events if the list becomes unwieldy.

### Data Playbook

1. Back up with `pg_dump` before large edits or upgrades, e.g.
   `docker compose exec postgres pg_dump -U dishlist dishlist > backup.sql`
   (for Neon, run `pg_dump "<direct url>"`).
2. Validate data by running `uv run python - <<'PY'` plus a short script that queries
   the database.
3. When pruning, never delete without exporting—archive first, then curate the live
   list.
