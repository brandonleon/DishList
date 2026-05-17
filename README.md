# DishList

A self-hosted potluck planner. Create an event, share the link, and let guests log what they're bringing — with dietary tags, notes, and a live dish board.

## Features

- **Multi-event** — each event gets its own shareable URL and an isolated guest board
- **Host contributions** — pin the house dishes to the top of the board so guests know what's already covered
- **Warning-based dietary tags** — guests tag dishes with what they *contain* (e.g. *Contains peanuts*, *Contains dairy*) rather than unverifiable "free-of" claims
- **Smart tag auto-suggest** — as a guest types their dish notes, relevant tags are automatically suggested in real time (e.g. typing "walnut" selects *Contains tree nuts*); negations like "peanut free" are detected and ignored
- **Card / table view toggle** — live-search across all guest submissions
- **Management page** — token-gated host dashboard to edit event settings, add/remove host items, and curate guest dishes
- **Admin portal** — IP-gated system panel to manage global dish categories, the dietary tag library, and all events
- **SQLite storage** — single `data/dishlist.db` file, trivial to back up or mount in Docker

## Getting started

```bash
uv sync
uv run python main.py          # local dev with live reload

# or run Uvicorn directly
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

Visit <http://127.0.0.1:8000> and hit **Create an Event** to get started.

> If your environment blocks file-system watchers (CI, containers), set `DISHLIST_RELOAD=0`
> or run `.venv/bin/python main.py` directly. If uv can't write to `~/.cache`, set
> `UV_CACHE_DIR=.uv-cache`.

## Docker

```bash
docker build -t dishlist .

docker run --rm -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  dishlist
```

Mount `data/` to persist the SQLite database and config between runs. Override the port with `-e PORT=8080`.

## URL structure

| Path | Description |
|---|---|
| `/` | Landing page |
| `/create` | Create a new event |
| `/e/{slug}` | Public guest board |
| `/e/{slug}/add` | Guest dish submission form |
| `/manage/{token}` | Host management dashboard |
| `/pantry-admin` | IP-gated system admin |

Event slugs are derived from the event name (max 32 chars including a 4-char uniqueness suffix) or fully random (8 chars) for more private events.

## Dietary tag library

Tags are organised into three categories out of the box:

| Category | Purpose |
|---|---|
| **Allergen warnings** | What the dish contains — *Contains peanuts*, *Contains dairy*, etc. |
| **Dietary preferences** | Lifestyle/dietary flags — *Vegan*, *Halal*, *Kosher*, etc. |
| **Content & serving** | Practical notes — *Spicy*, *Keep chilled*, *Reheat: oven*, *Prepared in a GF kitchen*, etc. |

The full library is managed from the admin panel — tags can be added, renamed, recategorised, or reset to defaults.

## Admin access

The admin panel lives at `/pantry-admin`. Access is restricted to IPs/networks listed in `data/config.json`. From the admin panel you can:

- Set the default dish categories shown on new event creation forms
- Add, rename, recategorise, or delete dietary tags
- Reset the tag library to the built-in defaults
- View and delete any event

## Data

| File | Contents |
|---|---|
| `data/dishlist.db` | All events, dishes, and tags (SQLite) |
| `data/config.json` | Global dish types and admin IP allowlist |
