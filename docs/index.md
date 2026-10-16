# DishList — User Guide

DishList is a self-hosted potluck coordinator. The host creates an event, shares a link, and guests sign up for what they're bringing. No accounts, no app installs — just a URL.

---

## Installation & startup

```bash
uv sync
docker compose up -d postgres   # local PostgreSQL on 127.0.0.1:5432
export DATABASE_URL=postgresql://dishlist:dishlist@127.0.0.1:5432/dishlist
uv run dishlist db upgrade      # create or upgrade the schema
uv run dishlist serve           # with live reload
```

DishList stores everything in PostgreSQL, named by the `DATABASE_URL` environment variable. Every `dishlist` command and the server itself use it. On first start against an empty database the server creates the tables itself. After that, run `dishlist db upgrade` whenever you pull a new version: the server refuses to start until the schema is current.

Visit <http://127.0.0.1:8000> to open DishList.

### Docker Compose

```bash
docker compose up --build --detach
```

Compose runs two services: `postgres` (data kept in the `pgdata` volume) and `dishlist`, which applies pending migrations with `dishlist db upgrade` and then starts the server. Set `POSTGRES_PASSWORD` in the environment or a `.env` file to change the default database password, and `PORT` to change the published port.

A `Justfile` is included for server deployments:

```bash
just deploy   # git pull + docker compose up --build --detach
just stop     # docker compose down
just logs     # follow container logs
just ps       # container status
```

DishList is designed to run behind a reverse proxy such as Nginx Proxy Manager. It automatically trusts `X-Forwarded-Proto` and `X-Forwarded-For` headers, so HTTPS links and redirects work correctly without extra configuration.

By default those headers are trusted from any address. If the container is reachable by anything other than your proxy, restrict it to the proxy's address (comma-separated IPs) with the `FORWARDED_ALLOW_IPS` environment variable or `dishlist serve --forwarded-allow-ips`. The option wins over the variable. For example, in `docker-compose.yml`:

```yaml
environment:
  FORWARDED_ALLOW_IPS: "172.18.0.1"
```

#### Upgrading

Back up the database, then deploy as usual. The container runs `dishlist db upgrade` before it starts serving.

```bash
docker compose exec postgres pg_dump -U dishlist dishlist > dishlist-backup.sql
just deploy
```

**Upgrading from 0.5.x or earlier:** 0.6.0 moves from SQLite to PostgreSQL and does **not** import the old `data/dishlist.db`. Events, dishes and settings start fresh. Keep the old file (`cp data/dishlist.db data/dishlist-0.5.db.bak`) if you may want to roll back, and re-run any `dishlist admin` settings (web admin, networks, metrics) after the upgrade.

#### Admin commands in Docker

Run `dishlist admin` commands inside the app container, which already has `DATABASE_URL` set:

```bash
# Status check
docker compose exec dishlist dishlist admin status

# Enable web admin and add your IP
docker compose exec dishlist dishlist admin web enable --network 192.168.1.5
```

Settings changed from the CLI reach the running server within about 5 seconds; no restart or reload is needed.

### FastAPI Cloud

DishList deploys to [FastAPI Cloud](https://fastapicloud.com) with a [Neon](https://neon.tech) PostgreSQL database. FastAPI Cloud finds the app through `[tool.fastapi]` in `pyproject.toml` and ignores the paths listed in `.fastapicloudignore`.

First deploy:

```bash
uv run fastapi login
uv run fastapi deploy                                  # creates the app
uv run fastapi cloud integrations resources connect    # attach a Neon database; sets DATABASE_URL and redeploys
```

On its first start against the new, empty Neon database, DishList creates its tables and default data. Several instances starting at once is safe: they take turns, and only the first one does the work.

Later releases that add a migration need it applied before deploying. Use Neon's **direct** connection string (host without `-pooler`, from the Neon console's *Connect* dialog):

```bash
DATABASE_URL="<neon direct url>" uv run dishlist db upgrade
uv run fastapi deploy
```

If the upgrade is skipped, the new deployment fails its startup check and the previous one keeps serving.

Manage settings from your own machine by pointing the CLI at Neon:

