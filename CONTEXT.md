# DishList — Domain Glossary

This file is the canonical source of domain language for DishList.
It is a glossary only — no implementation details, specs, or decisions.
Implementation decisions live in `docs/adr/`.

---

## Event

A hosted food-sharing gathering where guests pre-declare the contributions they intend to bring. The most common instance is a potluck, but the domain supports any gathering of this kind (dinner party, cookout, office lunch, etc.).

An Event has:
- a **name** and optional **description** and **date**
- a **Host** who creates it
- a set of allowed **Dish Types** that shape what guests can submit
- a public **Guest Board** (accessed via Slug)
- a private **Management Page** (accessed via Management Token)
- an **Open** or **Closed** state controlling whether new Submissions are accepted (stored as `is_active` in the database)

## Host

The person who creates and manages an Event. The Host sets the Event name, date, Dish Types, and their own contributions. The Host accesses the Management Page via the Management Token. There is exactly one Host per Event.

## Guest

A person who submits a Dish to an Event via the public Guest Board. Guests are not authenticated — their identity on a Submission is a self-reported display name (stored as `contributor` in the database). A Guest can submit multiple Dishes to the same Event.

---

## Submission

The record of a Guest's declared contribution to an Event. A Submission captures who is bringing something, what the Dish is, its Dish Type, any Tags, and optional notes. A Submission is scoped to one Event and is created when a Guest fills out the add-dish form.

Not to be confused with **Dish**, which is the food item itself. A Submission *describes* a Dish.

A **Host Contribution** is a special kind of Submission made by the Host, not a Guest. See **Host Contribution**.

## Host Contribution

A Dish added by the Host to represent what the house is already providing. Host Contributions are pinned to the top of the Guest Board so Guests can see what's covered before deciding what to bring. Structurally stored the same way as a Guest Submission but distinguished by the `is_host_item` flag.

## Dish

The food item being contributed to an Event. Described by a Submission. Has a name, a Dish Type, and optional dietary Tags and notes.

---

## Dish Type

A Host-defined label that categorizes Submissions within an Event (e.g. "Main", "Side", "Dessert", "Drinks"). Purely organizational — carries no system-enforced behavior beyond grouping and display. Each Event stores its own Dish Type list set at creation time. A system-level default list exists as a convenience seed for new Events but does not constrain what a Host can define.

## Tag

A label applied to a Submission that describes the Dish's dietary properties, allergen content, or serving logistics. Tags are system-managed (defined by the Host via admin tools) and selected by the Guest when submitting.

Tags follow the **warning-based tagging rule**: a Tag describes what a Dish *contains* or *is*, never what it lacks. "Contains peanuts" is valid; "Peanut-free" is not a Tag — it is an unverifiable negative claim. See ADR-0001.

## Tag Category

A grouping of Tags with a shared purpose. Three categories ship by default:

- **Allergen warnings** — what the Dish contains that may cause an allergic reaction
- **Dietary preferences** — lifestyle or religious dietary classifications (Vegan, Halal, Kosher, etc.)
- **Content & serving** — practical logistics (Spicy, Keep chilled, Reheat: oven, etc.)

Categories are ordered: Allergen warnings first, then Dietary preferences, then Content & serving.

## Tag Visibility

A Tag can be **visible** (shown immediately in the submission form) or **hidden** (surfaced only via search or keyword auto-detection). Hidden Tags exist for less common dietary needs that would clutter the default tag picker.

## Legacy: allergens and dietary_flags fields

Two fields on `DishEntry` predate the Tag system and are officially dead:

- **`allergens`** — a JSON list of free-text allergen strings. Replaced by the "Allergen warnings" Tag category. No longer exposed in any form or rendered in any template. The route handler still accepts it silently.
- **`dietary_flags`** — a denormalised cache of tag names derived from the `dish_tags` join table. The join table is the source of truth; this field is redundant. A fallback read path exists in `_row_to_entry` for backward compatibility with pre-Tag data.

