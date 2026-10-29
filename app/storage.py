"""Persistence for submissions, events, and config.

SQLite is the default (a local file under ``data/``). Setting ``DATABASE_URL``
to a ``postgresql://`` URL, for example a Neon connection string, switches to
PostgreSQL through a small connection wrapper (:class:`_Conn`) so the queries
below are written once, with ``?`` placeholders, and run on either backend.
Use PostgreSQL wherever the filesystem is not persistent across deploys.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import string
import threading
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, Generator, List, Optional, Sequence, Tuple

from .config import AppConfig, DATA_DIR
from .models import DishEntry, Event, Tag

# SQLite file used when DATABASE_URL is not a PostgreSQL URL.
DB_PATH = DATA_DIR / "dishlist.db"

Row = Any  # sqlite3.Row or a psycopg dict row; both support row["column"]

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
DEFAULT_HIDDEN_TAG_GROUPS: Dict[str, List[str]] = {
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
DEFAULT_TAG_KEYWORDS: Dict[str, List[str]] = {
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


def _postgres_url() -> Optional[str]:
    """The PostgreSQL URL from DATABASE_URL, or None to use SQLite.

    Read on every call so tests and operators can switch backends by changing
    the environment; any other value (including sqlite:///...) means SQLite.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    return url if url.startswith(("postgres://", "postgresql://")) else None


DEFAULT_SCHEMA = "dishlist"
_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def _schema_name() -> str:
    """PostgreSQL schema that holds DishList's tables (DATABASE_SCHEMA, default ``dishlist``).

    A dedicated schema keeps DishList from adopting, or colliding with, tables
    of the same name that already exist in ``public`` (shared or reused
    databases), since ``CREATE TABLE IF NOT EXISTS`` would silently reuse them.
    """
    name = os.environ.get("DATABASE_SCHEMA", "").strip() or DEFAULT_SCHEMA
    if not _SCHEMA_RE.match(name):
        raise ValueError(f"Invalid DATABASE_SCHEMA: {name!r}")
    return name


_pool: Any = None
_pool_url: Optional[str] = None
_pool_lock = threading.Lock()


def _get_pool(url: str) -> Any:
    global _pool, _pool_url
    with _pool_lock:
        if _pool is not None and _pool_url != url:
            _pool.close()
            _pool = None
        if _pool is None:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            _pool = ConnectionPool(
                url,
                min_size=1,
                max_size=10,
                kwargs={
                    "row_factory": dict_row,
                    # No server-side prepared statements: poolers such as
                    # Neon's PgBouncer endpoint may not support them.
                    "prepare_threshold": None,
                    # Text columns must always decode as str, whatever the
                    # database's own default encoding is.
                    "client_encoding": "UTF8",
                },
                # Serverless Postgres drops idle connections; verify on checkout.
                check=ConnectionPool.check_connection,
                open=True,
            )
            _pool_url = url
        return _pool


def describe_backend() -> str:
    """Human-readable backend for logs. Never includes credentials."""
    url = _postgres_url()
    if not url:
        return f"SQLite ({DB_PATH})"
    from urllib.parse import urlparse

    parsed = urlparse(url)
    database = parsed.path.lstrip("/") or "(default)"
    return (
        f"PostgreSQL (host={parsed.hostname}, database={database}, "
        f"schema={_schema_name()})"
    )


def close_pool() -> None:
    """Close the PostgreSQL pool, if one was opened."""
    global _pool, _pool_url
    with _pool_lock:
        if _pool is not None:
            _pool.close()
        _pool = None
        _pool_url = None


@lru_cache(maxsize=512)
def _pg_sql(sql: str) -> str:
    """Translate this module's SQLite-flavoured SQL for PostgreSQL."""
    return (
        sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        .replace("%", "%%")
        .replace("?", "%s")
    )


class _Conn:
    """Runs the same SQL on a sqlite3 or psycopg connection."""

    def __init__(self, raw: Any, postgres: bool) -> None:
        self.raw = raw
        self.postgres = postgres

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        if self.postgres:
            cursor = self.raw.cursor()
            cursor.execute(_pg_sql(sql), tuple(params))
            return cursor
        return self.raw.execute(sql, params)

    def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> Any:
        if self.postgres:
            cursor = self.raw.cursor()
            cursor.executemany(_pg_sql(sql), rows)
            return cursor
        return self.raw.executemany(sql, rows)

    def insert_returning_id(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Run an INSERT and return the new row's ``id`` on either backend."""
        if self.postgres:
            row = self.execute(sql + " RETURNING id", params).fetchone()
            return row["id"]
        new_id = self.execute(sql, params).lastrowid
        assert new_id is not None
        return new_id


def _ts(column: str) -> str:
    """SQL expression that orders an ISO-8601 text column chronologically."""
    return f"({column})::timestamptz" if _postgres_url() else f"datetime({column})"


@contextmanager
def _get_connection() -> Generator[_Conn, None, None]:
    url = _postgres_url()
    if url:
        # The pool commits on success and rolls back if the block raises.
        with _get_pool(url).connection() as raw:
            # SET LOCAL lasts for this transaction only, which is the one form
            # of search_path change that is safe behind a transaction pooler.
            raw.execute(f'SET LOCAL search_path TO "{_schema_name()}"')
            yield _Conn(raw, postgres=True)
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield _Conn(conn, postgres=False)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Columns added after the first release; CREATE TABLE IF NOT EXISTS does not
# touch tables that already exist, so older databases get them via ALTER TABLE.
_ADDED_COLUMNS = (
    ("events", "host_email", "TEXT"),
    ("events", "notify_host", "INTEGER NOT NULL DEFAULT 0"),
    ("dishes", "contributor_email", "TEXT"),
)


def _add_missing_columns(conn: _Conn) -> None:
    for table, column, definition in _ADDED_COLUMNS:
        if conn.postgres:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}"
            )
            continue
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    """Create database tables and seed defaults if they do not exist."""

    with _get_connection() as conn:
        if conn.postgres:
            # Several app instances may start at once; serialize schema setup.
            conn.execute("SELECT pg_advisory_xact_lock(727420)")
            conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{_schema_name()}"')
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                management_token TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                event_date TEXT,
                host_name TEXT NOT NULL DEFAULT 'The House',
                dish_types TEXT NOT NULL DEFAULT '[]',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                host_email TEXT,
                notify_host INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_events_slug ON events (slug)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_events_token ON events (management_token)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dishes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                contributor TEXT NOT NULL,
                dish_name TEXT NOT NULL,
                dish_type TEXT NOT NULL,
                notes TEXT,
                is_host_item INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                contributor_email TEXT,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_dishes_event_id
            ON dishes (event_id, is_host_item, created_at)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS config_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                value TEXT NOT NULL,
                position INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_config_entries_category
            ON config_entries (category)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                is_hidden INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tag_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
                UNIQUE (tag_id, keyword)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tag_keywords_tag_id
            ON tag_keywords (tag_id)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dish_tags (
                dish_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                FOREIGN KEY (dish_id) REFERENCES dishes(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
                UNIQUE (dish_id, tag_id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tags_category_position
            ON tags (category, position, id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_dish_tags_dish_id
            ON dish_tags (dish_id)
            """
        )
        _add_missing_columns(conn)
        _seed_or_migrate_config_entries(conn)
        _seed_or_migrate_tags(conn)
        _seed_or_migrate_keywords(conn)


# ── Event helpers ──────────────────────────────────────────────────────────────


def _row_to_event(row: Row) -> Event:
    event_date = None
    if row["event_date"]:
        try:
            event_date = date.fromisoformat(row["event_date"])
        except (ValueError, AttributeError):
            pass
    return Event(
        id=row["id"],
        slug=row["slug"],
        management_token=row["management_token"],
        name=row["name"],
        description=row["description"],
        event_date=event_date,
        host_name=row["host_name"],
        dish_types=json.loads(row["dish_types"]),
        is_active=bool(row["is_active"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        host_email=row["host_email"],
        notify_host=bool(row["notify_host"]),
    )


def _make_unique_slug(conn: _Conn, name: str, use_random: bool) -> str:
    for _ in range(20):
        if use_random:
            slug = _random_suffix(8)
        else:
            base = _slugify(name)
            suffix = _random_suffix(4)
            slug = f"{base}-{suffix}" if base else suffix
        if not conn.execute("SELECT id FROM events WHERE slug = ?", (slug,)).fetchone():
            return slug
    raise ValueError("Could not generate a unique event slug — please try again")


def _make_unique_token(conn: _Conn) -> str:
    for _ in range(20):
        token = _generate_management_token()
        if not conn.execute(
            "SELECT id FROM events WHERE management_token = ?", (token,)
        ).fetchone():
            return token
    raise ValueError("Could not generate a unique management token — please try again")


# ── Event CRUD ─────────────────────────────────────────────────────────────────


def create_event(
    name: str,
    description: Optional[str],
    event_date: Optional[str],
    host_name: str,
    dish_types: List[str],
    use_random_slug: bool = False,
    host_email: Optional[str] = None,
    notify_host: bool = False,
) -> Event:
    with _get_connection() as conn:
        slug = _make_unique_slug(conn, name, use_random_slug)
        token = _make_unique_token(conn)
        now = datetime.now(timezone.utc).isoformat()
        safe_host = host_name.strip() or "The House"
        event_id = conn.insert_returning_id(
            """
            INSERT INTO events (slug, management_token, name, description, event_date, host_name, dish_types, is_active, created_at, host_email, notify_host)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                slug,
                token,
                name.strip(),
                description or None,
                event_date or None,
                safe_host,
                json.dumps(dish_types),
                now,
                host_email,
                1 if (notify_host and host_email) else 0,
            ),
        )

    parsed_date = None
    if event_date:
        try:
            parsed_date = date.fromisoformat(event_date)
        except ValueError:
            pass

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
        created_at=datetime.fromisoformat(now),
        host_email=host_email,
        notify_host=bool(notify_host and host_email),
    )


def get_event_by_slug(slug: str) -> Optional[Event]:
    with _get_connection() as conn:
        row = conn.execute("SELECT * FROM events WHERE slug = ?", (slug,)).fetchone()
    return _row_to_event(row) if row else None


def get_event_by_management_token(token: str) -> Optional[Event]:
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE management_token = ?", (token,)
        ).fetchone()
    return _row_to_event(row) if row else None