```bash
DATABASE_URL="<neon direct url>" uv run dishlist admin web enable --network <your-ip>
```

Every running instance picks up the change within about 5 seconds.

> FastAPI Cloud starts the app itself, so `dishlist serve` options such as `--forwarded-allow-ips` don't apply there. Check that the admin and metrics IP allowlists see your real address before relying on them.

---

## Creating an event

1. Go to the landing page and click **Create an Event**.
2. Fill in the event details:
   - **Event name** *(required)* — shown at the top of the guest board.
   - **Date** — optional, displayed on the board for guests.
   - **Host / household name** — how your own contributions appear on the board (e.g. *The Smokehouse*). Defaults to *The House* if left blank.
   - **Description** — a short blurb guests see when they open the link.
3. Choose your **event URL style**:
   - **Name-based** *(default)* — derived from your event name, max 32 characters (e.g. `/e/friendsgiving-2026-wum2`). Easy to read and share.
   - **Fully random** — an 8-character code with no relation to the event name (e.g. `/e/x7k2m9p4`). Harder to guess — good for private events.
   - The preview updates live as you type so you know exactly what the link will look like before creating the event.
4. Edit the **dish categories** — one per line. These are the options guests pick from when submitting a dish. You can change them later from the management page.
5. Optionally add **host contributions** — dishes the house is already providing. These appear pinned at the top of the board.
6. Click **Create Event**.

After creation you land on your **management dashboard**. Bookmark that URL — it's the only way back to your host controls.

---

## Sharing with guests

From the management dashboard, copy the **Guest link** and share it however you like — group chat, email, calendar invite. Guests don't need an account.

The guest board shows:
- Host contributions pinned at the top, labelled with your household name.
- All guest submissions below, searchable and toggleable between card and table view.

---

## Guest dish submission

Guests open the guest link and click **Share Your Dish**. The form has four fields:

| Field | Notes |
|---|---|
| **Your name** | How the guest appears on the board |
| **Dish name** | What they're bringing |
| **Category** | Picked from the host's list |
| **Notes** | Serving size, prep details, allergens — anything guests should know |

### Dietary Tags

Below the notes field is a **Dietary Tags** section. Guests can search and select any tags that apply to their dish.

Tags are warning-based — they describe what a dish *contains*, not what it is free of. This keeps information honest and actionable for guests with allergies.

**Auto-suggest:** as the guest types their notes, matching tags are automatically selected in real time. For example:
- Typing `walnut` selects *Contains tree nuts*
- Typing `made with butter` selects *Contains dairy*
- Typing `reheat in the oven` selects *Reheat: oven*
- Typing `great for kids` selects *Kid-friendly*
- Typing `prepared in a gf kitchen` selects *Prepared in a GF kitchen*

Negation phrases are detected and ignored — typing `peanut free` or `dairy-free` will **not** select the corresponding allergen tag.

Guests can adjust any auto-suggested tag freely before submitting.

> **Need to change your submission?** The guest form doesn't support editing after submission. Ask the event host to update your entry from their management dashboard.

---

## Managing your event

Your management dashboard (`/manage/{token}`) lets you:

- **Edit event details** — name, date, description, host name, and dish categories.
- **Toggle submissions open/closed** — close the event to stop accepting new dishes.
- **Add, edit, or remove host contributions** — pin, fix, or unpin house dishes at any time.
- **Edit or delete any guest dish** — fix typos, update categories, or remove a dish.

> **Keep your management link safe.** Anyone with it can edit your event. It is not displayed on the guest board.

---

## Viewing the board

The guest board at `/e/{slug}` is public. It offers:

- **Search** — filters dishes live across name, contributor, category, and notes.
- **Card view** — visual grid, good for scanning at a glance.
- **Table view** — compact list, good for long events.

---

## Dietary tag library

Tags are organised into three categories:

| Category | Examples |
|---|---|
| **Allergen warnings** | Contains peanuts, Contains dairy, Contains gluten / wheat, Contains fish… |
| **Dietary preferences** | Vegan, Vegetarian, Pescatarian, Kosher, Halal |
| **Content & serving** | Spicy, Kid-friendly, Keep chilled, Prepared in a GF kitchen, Reheat: oven… |

