"""PostgreSQL-backed persistence for submissions, events, and config.

The database is named by the ``DATABASE_URL`` environment variable. The schema
is owned by the Alembic migrations in ``app/migrations``; apply them with
``dishlist db upgrade``.
"""

from __future__ import annotations

import logging
import re
import secrets
import string
from collections.abc import Generator, Sequence
from contextlib import contextmanager, suppress
from datetime import UTC, date, datetime
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .config import AppConfig, database_url
from .models import DishEntry, Event, Tag

_log = logging.getLogger(__name__)

Row = dict[str, Any]
Conn = Connection[Row]

CONFIG_CATEGORY_DISH_TYPES = "dish_type"
CONFIG_CATEGORY_ADMIN_NETWORKS = "admin_network"
CONFIG_CATEGORY_WEB_ADMIN = "web_admin"
CONFIG_CATEGORY_METRICS_NETWORKS = "metrics_network"
CONFIG_CATEGORY_METRICS = "metrics_enabled"

TAG_CATEGORY_ORDER = [
    "Allergen warnings",
    "Dietary preferences",
    "Content & serving",
]
DEFAULT_TAG_GROUPS = {
    "Dietary preferences": [
        "Vegan",
        "Vegetarian",
        "Pescatarian",
        "Kosher",
        "Halal",
    ],
    "Allergen warnings": [
        "Contains peanuts",
        "Contains tree nuts",
        "Contains dairy",
        "Contains eggs",
        "Contains gluten / wheat",
        "Contains soy",
        "Contains sesame",
        "Contains shellfish",
        "Contains fish",
        "Contains coconut",
        "Contains corn",
        "Contains mustard",
    ],
    "Content & serving": [
        "Contains alcohol",
        "Contains pork",
        "Spicy",
        "Kid-friendly",
        "Keep chilled",
        "Prepared in a GF kitchen",
        "Reheat: stovetop",
        "Reheat: oven",
        "Reheat: microwave",
        "Reheat: grill",
    ],
}

# Tags that are hidden by default — surfaced by search or keyword auto-detection
DEFAULT_HIDDEN_TAG_GROUPS: dict[str, list[str]] = {
    "Dietary preferences": [
        "Gluten-free",
        "Dairy-free",
        "Nut-free",
        "Egg-free",
        "Keto / Low-carb",
        "Paleo",
        "Low-sodium",
        "Sugar-free",
    ],
    "Content & serving": [
        "Finger food",
        "Best served warm",
        "Reheat: air fryer",
    ],
}
_CATEGORY_ORDER_LOOKUP = {
    category: idx for idx, category in enumerate(TAG_CATEGORY_ORDER)
}

