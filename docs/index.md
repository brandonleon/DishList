# DishList — User Guide

DishList is a self-hosted potluck coordinator. The host creates an event, shares a link, and guests sign up for what they're bringing. No accounts, no app installs — just a URL.

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

Negation phrases are detected and ignored — typing `peanut free` or `dairy-free` will **not** select the corresponding allergen tag.

Guests can adjust any auto-suggested tag freely before submitting.

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

The tag library is shared across all events and managed from the admin panel.

---

## Admin panel

The admin panel at `/pantry-admin` is restricted to specific IP addresses configured in `data/config.json`. It lets a system administrator:

- Manage the **global default dish categories** seeded into new events.
- **Add, rename, recategorise, or delete** individual dietary tags. Each tag chip has an inline edit (✎) and delete (✕) action.
- **Reset the tag library to defaults** — removes all current tags and reseeds the built-in 21-tag set. This also clears tag associations from all existing dishes.
- View and delete any event in the system.

To add your IP to the allowlist, edit `data/config.json` directly or use the admin panel once you're already on an allowed network.

---

## Troubleshooting

**I lost my management link.**
The management token is stored in `data/dishlist.db`. A system admin can retrieve it:
```bash
sqlite3 data/dishlist.db "SELECT name, management_token FROM events;"
```

**The guest board is showing stale data.**
The board uses HTMX partial refreshes on search. A hard browser refresh (`Cmd+Shift+R` / `Ctrl+Shift+R`) will reload everything.

**I can't access the admin panel.**
Your IP is not in the allowlist. Ask a system admin to add it to `data/config.json` under `admin_networks` (supports CIDR notation, e.g. `192.168.1.0/24`).

**Live reload isn't working.**
Set `DISHLIST_RELOAD=0` or run the app directly with `.venv/bin/python main.py`. Some environments (containers, certain CI systems) block file-system watchers.

**A tag auto-suggested incorrectly.**
Auto-suggest is a convenience helper — guests can uncheck any tag before submitting. If a keyword is causing consistent false positives, the tag library can be adjusted from the admin panel.
