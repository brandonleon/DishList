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
- **PostgreSQL storage** — a local container for development and self-hosting, or Neon on FastAPI Cloud; schema managed by versioned migrations

## Getting started

```bash
uv sync
docker compose up -d postgres   # local PostgreSQL on 127.0.0.1:5432
export DATABASE_URL=postgresql://dishlist:dishlist@127.0.0.1:5432/dishlist
uv run dishlist db upgrade      # create or upgrade the schema
uv run dishlist serve           # local dev with live reload
```

DishList stores everything in PostgreSQL, named by the `DATABASE_URL` environment variable. Every `dishlist` command and the server itself use it. Run `dishlist db upgrade` whenever you pull a new version: the server refuses to start until the schema is current.

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

## Configuration changes

Every running server re-reads its configuration from the database every few
seconds, so changes made with `dishlist admin` (locally, in a container, or
against a remote `DATABASE_URL`) take effect everywhere within about 5 seconds,
with no restart. The **Reload config** button in `/pantry-admin` applies them to
that server immediately.

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

## Docker Compose

```bash
docker compose up --build --detach
```

This starts PostgreSQL (data in the `pgdata` volume) and DishList, which runs
`dishlist db upgrade` before serving. Override the published port with `PORT`
and the database password with `POSTGRES_PASSWORD`.

A `Justfile` is included for server-side deployments:

```bash
just deploy   # git pull + docker compose up --build --detach
just stop     # docker compose down
just logs     # follow container logs
just ps       # show container status
```

### Reverse proxy / HTTPS

DishList is configured to run behind a reverse proxy (e.g. Nginx Proxy Manager). The server automatically trusts `X-Forwarded-Proto` and `X-Forwarded-For` headers, so URLs and redirects work correctly over HTTPS without any extra configuration.

Ensure your proxy passes the standard forwarded headers. Nginx Proxy Manager does this by default.

### Admin commands in Docker

Run any `dishlist admin` command inside the app container, which already has `DATABASE_URL` set:

```bash
docker compose exec dishlist dishlist admin status
docker compose exec dishlist dishlist admin web enable --network 192.168.1.5
docker compose exec dishlist dishlist admin events list
```

## FastAPI Cloud

DishList also deploys to [FastAPI Cloud](https://fastapicloud.com) with a
[Neon](https://neon.tech) database. In short: `uv run fastapi deploy`, then
`uv run fastapi cloud integrations resources connect` to attach a Neon database.
The first start creates the tables. See the [user guide](docs/index.md#fastapi-cloud)
for the full steps.

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

All events, dishes, tags and settings live in the PostgreSQL database named by
`DATABASE_URL`. The schema is defined by the Alembic migrations in
`app/migrations/`. An empty database is set up on first start; apply later
migrations with `dishlist db upgrade`. Back up with
`pg_dump`, e.g. `docker compose exec postgres pg_dump -U dishlist dishlist > backup.sql`.