# Default auto-detect keywords seeded for each built-in tag.
# Keys must match tag names in DEFAULT_TAG_GROUPS exactly.
DEFAULT_TAG_KEYWORDS: dict[str, list[str]] = {
    # ── Allergen warnings (visible) ────────────────────────────────────────────
    "Contains peanuts": ["peanut", "groundnut"],
    "Contains tree nuts": [
        "nut",
        "nuts",
        "almond",
        "cashew",
        "walnut",
        "pecan",
        "hazelnut",
        "pistachio",
        "macadamia",
    ],
    "Contains dairy": [
        "dairy",
        "milk",
        "cream",
        "cheese",
        "butter",
        "yogurt",
        "yoghurt",
        "whey",
    ],
    "Contains eggs": ["egg", "eggs"],
    "Contains gluten / wheat": ["gluten", "wheat", "flour"],
    "Contains soy": ["soy", "tofu", "edamame"],
    "Contains sesame": ["sesame", "tahini"],
    "Contains shellfish": [
        "shellfish",
        "shrimp",
        "prawn",
        "crab",
        "lobster",
        "scallop",
        "mussel",
        "oyster",
        "clam",
    ],
    "Contains fish": [
        "fish",
        "salmon",
        "tuna",
        "cod",
        "anchovy",
        "anchovies",
        "herring",
        "tilapia",
        "trout",
    ],
    "Contains coconut": [
        "coconut",
        "coconut milk",
        "coconut cream",
        "coconut oil",
        "desiccated coconut",
        "shredded coconut",
    ],
    "Contains corn": [
        "corn",
        "cornstarch",
        "cornmeal",
        "polenta",
        "grits",
        "corn syrup",
        "sweet corn",
    ],
    "Contains mustard": ["mustard", "dijon", "whole grain mustard"],
    # ── Content & serving (visible) ────────────────────────────────────────────
    "Contains alcohol": [
        "alcohol",
        "wine",
        "beer",
        "whiskey",
        "whisky",
        "vodka",
        "rum",
        "brandy",
        "bourbon",
        "liqueur",
    ],
    "Contains pork": [
        "pork",
        "bacon",
        "ham",
        "prosciutto",
        "pancetta",
        "chorizo",
        "salami",
        "lard",
    ],
    "Spicy": [
        "spicy",
        "chili",
        "chilli",
        "jalape\u00f1o",
        "jalapeno",
        "sriracha",
        "cayenne",
        "habanero",
    ],
    "Kid-friendly": ["for kids", "for children"],
    "Keep chilled": ["chilled", "refrigerate", "refrigerated"],
    "Prepared in a GF kitchen": [
        "gf kitchen",
        "gluten-free kitchen",
        "gluten free kitchen",
    ],
    "Reheat: stovetop": ["stovetop", "stove top", "hob"],
    "Reheat: oven": ["oven", "bake"],
    "Reheat: microwave": ["microwave"],
    "Reheat: grill": ["grill", "bbq", "barbecue", "broil"],
    # ── Dietary preferences (visible) ─────────────────────────────────────────
    "Vegan": ["vegan"],
    "Vegetarian": ["vegetarian", "veggie"],
    "Pescatarian": ["pescatarian"],
    "Kosher": ["kosher"],
    "Halal": ["halal"],
    # ── Dietary preferences (hidden) ──────────────────────────────────────────
    "Gluten-free": ["gluten-free", "gluten free", "gf"],
    "Dairy-free": ["dairy-free", "dairy free"],
    "Nut-free": ["nut-free", "nut free"],
    "Egg-free": ["egg-free", "egg free", "no eggs"],
    "Keto / Low-carb": ["keto", "ketogenic", "low-carb", "low carb", "keto-friendly"],
    "Paleo": ["paleo"],
    "Low-sodium": ["low sodium", "low-sodium", "low salt"],
    "Sugar-free": ["sugar-free", "sugar free", "no sugar", "no added sugar"],
    # ── Content & serving (hidden) ────────────────────────────────────────────
    "Finger food": ["finger food", "nibbles", "bites", "bite size", "bite-size"],
    "Best served warm": ["best served warm", "best warm", "serve warm"],
    "Reheat: air fryer": ["air fryer", "airfryer"],
}
_SLUG_ALPHABET = string.ascii_lowercase + string.digits


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:27]


def _random_suffix(length: int = 4) -> str:
    return "".join(secrets.choice(_SLUG_ALPHABET) for _ in range(length))


def _generate_management_token() -> str:
    return secrets.token_urlsafe(32)


class SchemaOutOfDateError(RuntimeError):
    """The database has not been migrated to the schema this release needs."""


_pool: ConnectionPool[Conn] | None = None


def _get_pool() -> ConnectionPool[Conn]:
    global _pool  # noqa: PLW0603 - one lazily created pool per process
    if _pool is None:
        _pool = ConnectionPool(
            database_url(),
            min_size=1,
            max_size=5,
            timeout=10,
            # Neon's pooled endpoint (PgBouncer, transaction mode) cannot keep
            # server-side prepared statements, so never prepare them.
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
            # Neon suspends idle compute; drop dead connections before use.
            check=ConnectionPool.check_connection,
            open=True,
        )
    return _pool


def close_pool() -> None:
    """Close the connection pool; the next query opens a fresh one."""
    global _pool  # noqa: PLW0603 - one lazily created pool per process
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def _get_connection() -> Generator[Conn]:
    """Yield a pooled connection inside a transaction (commit on success)."""
    with _get_pool().connection() as conn:
        yield conn