Both should be removed in a future cleanup (database migration + model update). Tracked in issue #33. Do not build new features on top of either field.

## Tag Keyword

A keyword associated with a Tag used for client-side auto-detection. When a Guest types their dish name or notes, matching keywords cause the relevant Tag to be automatically suggested. Negations (e.g. "peanut free") are detected and ignored, consistent with the warning-based tagging rule.

---

## Event Slug

The short, URL-safe public identifier for an Event, embedded in the Guest Board URL (e.g. `/e/friendsgiving-a3f2`). Derived from the Event name with a random suffix for uniqueness, or fully random for more private events. Intended for sharing with Guests.

## Event State

An Event is either **Open** or **Closed** (stored as `is_active` in the database).

- **Open** — the Guest Board is visible and new Submissions are accepted.
- **Closed** — the Guest Board remains visible (read-only), but the add-dish form returns 403 and no new Submissions are accepted. Closed covers both the post-event case (the gathering happened) and early closure (the Host explicitly stops accepting Submissions before the event date).

The Host toggles this state from the Management Page.

## Guest Board

The public-facing page for an Event, accessible via the Event Slug. Displays Host Contributions (pinned at top) and all Guest Submissions. Guests can add a Submission and filter/search the board. No authentication required — anyone with the link can view and submit.

Live search filters Guest Submissions only. Host Contributions are always shown regardless of the search query — this is intentional so Guests always see what the house is providing.

## Management Page

The Host-only page for an Event, accessible via the Management Token. Allows the Host to edit Event settings, add and remove Host Contributions, curate Guest Submissions, and toggle the Event's active state. Not accessible to Guests.

## Application Config

The set of system-wide settings managed by the System Admin: default Dish Types, admin IP allowlist, and Web Admin Panel toggle. The intended source of truth is the `config_entries` table in SQLite. A `data/config.json` file is kept in sync as a migration shim for deployments that predate DB-based config — the file can override the DB if it is newer (last-writer-wins by timestamp). The end state is DB-only; `config.json` is not the source of truth. See ADR-0005.

## System Admin

The operator who deploys and maintains a DishList instance. Distinct from the Host, who manages a single Event. The System Admin configures global settings (default Dish Types, Tag library, admin access) via the CLI or Web Admin Panel. Has no in-app identity — access is granted by network position (IP allowlist) rather than credentials.

## Web Admin Panel

An optional IP-gated web interface at `/pantry-admin` for System Admin tasks: managing Events, Tags, Dish Types, and admin network settings. Disabled by default. Requires both an explicit enable command and at least one IP or CIDR range in the allowlist before it becomes reachable. Returns 404 when disabled — it does not reveal its own existence. See ADR-0002.

## CLI

The `dishlist` command-line tool. The primary interface for System Admin tasks. Always available regardless of Web Admin Panel state. Operates directly on the database and config files.

## Slug Mode

A property of how an Event Slug is generated at Event creation time. Two modes:

- **Discoverable** — the Slug is derived from the Event name with a short random suffix (e.g. `friendsgiving-a3f2`). Recognisable and easy to share verbally, but someone who knows the event name could guess it.
- **Private** — the Slug is a fully random 8-character string (e.g. `k7mx9qr2`). Effectively unguessable. Appropriate when the Host wants to control who can find the Guest Board.

Slug Mode is set once at Event creation and cannot be changed. It is a property of the Slug, not of the Event itself — it has no effect on access control beyond discoverability.

## Management Token

An unguessable secret token embedded in the Management Page URL (e.g. `/manage/<token>`). Grants Host-level access to edit Event settings, manage Host Contributions, and curate Guest Submissions. Acts as a lightweight security boundary — not authentication, but the token is 32 bytes of URL-safe entropy and access requires it to be leaked. Should be kept private and shared only with the Host.
