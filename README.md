# DishList

A self-hosted potluck planner. Create an event, share the link, and let guests log what they're bringing — with dietary tags, notes, and a live dish board.

## Features

- **Multi-event** — each event gets its own shareable URL and an isolated guest board
- **Host contributions** — pin the house dishes to the top of the board so guests know what's already covered
- **Warning-based dietary tags** — guests tag dishes with what they *contain* (e.g. *Contains peanuts*, *Contains dairy*) rather than unverifiable "free-of" claims
- **Smart tag auto-suggest** — as a guest types their dish notes, relevant tags are automatically suggested in real time; negations like "peanut free" are detected and ignored
- **Card / table view toggle** — live-search across all guest submissions
- **Management page** — token-gated host dashboard to edit event settings, add/remove host items, and curate guest dishes
- **CLI admin** — full `dishlist` command-line tool for managing configuration, tags, networks, and events without a browser
- **Web admin** — optional `/pantry-admin` panel (disabled by default; enable via CLI)
- **Prometheus metrics** — optional `/metrics` endpoint with its own IP allowlist (disabled by default; enable via CLI)
- **SQLite storage** — single `data/dishlist.db` file, trivial to back up or mount in Docker

## Getting started

```bash
uv sync
uv run dishlist serve          # local dev with live reload

# or run Uvicorn directly
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Visit <http://127.0.0.1:8000> and hit **Create an Event** to get started.

> To disable live reload: `uv run dishlist serve --no-reload` or set `DISHLIST_RELOAD=0`.
> If uv can't write to `~/.cache`, set `UV_CACHE_DIR=.uv-cache`.

## CLI

All admin tasks are available through the `dishlist` CLI:

```
dishlist serve                          Start the web server
dishlist admin status                   Show current config and system status

dishlist admin web enable               Enable /pantry-admin
dishlist admin web enable --network IP  Enable and add an allowed IP in one step
dishlist admin web disable              Disable /pantry-admin

dishlist admin networks list            List allowed admin IP/CIDR ranges
dishlist admin networks add <cidr>      Add an IP or CIDR (e.g. 192.168.1.5)
dishlist admin networks remove <cidr>   Remove an IP or CIDR

dishlist admin dish-types list          List default dish categories
dishlist admin dish-types add <name>    Add a category
dishlist admin dish-types remove <name> Remove a category

dishlist admin tags list                List dietary tags (with IDs)
dishlist admin tags add <name> <cat>    Add a tag to a category
dishlist admin tags remove <id>         Remove a tag by ID
dishlist admin tags reset               Reset tag library to built-in defaults

dishlist admin events list              List all events
dishlist admin events delete <id>       Delete an event and all its dishes

dishlist admin metrics status           Show /metrics endpoint status
dishlist admin metrics enable           Enable the Prometheus /metrics endpoint
dishlist admin metrics enable --network IP
                                        Enable and add an allowed scrape IP
dishlist admin metrics disable          Disable the Prometheus /metrics endpoint
dishlist admin metrics networks list    List allowed metrics scrape networks
dishlist admin metrics networks add <cidr>
                                        Add a CIDR to the metrics allowlist
dishlist admin metrics networks remove <cidr>
                                        Remove a CIDR from the metrics allowlist
```

## Web admin

The web panel at `/pantry-admin` is **disabled by default**. Enable it after adding your IP to the allowlist:

```bash
dishlist admin web enable --network 192.168.1.5
# or separately:
dishlist admin networks add 192.168.1.5
dishlist admin web enable
```

Disable it again at any time:

```bash
dishlist admin web disable
```

When disabled, `/pantry-admin` returns 404.

## Prometheus metrics

A Prometheus-format `/metrics` endpoint is available but **disabled by default**.
It has its own IP allowlist separate from the admin panel, so a scraper host can
be allowed without granting it admin access.

```bash
# Enable and add your scraper to the allowlist in one step
dishlist admin metrics enable --network 10.0.0.5
# or separately
dishlist admin metrics networks add 10.0.0.5
dishlist admin metrics enable
```

Disable again at any time:

```bash
dishlist admin metrics disable
```

When disabled, `/metrics` returns 404; when enabled, requests from outside the
allowlist get 403. Exposed metrics include `dishlist_http_requests_total`,
`dishlist_http_request_duration_seconds`, `dishlist_events_total`, and
`dishlist_dishes_total`.

## Docker

```bash
docker build -t dishlist .

docker run -d --name dishlist -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  dishlist
```

Mount `data/` to persist the database and config between runs. Override the port with `-e PORT=8080`.

### Admin commands in Docker

Run any `dishlist admin` command against a running container by exec-ing into it — or as a one-shot against the same data volume:

```bash
# Check status
docker exec dishlist dishlist admin status

# Enable web admin and whitelist your IP
docker exec dishlist dishlist admin web enable --network 192.168.1.5

# Or as a one-shot (no running container needed)
docker run --rm \
  -v "$(pwd)/data:/app/data" \
  dishlist dishlist admin web enable --network 192.168.1.5

# Any other admin subcommand works the same way
docker exec dishlist dishlist admin tags list
docker exec dishlist dishlist admin events list
```

> The data volume must be mounted so CLI changes are written to the same
> `dishlist.db` and `config.json` the server is reading.

## URL structure

| Path | Description |
|---|---|
| `/` | Landing page |
| `/create` | Create a new event |
| `/e/{slug}` | Public guest board |
| `/e/{slug}/add` | Guest dish submission form |
| `/manage/{token}` | Host management dashboard |
| `/pantry-admin` | IP-gated web admin (disabled by default) |
| `/metrics` | IP-gated Prometheus metrics (disabled by default) |

Event slugs are derived from the event name (max 32 chars including a 4-char uniqueness suffix) or fully random (8 chars) for more private events.

## Dietary tag library

Tags are organised into three categories out of the box:

| Category | Purpose |
|---|---|
| **Allergen warnings** | What the dish contains — *Contains peanuts*, *Contains dairy*, etc. |
| **Dietary preferences** | Lifestyle flags — *Vegan*, *Halal*, *Kosher*, etc. |
| **Content & serving** | Practical notes — *Spicy*, *Keep chilled*, *Reheat: oven*, *Prepared in a GF kitchen*, etc. |

Manage tags via `dishlist admin tags` or through the web admin panel.

## Data

| File | Contents |
|---|---|
| `data/dishlist.db` | All events, dishes, and tags (SQLite) |
| `data/config.json` | Dish types, admin IP allowlist, web admin toggle |