def get_event_by_id(event_id: int) -> Optional[Event]:
    with _get_connection() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return _row_to_event(row) if row else None


def load_events() -> List[Event]:
    with _get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM events ORDER BY {_ts('created_at')} DESC, id DESC"
        ).fetchall()
    return [_row_to_event(r) for r in rows]


def count_events() -> int:
    with _get_connection() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]


def count_dishes() -> int:
    with _get_connection() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM dishes").fetchone()["n"]


def update_event(
    event_id: int,
    name: str,
    description: Optional[str],
    event_date: Optional[str],
    host_name: str,
    dish_types: List[str],
    is_active: bool,
) -> None:
    with _get_connection() as conn:
        conn.execute(
            """
            UPDATE events
            SET name = ?, description = ?, event_date = ?, host_name = ?, dish_types = ?, is_active = ?
            WHERE id = ?
            """,
            (
                name.strip(),
                description or None,
                event_date or None,
                host_name.strip() or "The House",
                json.dumps(dish_types),
                1 if is_active else 0,
                event_id,
            ),
        )


# How long after the event date, or after creation for undated events, stored
# email addresses are kept before being wiped.
EMAIL_GRACE_DAYS = 1
EMAIL_UNDATED_RETENTION_DAYS = 30


def purge_expired_emails(today: Optional[date] = None) -> int:
    """Null out stored email addresses for events that are over.

    An event is over once it is closed, its date passed (plus a short grace
    period), or, with no date, it is older than EMAIL_UNDATED_RETENTION_DAYS.
    Returns the number of addresses removed.
    """

    day = today or datetime.now(timezone.utc).date()
    # Dates are stored as ISO text, so plain string comparison is chronological
    # and works the same on SQLite and PostgreSQL.
    dated_cutoff = (day - timedelta(days=EMAIL_GRACE_DAYS)).isoformat()
    undated_cutoff = (day - timedelta(days=EMAIL_UNDATED_RETENTION_DAYS)).isoformat()
    over = """
        SELECT id FROM events WHERE
            is_active = 0
            OR (event_date IS NOT NULL AND event_date < ?)
            OR (event_date IS NULL AND substr(created_at, 1, 10) < ?)
    """
    params = (dated_cutoff, undated_cutoff)
    with _get_connection() as conn:
        dishes = conn.execute(
            f"UPDATE dishes SET contributor_email = NULL "
            f"WHERE contributor_email IS NOT NULL AND event_id IN ({over})",
            params,
        ).rowcount
        events = conn.execute(
            f"UPDATE events SET host_email = NULL, notify_host = 0 "
            f"WHERE host_email IS NOT NULL AND id IN ({over})",
            params,
        ).rowcount
    return dishes + events


