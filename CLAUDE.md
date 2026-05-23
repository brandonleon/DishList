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
