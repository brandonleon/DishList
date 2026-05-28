# DishList — Claude Code Instructions

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

## Directory structure

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