def delete_event(event_id: int) -> None:
    with _get_connection() as conn:
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))


# ── Dish helpers ───────────────────────────────────────────────────────────────


def _row_to_entry(row: Row, tags: Optional[List[Tag]] = None) -> DishEntry:
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
        is_host_item=bool(row["is_host_item"]),
        created_at=row["created_at"],
        contributor_email=row["contributor_email"],
    )


def _category_sort_index(category: str) -> int:
    return _CATEGORY_ORDER_LOOKUP.get(category, len(TAG_CATEGORY_ORDER))


def _tag_sort_key(tag: Tag) -> Tuple[int, int, str]:
    return (_category_sort_index(tag.category), tag.position, tag.name.lower())


def _load_tags_for_dishes(
    conn: _Conn, dish_ids: Sequence[int]
) -> Dict[int, List[Tag]]:
    mapping: Dict[int, List[Tag]] = {}
    if not dish_ids:
        return mapping
    placeholders = ",".join("?" for _ in dish_ids)
    rows = conn.execute(
        f"""
        SELECT dt.dish_id, t.id AS tag_id, t.name, t.category, t.position
        FROM dish_tags AS dt
        JOIN tags AS t ON t.id = dt.tag_id
        WHERE dt.dish_id IN ({placeholders})
        ORDER BY t.category, t.position, LOWER(t.name)
        """,
        tuple(dish_ids),
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


def _replace_dish_tags(
    conn: _Conn, dish_id: int, tag_ids: Sequence[int]
) -> None:
    conn.execute("DELETE FROM dish_tags WHERE dish_id = ?", (dish_id,))
    deduped = list(dict.fromkeys(tag_ids))
    if deduped:
        conn.executemany(
            "INSERT INTO dish_tags (dish_id, tag_id) VALUES (?, ?)",
            [(dish_id, tag_id) for tag_id in deduped],
        )


# ── Dish CRUD ──────────────────────────────────────────────────────────────────


def load_dishes_for_event(event_id: int) -> List[DishEntry]:
    """All dishes for an event: host items first, then guest submissions by created_at ascending."""
    with _get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, event_id, contributor, dish_name, dish_type,
                   notes, is_host_item, created_at, contributor_email
            FROM dishes
            WHERE event_id = ?
            ORDER BY is_host_item DESC, {_ts("created_at")} ASC, id ASC
            """,
            (event_id,),
        ).fetchall()
        tag_map = _load_tags_for_dishes(conn, [row["id"] for row in rows])
    return [_row_to_entry(row, tag_map.get(row["id"])) for row in rows]


def load_all_dishes() -> List[DishEntry]:
    """All dishes across all events, newest first. For system-admin overview."""
    with _get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, event_id, contributor, dish_name, dish_type,
                   notes, is_host_item, created_at, contributor_email
            FROM dishes
            ORDER BY {_ts("created_at")} DESC, id DESC
            """
        ).fetchall()
        tag_map = _load_tags_for_dishes(conn, [row["id"] for row in rows])
    return [_row_to_entry(row, tag_map.get(row["id"])) for row in rows]


