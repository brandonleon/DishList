# DishList — User Guide

DishList is a self-hosted potluck coordinator. The host creates an event, shares a link, and guests sign up for what they're bringing. No accounts, no app installs — just a URL.

---

## Installation & startup

```bash
uv sync
uv run dishlist serve          # with live reload

# or directly with Uvicorn
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Visit <http://127.0.0.1:8000> to open DishList.

### Docker

```bash
docker build -t dishlist .

docker run -d --name dishlist -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  dishlist
```

Mount `data/` so the database and config persist between container restarts. Override the port with `-e PORT=8080`.

A `Justfile` is included for server deployments:

```bash
just deploy   # git pull + docker compose up --build --detach
just stop     # docker compose down
just logs     # follow container logs
just ps       # container status
```

DishList is designed to run behind a reverse proxy such as Nginx Proxy Manager. Set `FORWARDED_ALLOW_IPS` to the proxy IPs or CIDR ranges in front of the app, as seen by the app, so HTTPS links, redirects and client IPs work correctly. Include every proxy in the chain (with a CDN, add its published ranges). Do not use `*`: it lets any client fake its IP and get past the admin and metrics allowlists.

#### Admin commands in Docker

Run `dishlist admin` commands against the running container with `docker exec`, or as a one-shot using the same data volume:

```bash
# Status check
docker exec dishlist dishlist admin status

# Enable web admin and add your IP (against running container)
docker exec dishlist dishlist admin web enable --network 192.168.1.5

# Same thing as a one-shot (container doesn't need to be running)
docker run --rm \
  -v "$(pwd)/data:/app/data" \
  dishlist dishlist admin web enable --network 192.168.1.5
```

> Always mount the same `data/` volume so CLI changes are written to the
> same `dishlist.db` and `config.json` the server is using.

---

### Database

DishList stores data in SQLite (`data/dishlist.db`) by default. If your host does not keep the filesystem between deploys, every redeploy would erase your events, so set `DATABASE_URL` to a PostgreSQL connection string instead:

```bash
DATABASE_URL="postgresql://user:password@host/dbname?sslmode=require"
```

The tables are created on first start, inside a dedicated PostgreSQL schema named `dishlist` (change it with `DATABASE_SCHEMA`), so DishList never reads or modifies tables that already exist in `public`. There is nothing to migrate for a new database. The server log prints the backend in use at startup (credentials are never printed). The `dishlist admin` commands use the same `DATABASE_URL`, so run them with it set.

---

## Creating an event

1. Go to the landing page and click **Create an Event**.
2. Fill in the event details:
   - **Event name** *(required)* — shown at the top of the guest board.
   - **Date** — optional, displayed on the board for guests.
   - **Host / household name** — how your own contributions appear on the board (e.g. *The Smokehouse*). Defaults to *The House* if left blank.
   - **Description** — a short blurb guests see when they open the link.
   - **Your email** *(optional, only shown if the server has email set up)* — we'll email you your private management link. Guests never see it, and it is deleted after your event is over. Tick **Email me when a guest adds a dish** to get a notice for each new dish.
3. Choose your **event URL style**:
   - **Name-based** *(default)* — derived from your event name, max 32 characters (e.g. `/e/friendsgiving-2026-wum2`). Easy to read and share.
   - **Fully random** — an 8-character code with no relation to the event name (e.g. `/e/x7k2m9p4`). Harder to guess — good for private events.
   - The preview updates live as you type so you know exactly what the link will look like before creating the event.
4. Edit the **dish categories** — one per line. These are the options guests pick from when submitting a dish. You can change them later from the management page.
5. Optionally add **host contributions** — dishes the house is already providing. These appear pinned at the top of the board.
6. Click **Create Event**.

After creation you land on your **management dashboard**. Bookmark that URL — it's the only way back to your host controls. If you gave an email, the link is also in your inbox, and you can send it to yourself again with **Email me this management link**.

---

## Lost a link? Find your events and dishes by email

If the server has email set up and you gave an email address when you created an event or added a dish, you can get your links again. Open **Find your events and dishes by email** on the home page (or go to `/find`), enter the address and submit.

If anything is stored under that address you'll receive one email:
- for **events you host**: the public guest link and your private management link;
- for **dishes you added**: the link to each event's public page (no management link; ask the host for any change).

The page always shows the same message — *"If an event or dish is associated with this email, you will receive an email with details."* — whether or not the address is known, so it can't be used to check who has signed up, and mistyped addresses are never emailed. Addresses are deleted once an event is over, so only live events can be found. Lookups are rate-limited.

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
- **Add or remove host contributions** — pin or unpin house dishes at any time.
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

dishlist admin email test --to <addr>   Send a test email through Resend
```

### Email (optional)

DishList can email hosts their management link and email guests a confirmation. It is off unless you set these environment variables:

| Variable | Purpose |
|---|---|
| `RESEND_API_KEY` | Your [Resend](https://resend.com) API key. |
| `RESEND_FROM` | Sender, e.g. `DishList <potluck@yourdomain.com>`. The domain must be verified in Resend to send to arbitrary recipients. |
| `PUBLIC_BASE_URL` | Public origin used in email links, e.g. `https://dish.example.com`. Falls back to the request's own URL. |

With these set, the create-event and add-dish forms show an optional email field. Addresses are never shown on the board and are deleted once the event is closed, its date has passed, or 30 days after creation for undated events. Guest emails tell the guest to contact the host for any change; guests have no edit link. Sends are rate-limited per IP, per recipient and per event. Check your setup with `dishlist admin email test --to you@example.com`.

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
If you gave an email when creating the event, check your inbox, or open any earlier email from DishList. Otherwise retrieve it from the database:
```bash
sqlite3 data/dishlist.db "SELECT name, management_token FROM events;"
```
or, with PostgreSQL, run `dishlist admin events token <id>` with `DATABASE_URL` set (list ids with `dishlist admin events list`).

**My events disappear after every deploy.**
Your host is wiping the local `data/` folder. Set `DATABASE_URL` to a PostgreSQL database (see Database above).

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
DishList only accepts `X-Forwarded-Proto` and `X-Forwarded-For` from addresses listed in `FORWARDED_ALLOW_IPS`. Add your proxy's address as the app sees it, and make sure the proxy is sending the headers — Nginx Proxy Manager does by default. If links still generate as `http://`, or every visitor shows the same IP, this setting is the first thing to check.