def _inserted_id(cursor: Any) -> int:
    """Return the id from an ``INSERT ... RETURNING id`` that ``cursor`` just ran."""
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("INSERT did not return a row id")
    return row["id"]


def current_schema_revision() -> str | None:
    """Return the migration revision recorded in the database, if any."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT to_regclass('alembic_version') IS NOT NULL AS present"
        ).fetchone()
        if not row or not row["present"]:
            return None
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    return row["version_num"] if row else None


def _database_is_empty() -> bool:
    """True when the current schema has no tables at all."""
    with _get_connection() as conn:
        row = conn.execute(
            """
            SELECT NOT EXISTS (
                SELECT 1 FROM pg_tables WHERE schemaname = current_schema()
            ) AS empty
            """
        ).fetchone()
    return bool(row and row["empty"])


def check_schema() -> None:
    """Make sure the database is at the latest migration revision.

    A completely empty database is set up by applying every migration. A
    database that is behind, or holds tables without migration history, is
    never changed here: startup fails and the operator runs
    ``dishlist db upgrade``.
    """
    from . import migrations  # noqa: PLC0415 - keeps Alembic off the import path

    head = migrations.head_revision()
    current = current_schema_revision()
    if current is None and _database_is_empty():
        _log.info("Empty database: applying migrations up to %s", head)
        migrations.upgrade(database_url())
        current = current_schema_revision()
    if current != head:
        found = current or "no migration history"
        raise SchemaOutOfDateError(
            f"Database schema is at {found}, but this release needs {head}. "
            "Run `dishlist db upgrade` against this DATABASE_URL first."
        )


# ── Event helpers ──────────────────────────────────────────────────────────────


def _row_to_event(row: Row) -> Event:
    return Event(
        id=row["id"],
        slug=row["slug"],
        management_token=row["management_token"],
        name=row["name"],
        description=row["description"],
        event_date=row["event_date"],
        host_name=row["host_name"],
        dish_types=row["dish_types"],
        is_active=row["is_active"],
        created_at=row["created_at"],
    )


def _parse_event_date(value: str | None) -> date | None:
    """Parse an ISO date from a form field; anything else is stored as no date."""
    if not value:
        return None
    with suppress(ValueError):
        return date.fromisoformat(value)
    return None


def _make_unique_slug(conn: Conn, name: str, use_random: bool) -> str:
    for _ in range(20):
        if use_random:
            slug = _random_suffix(8)
        else:
            base = _slugify(name)
            suffix = _random_suffix(4)
            slug = f"{base}-{suffix}" if base else suffix
        if not conn.execute(
            "SELECT id FROM events WHERE slug = %s", (slug,)
        ).fetchone():
            return slug
    raise ValueError("Could not generate a unique event slug — please try again")


def _make_unique_token(conn: Conn) -> str:
    for _ in range(20):
        token = _generate_management_token()
        if not conn.execute(
            "SELECT id FROM events WHERE management_token = %s", (token,)
        ).fetchone():
            return token
    raise ValueError("Could not generate a unique management token — please try again")


# ── Event CRUD ─────────────────────────────────────────────────────────────────


def create_event(
    name: str,
    description: str | None,
    event_date: str | None,
    host_name: str,
    dish_types: list[str],
    use_random_slug: bool = False,
) -> Event:
    with _get_connection() as conn:
        slug = _make_unique_slug(conn, name, use_random_slug)
        token = _make_unique_token(conn)
        now = datetime.now(UTC)
        safe_host = host_name.strip() or "The House"
        parsed_date = _parse_event_date(event_date)
        cursor = conn.execute(
            """
            INSERT INTO events (slug, management_token, name, description, event_date, host_name, dish_types, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s)
            RETURNING id
            """,
            (
                slug,
                token,
                name.strip(),
                description or None,
                parsed_date,
                safe_host,
                Jsonb(dish_types),
                now,
            ),
        )
        event_id = _inserted_id(cursor)

    return Event(
        id=event_id,
        slug=slug,
        management_token=token,
        name=name.strip(),
        description=description or None,
        event_date=parsed_date,
        host_name=safe_host,
        dish_types=dish_types,
        is_active=True,
        created_at=now,
    )


def get_event_by_slug(slug: str) -> Event | None:
    with _get_connection() as conn:
        row = conn.execute("SELECT * FROM events WHERE slug = %s", (slug,)).fetchone()
    return _row_to_event(row) if row else None


def get_event_by_management_token(token: str) -> Event | None:
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE management_token = %s", (token,)
        ).fetchone()
    return _row_to_event(row) if row else None


def get_event_by_id(event_id: int) -> Event | None:
    with _get_connection() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = %s", (event_id,)).fetchone()
    return _row_to_event(row) if row else None


def load_events() -> list[Event]:
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [_row_to_event(r) for r in rows]


def count_events() -> int:
    """Return the number of events without loading full rows."""
    with _get_connection() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]


def count_dishes() -> int:
    """Return the number of dishes without loading full rows."""
    with _get_connection() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM dishes").fetchone()["n"]


def update_event(
    event_id: int,
    name: str,
    description: str | None,
    event_date: str | None,
    host_name: str,
    dish_types: list[str],
    is_active: bool,
) -> None:
    safe_host = host_name.strip() or "The House"
    with _get_connection() as conn:
        conn.execute(
            """
            UPDATE events
            SET name = %s, description = %s, event_date = %s, host_name = %s, dish_types = %s, is_active = %s
            WHERE id = %s
            """,
            (
                name.strip(),
                description or None,
                _parse_event_date(event_date),
                safe_host,
                Jsonb(dish_types),
                is_active,
                event_id,
            ),
        )
        # House dishes are attributed to the host, so keep them in step with a rename.
        conn.execute(
            """
            UPDATE dishes SET contributor = %s
            WHERE event_id = %s AND is_host_item AND contributor != %s
            """,
            (safe_host, event_id, safe_host),
        )


def delete_event(event_id: int) -> None:
    with _get_connection() as conn:
        conn.execute("DELETE FROM events WHERE id = %s", (event_id,))


# ── Dish helpers ───────────────────────────────────────────────────────────────


def _row_to_entry(row: Row, tags: list[Tag] | None = None) -> DishEntry:
    tag_list = tags or []
    return DishEntry(
        id=row["id"],
        event_id=row["event_id"],
        contributor=row["contributor"],
        dish_name=row["dish_name"],
        dish_type=row["dish_type"],
        tag_ids=[tag.id for tag in tag_list],
        tags=tag_list,
        notes=row["notes"],
        is_host_item=row["is_host_item"],
        created_at=row["created_at"],
    )


def _category_sort_index(category: str) -> int:
    return _CATEGORY_ORDER_LOOKUP.get(category, len(TAG_CATEGORY_ORDER))


def _tag_sort_key(tag: Tag) -> tuple[int, int, str]:
    return (_category_sort_index(tag.category), tag.position, tag.name.lower())


def _load_tags_for_dishes(conn: Conn, dish_ids: Sequence[int]) -> dict[int, list[Tag]]:
    mapping: dict[int, list[Tag]] = {}
    if not dish_ids:
        return mapping
    rows = conn.execute(
        """
        SELECT dt.dish_id, t.id AS tag_id, t.name, t.category, t.position
        FROM dish_tags AS dt
        JOIN tags AS t ON t.id = dt.tag_id
        WHERE dt.dish_id = ANY(%s)
        ORDER BY t.category, t.position, LOWER(t.name)
        """,
        (list(dish_ids),),
    ).fetchall()
    for row in rows:
        mapping.setdefault(row["dish_id"], []).append(
            Tag(
                id=row["tag_id"],
                name=row["name"],
                category=row["category"],
                position=row["position"],
            )
        )
    return mapping


def _replace_dish_tags(conn: Conn, dish_id: int, tag_ids: Sequence[int]) -> None:
    conn.execute("DELETE FROM dish_tags WHERE dish_id = %s", (dish_id,))
    deduped = list(dict.fromkeys(tag_ids))
    if deduped:
        conn.cursor().executemany(
            "INSERT INTO dish_tags (dish_id, tag_id) VALUES (%s, %s)",
            [(dish_id, tag_id) for tag_id in deduped],
        )


# ── Dish CRUD ──────────────────────────────────────────────────────────────────


def load_dishes_for_event(event_id: int) -> list[DishEntry]:
    """All dishes for an event: host items first, then guest submissions by created_at ascending."""
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, event_id, contributor, dish_name, dish_type,
                   notes, is_host_item, created_at
            FROM dishes
            WHERE event_id = %s
            ORDER BY is_host_item DESC, created_at ASC, id ASC
            """,
            (event_id,),
        ).fetchall()
        tag_map = _load_tags_for_dishes(conn, [row["id"] for row in rows])
    return [_row_to_entry(row, tag_map.get(row["id"])) for row in rows]