def get_dish(dish_id: int) -> Optional[DishEntry]:
    with _get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, event_id, contributor, dish_name, dish_type,
                   notes, is_host_item, created_at, contributor_email
            FROM dishes WHERE id = ?
            """,
            (dish_id,),
        ).fetchone()
        tag_map = _load_tags_for_dishes(conn, [dish_id]) if row else {}
    return _row_to_entry(row, tag_map.get(dish_id)) if row else None


def add_dish(entry: DishEntry) -> int:
    """Insert a dish and return its new id."""
    with _get_connection() as conn:
        dish_id = conn.insert_returning_id(
            """
            INSERT INTO dishes (event_id, contributor, dish_name, dish_type,
                                notes, is_host_item, created_at, contributor_email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.event_id,
                entry.contributor,
                entry.dish_name,
                entry.dish_type,
                entry.notes,
                1 if entry.is_host_item else 0,
                entry.created_at.isoformat(),
                entry.contributor_email,
            ),
        )
        _replace_dish_tags(conn, dish_id, entry.tag_ids)
    return dish_id


def update_dish(dish_id: int, entry: DishEntry) -> None:
    with _get_connection() as conn:
        conn.execute(
            """
            UPDATE dishes
            SET contributor = ?, dish_name = ?, dish_type = ?, notes = ?, created_at = ?
            WHERE id = ?
            """,
            (
                entry.contributor,
                entry.dish_name,
                entry.dish_type,
                entry.notes,
                entry.created_at.isoformat(),
                dish_id,
            ),
        )
        _replace_dish_tags(conn, dish_id, entry.tag_ids)


