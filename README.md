## DishList

FastAPI-powered potluck planner where guests can log what they are bringing, show allergens, and mark dietary flags.

### Highlights

- Bootstrap UI with a toggle between card and table views so guests can scan long lists.
- Admin portal to update dish types/IP allowlist plus edit or delete any submission.
- File-backed SQLite database (`data/dishlist.db`) ready to map to a Docker volume later.

### Getting started

```bash
uv sync
uv run main.py  # local dev (reload enabled)

# or start Uvicorn directly (e.g., for production)
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

Visit <http://127.0.0.1:8000/> to see the potluck board. Submissions are stored in `data/dishlist.db` (SQLite).

### Docker

```bash
# build the image (from the repo root)
docker build -t dishl-list .

# run the container, exposing port 8000 and persisting the SQLite/config files
docker run --rm -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  dishl-list
```

The container defaults to port `8000`, but you can override it with `-e PORT=8080`. Mounting the `data/` directory keeps `dishlist.db` and `config.json` in sync with the host so the admin tools retain state between runs.

### Admin access

The configuration screen lives at `/pantry-admin`. Only IPs/networks listed in `data/config.json` may hit that route. Use it to:

- Control the dish types shown in the submission form
- Update which IP ranges may open the admin URL
- Edit or delete dishes without grabbing anyone's laptop

All data is file-based so it is easy to reset or version control.

### Data storage

- Dish submissions live in the SQLite database at `data/dishlist.db`, making it easy to mount the file in a Docker volume later.
- Admin settings continue to live in `data/config.json` for straightforward editing or seeding.