def load_all_dishes() -> list[DishEntry]:
    """All dishes across all events, newest first. For system-admin overview."""
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, event_id, contributor, dish_name, dish_type,
                   notes, is_host_item, created_at
            FROM dishes
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
        tag_map = _load_tags_for_dishes(conn, [row["id"] for row in rows])
    return [_row_to_entry(row, tag_map.get(row["id"])) for row in rows]


def get_dish(dish_id: int) -> DishEntry | None:
    with _get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, event_id, contributor, dish_name, dish_type,
                   notes, is_host_item, created_at
            FROM dishes WHERE id = %s
            """,
            (dish_id,),
        ).fetchone()
        tag_map = _load_tags_for_dishes(conn, [dish_id]) if row else {}
    return _row_to_entry(row, tag_map.get(dish_id)) if row else None


def add_dish(entry: DishEntry) -> int:
    """Insert a dish and return its new id."""
    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO dishes (event_id, contributor, dish_name, dish_type,
                                notes, is_host_item, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                entry.event_id,
                entry.contributor,
                entry.dish_name,
                entry.dish_type,
                entry.notes,
                entry.is_host_item,
                entry.created_at,
            ),
        )
        dish_id = _inserted_id(cursor)
        _replace_dish_tags(conn, dish_id, entry.tag_ids)
    return dish_id


def update_dish(dish_id: int, entry: DishEntry) -> None:
    with _get_connection() as conn:
        conn.execute(
            """
            UPDATE dishes
            SET contributor = %s, dish_name = %s, dish_type = %s, notes = %s, created_at = %s
            WHERE id = %s
            """,
            (
                entry.contributor,
                entry.dish_name,
                entry.dish_type,
                entry.notes,
                entry.created_at,
                dish_id,
            ),
        )
        _replace_dish_tags(conn, dish_id, entry.tag_ids)


def delete_dish(dish_id: int) -> None:
    with _get_connection() as conn:
        conn.execute("DELETE FROM dishes WHERE id = %s", (dish_id,))


# ── Tag CRUD ───────────────────────────────────────────────────────────────────


def _load_keywords_for_tags(conn: Conn, tag_ids: Sequence[int]) -> dict[int, list[str]]:
    """Return a mapping of tag_id → list of keywords."""
    if not tag_ids:
        return {}
    rows = conn.execute(
        "SELECT tag_id, keyword FROM tag_keywords WHERE tag_id = ANY(%s) ORDER BY tag_id, id",
        (list(tag_ids),),
    ).fetchall()
    mapping: dict[int, list[str]] = {}
    for row in rows:
        mapping.setdefault(row["tag_id"], []).append(row["keyword"])
    return mapping


def _set_tag_keywords_conn(conn: Conn, tag_id: int, keywords: list[str]) -> None:
    """Replace all keywords for a tag within an existing connection/transaction."""
    cleaned = [kw.strip().lower() for kw in keywords if kw.strip()]
    deduped = list(dict.fromkeys(cleaned))
    conn.execute("DELETE FROM tag_keywords WHERE tag_id = %s", (tag_id,))
    if deduped:
        conn.cursor().executemany(
            "INSERT INTO tag_keywords (tag_id, keyword) VALUES (%s, %s)",
            [(tag_id, kw) for kw in deduped],
        )


def load_tags() -> list[Tag]:
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, category, position, is_hidden FROM tags"
        ).fetchall()
        tag_ids = [row["id"] for row in rows]
        kw_map = _load_keywords_for_tags(conn, tag_ids)
    tags = [
        Tag(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            position=row["position"],
            is_hidden=row["is_hidden"],
            keywords=kw_map.get(row["id"], []),
        )
        for row in rows
    ]
    tags.sort(key=_tag_sort_key)
    return tags


def get_tag_counts() -> dict[str, int]:
    """Return total, visible, and hidden tag counts for summary display."""
    with _get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM tags").fetchone()["n"]
        hidden = conn.execute(
            "SELECT COUNT(*) AS n FROM tags WHERE is_hidden"
        ).fetchone()["n"]
    return {"total": total, "visible": total - hidden, "hidden": hidden}


def load_tag_groups() -> list[tuple[str, list[Tag]]]:
    tags = load_tags()
    grouped: dict[str, list[Tag]] = {}
    for tag in tags:
        grouped.setdefault(tag.category, []).append(tag)
    ordered: list[tuple[str, list[Tag]]] = []
    for category in TAG_CATEGORY_ORDER:
        bucket = grouped.pop(category, None)
        if bucket:
            ordered.append((category, bucket))
    for category in sorted(grouped.keys()):
        ordered.append((category, grouped[category]))
    return ordered


def get_tags_by_ids(tag_ids: Sequence[int]) -> list[Tag]:
    if not tag_ids:
        return []
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, category, position, is_hidden FROM tags WHERE id = ANY(%s)",
            (list(tag_ids),),
        ).fetchall()
        kw_map = _load_keywords_for_tags(conn, [row["id"] for row in rows])
    tags = [
        Tag(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            position=row["position"],
            is_hidden=row["is_hidden"],
            keywords=kw_map.get(row["id"], []),
        )
        for row in rows
    ]
    tags.sort(key=_tag_sort_key)
    return tags


def get_tag_categories() -> list[str]:
    """Return ordered categories: predefined first, then any extras found in the DB."""
    with _get_connection() as conn:
        rows = conn.execute("SELECT DISTINCT category FROM tags").fetchall()
    db_cats = {row["category"] for row in rows}
    result = list(TAG_CATEGORY_ORDER)
    for cat in sorted(db_cats):
        if cat not in result:
            result.append(cat)
    return result


def set_tag_keywords(tag_id: int, keywords: list[str]) -> None:
    """Public helper: replace all keywords for a tag."""
    with _get_connection() as conn:
        _set_tag_keywords_conn(conn, tag_id, keywords)


def toggle_tag_visibility(tag_id: int) -> bool:
    """Flip is_hidden for a tag. Returns the new is_hidden value."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT is_hidden FROM tags WHERE id = %s", (tag_id,)
        ).fetchone()
        if not row:
            raise ValueError("Tag not found")
        new_val = not row["is_hidden"]
        conn.execute("UPDATE tags SET is_hidden = %s WHERE id = %s", (new_val, tag_id))
    return new_val