def delete_dish(dish_id: int) -> None:
    with _get_connection() as conn:
        conn.execute("DELETE FROM dishes WHERE id = ?", (dish_id,))


# ── Tag CRUD ───────────────────────────────────────────────────────────────────


def _load_keywords_for_tags(
    conn: _Conn, tag_ids: Sequence[int]
) -> Dict[int, List[str]]:
    """Return a mapping of tag_id → list of keywords."""
    if not tag_ids:
        return {}
    placeholders = ",".join("?" for _ in tag_ids)
    rows = conn.execute(
        f"SELECT tag_id, keyword FROM tag_keywords WHERE tag_id IN ({placeholders}) ORDER BY tag_id, id",
        tuple(tag_ids),
    ).fetchall()
    mapping: Dict[int, List[str]] = {}
    for row in rows:
        mapping.setdefault(row["tag_id"], []).append(row["keyword"])
    return mapping


def _set_tag_keywords_conn(
    conn: _Conn, tag_id: int, keywords: List[str]
) -> None:
    """Replace all keywords for a tag within an existing connection/transaction."""
    cleaned = [kw.strip().lower() for kw in keywords if kw.strip()]
    deduped = list(dict.fromkeys(cleaned))
    conn.execute("DELETE FROM tag_keywords WHERE tag_id = ?", (tag_id,))
    if deduped:
        conn.executemany(
            "INSERT INTO tag_keywords (tag_id, keyword) VALUES (?, ?)",
            [(tag_id, kw) for kw in deduped],
        )


def load_tags() -> List[Tag]:
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
            is_hidden=bool(row["is_hidden"]),
            keywords=kw_map.get(row["id"], []),
        )
        for row in rows
    ]
    tags.sort(key=_tag_sort_key)
    return tags


def get_tag_counts() -> Dict[str, int]:
    """Return total, visible, and hidden tag counts for summary display."""
    with _get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM tags").fetchone()["n"]
        hidden = conn.execute(
            "SELECT COUNT(*) AS n FROM tags WHERE is_hidden = 1"
        ).fetchone()["n"]
    return {"total": total, "visible": total - hidden, "hidden": hidden}


def load_tag_groups() -> List[Tuple[str, List[Tag]]]:
    tags = load_tags()
    grouped: Dict[str, List[Tag]] = {}
    for tag in tags:
        grouped.setdefault(tag.category, []).append(tag)
    ordered: List[Tuple[str, List[Tag]]] = []
    for category in TAG_CATEGORY_ORDER:
        bucket = grouped.pop(category, None)
        if bucket:
            ordered.append((category, bucket))
    for category in sorted(grouped.keys()):
        ordered.append((category, grouped[category]))
    return ordered


def get_tags_by_ids(tag_ids: Sequence[int]) -> List[Tag]:
    if not tag_ids:
        return []
    placeholders = ",".join("?" for _ in tag_ids)
    with _get_connection() as conn:
        rows = conn.execute(
            f"SELECT id, name, category, position, is_hidden FROM tags WHERE id IN ({placeholders})",
            tuple(tag_ids),
        ).fetchall()
        kw_map = _load_keywords_for_tags(conn, [row["id"] for row in rows])
    tags = [
        Tag(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            position=row["position"],
            is_hidden=bool(row["is_hidden"]),
            keywords=kw_map.get(row["id"], []),
        )
        for row in rows
    ]
    tags.sort(key=_tag_sort_key)
    return tags


def get_tag_categories() -> List[str]:
    """Return ordered categories: predefined first, then any extras found in the DB."""
    with _get_connection() as conn:
        rows = conn.execute("SELECT DISTINCT category FROM tags").fetchall()
    db_cats = {row["category"] for row in rows}
    result = list(TAG_CATEGORY_ORDER)
    for cat in sorted(db_cats):
        if cat not in result:
            result.append(cat)
    return result