The tag library is shared across all events and managed via the CLI or web admin.

---

## Administration

DishList is administered via the `dishlist` CLI. The web admin panel is disabled by default for security.

### CLI reference

```
dishlist serve                          Start the web server
dishlist admin status                   Show current config and system status

dishlist admin web enable               Enable /pantry-admin web panel
dishlist admin web enable --network IP  Enable and whitelist an IP in one step
dishlist admin web disable              Disable /pantry-admin web panel

dishlist admin networks list            List allowed admin IP/CIDR ranges
dishlist admin networks add <cidr>      Add an IP or CIDR (e.g. 192.168.1.5)
dishlist admin networks remove <cidr>   Remove an IP or CIDR

dishlist admin dish-types list          List default dish categories for new events
dishlist admin dish-types add <name>    Add a category
dishlist admin dish-types remove <name> Remove a category

dishlist admin tags list                List all dietary tags (with IDs)
dishlist admin tags add <name> <cat>    Add a tag to a category
dishlist admin tags remove <id>         Remove a tag by ID
dishlist admin tags reset               Reset tag library to built-in defaults

dishlist admin events list              List all events
dishlist admin events delete <id>       Delete an event and all its dishes
```

### Enabling the web admin panel

The web panel at `/pantry-admin` is **off by default**. To enable it:

```bash
# Add your IP and enable in one step
dishlist admin web enable --network 192.168.1.5

# Or separately
dishlist admin networks add 192.168.1.5
dishlist admin web enable
```

CIDR ranges work too — e.g. `10.0.0.0/24` to allow a whole subnet.

When enabled, `/pantry-admin` lets you manage dish categories, the dietary tag library, and all events from a browser. Only requests from allowed IPs can access it.

To disable:

```bash
dishlist admin web disable
```

### Web admin capabilities

When the web panel is enabled, it provides:

- Add, rename, recategorise, or delete individual dietary tags (inline edit on each chip)
- Reset the tag library to defaults (with confirmation — clears all tag associations from dishes)
- Manage global default dish categories
- View and delete any event

---

## Troubleshooting

**I lost my management link.**
Find the event's ID, then print its management path:
```bash
dishlist admin events list
dishlist admin events token <event_id>
```

**The server won't start: "Database schema is at …, but this release needs …".**
The database hasn't been migrated for this version. Run `dishlist db upgrade` with the same `DATABASE_URL`. If it says "no migration history", the database already holds tables that aren't DishList's; point `DATABASE_URL` at an empty database instead.

**`DATABASE_URL must be set`.**
Every `dishlist` command needs the database URL. Export it (see *Installation & startup*) or run the command inside the container with `docker compose exec dishlist …`.

**`/pantry-admin` returns 404.**
The web admin panel is disabled. Enable it with:
```bash
dishlist admin web enable --network <your-ip>
```

**I can't access `/pantry-admin` (403 Forbidden).**
Your IP is not in the allowlist. Add it:
```bash
dishlist admin networks add <your-ip>
```

**The guest board is showing stale data.**
The board uses HTMX partial refreshes on search. A hard browser refresh (`Cmd+Shift+R` / `Ctrl+Shift+R`) will reload everything.

**Live reload isn't working.**
Run `uv run dishlist serve --no-reload` or set `DISHLIST_RELOAD=0`. Some environments block file-system watchers.

**A tag auto-suggested incorrectly.**
Auto-suggest is a convenience helper — guests can uncheck any tag before submitting. Tags can be renamed or removed via `dishlist admin tags`.

**Running behind a reverse proxy (Nginx, Caddy, etc.) and seeing mixed-content warnings or broken search.**
DishList trusts `X-Forwarded-Proto` and `X-Forwarded-For` headers automatically. Make sure your proxy is sending them — Nginx Proxy Manager does by default. If links still generate as `http://`, verify the proxy is correctly forwarding these headers to port 8000 and that the proxy's address is allowed by `FORWARDED_ALLOW_IPS` (see above).