def update_tag(
    tag_id: int,
    name: str,
    category: str,
    keywords: list[str] | None = None,
    is_hidden: bool | None = None,
) -> None:
    cleaned = name.strip()
    cat = category.strip()
    if not cleaned:
        raise ValueError("Tag name cannot be empty")
    if not cat:
        raise ValueError("Category cannot be empty")
    with _get_connection() as conn:
        if conn.execute(
            "SELECT id FROM tags WHERE LOWER(name) = LOWER(%s) AND id != %s",
            (cleaned, tag_id),
        ).fetchone():
            raise ValueError("A tag with that name already exists")
        if is_hidden is None:
            conn.execute(
                "UPDATE tags SET name = %s, category = %s WHERE id = %s",
                (cleaned, cat, tag_id),
            )
        else:
            conn.execute(
                "UPDATE tags SET name = %s, category = %s, is_hidden = %s WHERE id = %s",
                (cleaned, cat, is_hidden, tag_id),
            )
        if keywords is not None:
            _set_tag_keywords_conn(conn, tag_id, keywords)


def reset_tags_to_defaults() -> None:
    """Delete all tags (and their dish associations via CASCADE) then reseed defaults."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM tags")
        _insert_default_tags(conn)


def create_tag(
    name: str,
    category: str,
    keywords: list[str] | None = None,
    is_hidden: bool = False,
) -> Tag:
    cleaned_name = name.strip()
    cat = category.strip()
    if not cleaned_name:
        raise ValueError("Tag name cannot be empty")
    if not cat:
        raise ValueError("Category cannot be empty")
    with _get_connection() as conn:
        if conn.execute(
            "SELECT id FROM tags WHERE LOWER(name) = LOWER(%s)", (cleaned_name,)
        ).fetchone():
            raise ValueError("That tag already exists")
        row = conn.execute(
            "SELECT COALESCE(MAX(position), -1) AS max_position FROM tags WHERE category = %s",
            (cat,),
        ).fetchone()
        next_position = row["max_position"] + 1
        cursor = conn.execute(
            "INSERT INTO tags (name, category, position, is_hidden) VALUES (%s, %s, %s, %s) RETURNING id",
            (cleaned_name, cat, next_position, is_hidden),
        )
        tag_id = _inserted_id(cursor)
        kw_list: list[str] = []
        if keywords:
            kw_list = [kw.strip().lower() for kw in keywords if kw.strip()]
            kw_list = list(dict.fromkeys(kw_list))
            _set_tag_keywords_conn(conn, tag_id, kw_list)
    return Tag(
        id=tag_id,
        name=cleaned_name,
        category=cat,
        position=next_position,
        keywords=kw_list,
        is_hidden=is_hidden,
    )


def delete_tag(tag_id: int) -> None:
    with _get_connection() as conn:
        conn.execute("DELETE FROM tags WHERE id = %s", (tag_id,))


# ── Config persistence ─────────────────────────────────────────────────────────


def load_app_config_from_db() -> tuple[AppConfig, datetime] | None:
    with _get_connection() as conn:
        dish_rows = conn.execute(
            "SELECT value, position, updated_at FROM config_entries WHERE category = %s ORDER BY position ASC, id ASC",
            (CONFIG_CATEGORY_DISH_TYPES,),
        ).fetchall()
        admin_rows = conn.execute(
            "SELECT value, position, updated_at FROM config_entries WHERE category = %s ORDER BY position ASC, id ASC",
            (CONFIG_CATEGORY_ADMIN_NETWORKS,),
        ).fetchall()
        web_admin_rows = conn.execute(
            "SELECT value, updated_at FROM config_entries WHERE category = %s",
            (CONFIG_CATEGORY_WEB_ADMIN,),
        ).fetchall()
        metrics_network_rows = conn.execute(
            "SELECT value, position, updated_at FROM config_entries WHERE category = %s ORDER BY position ASC, id ASC",
            (CONFIG_CATEGORY_METRICS_NETWORKS,),
        ).fetchall()
        metrics_enabled_rows = conn.execute(
            "SELECT value, updated_at FROM config_entries WHERE category = %s",
            (CONFIG_CATEGORY_METRICS,),
        ).fetchall()
    if (
        not dish_rows
        and not admin_rows
        and not web_admin_rows
        and not metrics_network_rows
        and not metrics_enabled_rows
    ):
        return None
    dish_types = [row["value"] for row in dish_rows]
    admin_networks = [row["value"] for row in admin_rows]
    # Migration: existing DB rows without a web_admin entry and with custom
    # networks are treated as enabled to preserve prior behaviour.
    if web_admin_rows:
        web_admin_enabled = web_admin_rows[0]["value"] == "true"
    else:
        web_admin_enabled = bool(admin_networks)
    metrics_networks = [row["value"] for row in metrics_network_rows]
    if not metrics_networks:
        metrics_networks = ["127.0.0.1/32"]
    metrics_enabled = (
        bool(metrics_enabled_rows) and metrics_enabled_rows[0]["value"] == "true"
    )
    all_rows = (
        list(dish_rows)
        + list(admin_rows)
        + list(web_admin_rows)
        + list(metrics_network_rows)
        + list(metrics_enabled_rows)
    )
    latest_updated = _latest_updated_at(all_rows)
    return AppConfig(
        dish_types=dish_types,
        admin_networks=admin_networks,
        web_admin_enabled=web_admin_enabled,
        metrics_networks=metrics_networks,
        metrics_enabled=metrics_enabled,
    ), latest_updated


def save_app_config_to_db(config: AppConfig) -> None:
    timestamp = datetime.now(UTC)
    with _get_connection() as conn:
        conn.execute(
            "DELETE FROM config_entries WHERE category IN (%s, %s, %s, %s, %s)",
            (
                CONFIG_CATEGORY_DISH_TYPES,
                CONFIG_CATEGORY_ADMIN_NETWORKS,
                CONFIG_CATEGORY_WEB_ADMIN,
                CONFIG_CATEGORY_METRICS_NETWORKS,
                CONFIG_CATEGORY_METRICS,
            ),
        )
        _bulk_insert_config_entries(
            conn, CONFIG_CATEGORY_DISH_TYPES, config.dish_types, timestamp
        )
        _bulk_insert_config_entries(
            conn, CONFIG_CATEGORY_ADMIN_NETWORKS, config.admin_networks, timestamp
        )
        _bulk_insert_config_entries(
            conn,
            CONFIG_CATEGORY_WEB_ADMIN,
            ["true" if config.web_admin_enabled else "false"],
            timestamp,
        )
        _bulk_insert_config_entries(
            conn,
            CONFIG_CATEGORY_METRICS_NETWORKS,
            config.metrics_networks,
            timestamp,
        )
        _bulk_insert_config_entries(
            conn,
            CONFIG_CATEGORY_METRICS,
            ["true" if config.metrics_enabled else "false"],
            timestamp,
        )


def _bulk_insert_config_entries(
    conn: Conn, category: str, values: list[str], timestamp: datetime
) -> None:
    if not values:
        return
    conn.cursor().executemany(
        "INSERT INTO config_entries (category, value, position, updated_at) VALUES (%s, %s, %s, %s)",
        [(category, value, idx, timestamp) for idx, value in enumerate(values)],
    )


def _latest_updated_at(rows: list[Row]) -> datetime:
    if not rows:
        return datetime.fromtimestamp(0, tz=UTC)
    return max(row["updated_at"] for row in rows)


# ── Seeding ────────────────────────────────────────────────────────────────────
# A new database is seeded by the baseline migration. These defaults are used
# only by ``reset_tags_to_defaults``.


def _insert_default_tag(
    conn: Conn, name: str, category: str, position: int, is_hidden: bool
) -> None:
    cursor = conn.execute(
        "INSERT INTO tags (name, category, position, is_hidden) VALUES (%s, %s, %s, %s) RETURNING id",
        (name, category, position, is_hidden),
    )
    tag_id = _inserted_id(cursor)
    kws = DEFAULT_TAG_KEYWORDS.get(name, [])
    if kws:
        _set_tag_keywords_conn(conn, tag_id, kws)


def _insert_default_tags(conn: Conn) -> None:
    """Seed all default tags (visible, then hidden) with their keywords."""
    for category in TAG_CATEGORY_ORDER:
        visible = DEFAULT_TAG_GROUPS.get(category, [])
        for position, name in enumerate(visible):
            _insert_default_tag(conn, name, category, position, is_hidden=False)
        for offset, name in enumerate(DEFAULT_HIDDEN_TAG_GROUPS.get(category, [])):
            _insert_default_tag(
                conn, name, category, len(visible) + offset, is_hidden=True
            )