def set_tag_keywords(tag_id: int, keywords: List[str]) -> None:
    """Public helper: replace all keywords for a tag."""
    with _get_connection() as conn:
        _set_tag_keywords_conn(conn, tag_id, keywords)


def toggle_tag_visibility(tag_id: int) -> bool:
    """Flip is_hidden for a tag. Returns the new is_hidden value."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT is_hidden FROM tags WHERE id = ?", (tag_id,)
        ).fetchone()
        if not row:
            raise ValueError("Tag not found")
        new_val = 0 if row["is_hidden"] else 1
        conn.execute("UPDATE tags SET is_hidden = ? WHERE id = ?", (new_val, tag_id))
    return bool(new_val)


def update_tag(
    tag_id: int,
    name: str,
    category: str,
    keywords: Optional[List[str]] = None,
    is_hidden: Optional[bool] = None,
) -> None:
    cleaned = name.strip()
    cat = category.strip()
    if not cleaned:
        raise ValueError("Tag name cannot be empty")
    if not cat:
        raise ValueError("Category cannot be empty")
    with _get_connection() as conn:
        if conn.execute(
            "SELECT id FROM tags WHERE LOWER(name) = LOWER(?) AND id != ?",
            (cleaned, tag_id),
        ).fetchone():
            raise ValueError("A tag with that name already exists")
        if is_hidden is None:
            conn.execute(
                "UPDATE tags SET name = ?, category = ? WHERE id = ?",
                (cleaned, cat, tag_id),
            )
        else:
            conn.execute(
                "UPDATE tags SET name = ?, category = ?, is_hidden = ? WHERE id = ?",
                (cleaned, cat, 1 if is_hidden else 0, tag_id),
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
    keywords: Optional[List[str]] = None,
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
            "SELECT id FROM tags WHERE LOWER(name) = LOWER(?)", (cleaned_name,)
        ).fetchone():
            raise ValueError("That tag already exists")
        row = conn.execute(
            "SELECT COALESCE(MAX(position), -1) AS max_position FROM tags WHERE category = ?",
            (cat,),
        ).fetchone()
        next_position = row["max_position"] + 1
        tag_id = conn.insert_returning_id(
            "INSERT INTO tags (name, category, position, is_hidden) VALUES (?, ?, ?, ?)",
            (cleaned_name, cat, next_position, 1 if is_hidden else 0),
        )
        kw_list: List[str] = []
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
        conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))


# ── Config persistence ─────────────────────────────────────────────────────────


def load_app_config_from_db() -> Optional[Tuple[AppConfig, datetime]]:
    with _get_connection() as conn:
        dish_rows = conn.execute(
            "SELECT value, position, updated_at FROM config_entries WHERE category = ? ORDER BY position ASC, id ASC",
            (CONFIG_CATEGORY_DISH_TYPES,),
        ).fetchall()
        admin_rows = conn.execute(
            "SELECT value, position, updated_at FROM config_entries WHERE category = ? ORDER BY position ASC, id ASC",
            (CONFIG_CATEGORY_ADMIN_NETWORKS,),
        ).fetchall()
        web_admin_rows = conn.execute(
            "SELECT value, updated_at FROM config_entries WHERE category = ?",
            (CONFIG_CATEGORY_WEB_ADMIN,),
        ).fetchall()
        metrics_network_rows = conn.execute(
            "SELECT value, position, updated_at FROM config_entries WHERE category = ? ORDER BY position ASC, id ASC",
            (CONFIG_CATEGORY_METRICS_NETWORKS,),
        ).fetchall()
        metrics_enabled_rows = conn.execute(
            "SELECT value, updated_at FROM config_entries WHERE category = ?",
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
    timestamp = datetime.now(timezone.utc).isoformat()
    with _get_connection() as conn:
        conn.execute(
            "DELETE FROM config_entries WHERE category IN (?, ?, ?, ?, ?)",
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
    conn: _Conn, category: str, values: List[str], timestamp: str
) -> None:
    if not values:
        return
    conn.executemany(
        "INSERT INTO config_entries (category, value, position, updated_at) VALUES (?, ?, ?, ?)",
        [(category, value, idx, timestamp) for idx, value in enumerate(values)],
    )


def _latest_updated_at(rows: list) -> datetime:
    if not rows:
        return datetime.fromtimestamp(0, tz=timezone.utc)

    def _parse(ts: str) -> datetime:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    return max(_parse(row["updated_at"]) for row in rows)


# ── Seeding ────────────────────────────────────────────────────────────────────


def _seed_or_migrate_config_entries(conn: _Conn) -> None:
    if conn.execute("SELECT COUNT(*) as count FROM config_entries").fetchone()["count"]:
        return
    timestamp = datetime.now(timezone.utc).isoformat()
    defaults = AppConfig()
    _bulk_insert_config_entries(
        conn, CONFIG_CATEGORY_DISH_TYPES, defaults.dish_types, timestamp
    )
    _bulk_insert_config_entries(
        conn, CONFIG_CATEGORY_ADMIN_NETWORKS, defaults.admin_networks, timestamp
    )
    _bulk_insert_config_entries(conn, CONFIG_CATEGORY_WEB_ADMIN, ["false"], timestamp)


def _seed_or_migrate_tags(conn: _Conn) -> None:
    if conn.execute("SELECT COUNT(*) AS count FROM tags").fetchone()["count"] == 0:
        _insert_default_tags(conn)
    else:
        _add_missing_default_tags(conn)


def _add_missing_default_tags(conn: _Conn) -> None:
    """Add any new default tags that are absent from an existing database."""
    all_defaults: List[Tuple[str, str, bool]] = []
    for category in TAG_CATEGORY_ORDER:
        for name in DEFAULT_TAG_GROUPS.get(category, []):
            all_defaults.append((name, category, False))
        for name in DEFAULT_HIDDEN_TAG_GROUPS.get(category, []):
            all_defaults.append((name, category, True))
    for name, category, is_hidden in all_defaults:
        if conn.execute(
            "SELECT id FROM tags WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone():
            continue
        row = conn.execute(
            "SELECT COALESCE(MAX(position), -1) AS mp FROM tags WHERE category = ?",
            (category,),
        ).fetchone()
        tag_id = conn.insert_returning_id(
            "INSERT INTO tags (name, category, position, is_hidden) VALUES (?, ?, ?, ?)",
            (name, category, row["mp"] + 1, 1 if is_hidden else 0),
        )
        kws = DEFAULT_TAG_KEYWORDS.get(name, [])
        if kws:
            _set_tag_keywords_conn(conn, tag_id, kws)


def _insert_default_tags(conn: _Conn) -> None:
    """Seed all default tags (visible + hidden) with their keywords."""
    for category in TAG_CATEGORY_ORDER:
        # Visible tags
        for position, name in enumerate(DEFAULT_TAG_GROUPS.get(category, [])):
            tag_id = conn.insert_returning_id(
                "INSERT INTO tags (name, category, position, is_hidden) VALUES (?, ?, ?, 0)",
                (name, category, position),
            )
            kws = DEFAULT_TAG_KEYWORDS.get(name, [])
            if kws:
                _set_tag_keywords_conn(conn, tag_id, kws)
        # Hidden tags
        for name in DEFAULT_HIDDEN_TAG_GROUPS.get(category, []):
            row = conn.execute(
                "SELECT COALESCE(MAX(position), -1) AS mp FROM tags WHERE category = ?",
                (category,),
            ).fetchone()
            tag_id = conn.insert_returning_id(
                "INSERT INTO tags (name, category, position, is_hidden) VALUES (?, ?, ?, 1)",
                (name, category, row["mp"] + 1),
            )
            kws = DEFAULT_TAG_KEYWORDS.get(name, [])
            if kws:
                _set_tag_keywords_conn(conn, tag_id, kws)


def _seed_or_migrate_keywords(conn: _Conn) -> None:
    """Seed auto-detect keywords for existing tags that have none yet."""
    count = conn.execute("SELECT COUNT(*) AS count FROM tag_keywords").fetchone()[
        "count"
    ]
    if count > 0:
        return
    tag_rows = conn.execute("SELECT id, name FROM tags").fetchall()
    for row in tag_rows:
        kws = DEFAULT_TAG_KEYWORDS.get(row["name"], [])
        if kws:
            _set_tag_keywords_conn(conn, row["id"], kws)
