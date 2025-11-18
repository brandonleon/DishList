"""SQLite-backed persistence for submissions and config."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from .config import AppConfig, DATA_DIR
from .models import DishEntry, Tag

DB_PATH = DATA_DIR / "dishlist.db"
CONFIG_CATEGORY_DISH_TYPES = "dish_type"
CONFIG_CATEGORY_ADMIN_NETWORKS = "admin_network"
TAG_CATEGORY_ORDER = [
    "Dietary patterns",
    "Ingredient avoidances",
    "Preparation and cross-contact",
    "Additives and content",
    "Spice and suitability",
    "Serving logistics",
]
DEFAULT_TAG_GROUPS = {
    "Dietary patterns": [
        "Vegan",
        "Vegetarian",
        "Vegetarian but not vegan (contains eggs/honey)",
        "Pescatarian",
        "Kosher",
        "Halal",
        "Keto",
        "Paleo",
        "Whole30",
        "Low-FODMAP",
        "Low-carb",
        "Low-sodium",
        "Low-sugar/Diabetic-friendly",
    ],
    "Ingredient avoidances": [
        "Gluten-Free",
        "Dairy-Free",
        "Lactose-free (distinct from dairy-free)",
        "Peanut-free",
        "Tree-nut-free",
        "Egg-free",
        "Soy-free",
        "Sesame-free",
        "Shellfish-free",
        "Fish-free",
        "Corn-free",
        "Nightshade-free",
        "Onion-free",
        "Garlic-free",
    ],
    "Preparation and cross-contact": [
        "Prepared in GF kitchen",
        "Shared fryer/oil",
        "Separate utensils used",
        "May contain trace allergens",
        "Contains pork/beef",
        "Gelatin present",
    ],
    "Additives and content": [
        "Contains alcohol",
        "Caffeine present (e.g., tiramisu/coffee desserts)",
        "Artificial sweeteners",
        "MSG added",
    ],
    "Spice and suitability": [
        "Mild heat",
        "Medium heat",
        "Spicy heat",
        "Kid-friendly",
    ],
    "Serving logistics": [
        "Requires reheating",
        "Keep chilled",
        "Contains raw/undercooked ingredients (e.g., cured fish/meat)",
        "Shelf-stable",
    ],
}
_CATEGORY_ORDER_LOOKUP = {category: idx for idx, category in enumerate(TAG_CATEGORY_ORDER)}
CATEGORY_NORMALIZATION = {
    "Vegetarian but not vegan (contains eggs/honey)": "Dietary patterns",
    "Lactose-free (distinct from dairy-free)": "Ingredient avoidances",
}


def _get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create the database tables and seed defaults if they do not exist."""

    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dishes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contributor TEXT NOT NULL,
                dish_name TEXT NOT NULL,
                dish_type TEXT NOT NULL,
                allergens TEXT NOT NULL,
                dietary_flags TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL
            )
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
                position INTEGER NOT NULL DEFAULT 0
            )
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
        _seed_or_migrate_config_entries(conn)
        _seed_or_migrate_tags(conn)


def _row_to_entry(row: sqlite3.Row, tags: Optional[List[Tag]] = None) -> DishEntry:
    tag_list = tags or []
    dietary_flags = [tag.name for tag in tag_list]
    if not dietary_flags:
        dietary_flags = json.loads(row["dietary_flags"])
    return DishEntry(
        id=row["id"],
        contributor=row["contributor"],
        dish_name=row["dish_name"],
        dish_type=row["dish_type"],
        allergens=json.loads(row["allergens"]),
        dietary_flags=dietary_flags,
        tag_ids=[tag.id for tag in tag_list],
        tags=tag_list,
        notes=row["notes"],
        created_at=row["created_at"],
    )


def _category_sort_index(category: str) -> int:
    return _CATEGORY_ORDER_LOOKUP.get(category, len(TAG_CATEGORY_ORDER))


def _tag_sort_key(tag: Tag) -> Tuple[int, int, str]:
    return (_category_sort_index(tag.category), tag.position, tag.name.lower())


def _load_tags_for_dishes(conn: sqlite3.Connection, dish_ids: Sequence[int]) -> Dict[int, List[Tag]]:
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


def _replace_dish_tags(conn: sqlite3.Connection, dish_id: int, tag_ids: Sequence[int]) -> None:
    conn.execute("DELETE FROM dish_tags WHERE dish_id = ?", (dish_id,))
    deduped = []
    seen = set()
    for tag_id in tag_ids:
        if tag_id in seen:
            continue
        seen.add(tag_id)
        deduped.append(tag_id)
    if not deduped:
        return
    conn.executemany(
        "INSERT INTO dish_tags (dish_id, tag_id) VALUES (?, ?)",
        [(dish_id, tag_id) for tag_id in deduped],
    )


def load_dishes() -> List[DishEntry]:
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, contributor, dish_name, dish_type, allergens, dietary_flags, notes, created_at
            FROM dishes
            ORDER BY datetime(created_at) DESC, id DESC
            """
        ).fetchall()
        tag_map = _load_tags_for_dishes(conn, [row["id"] for row in rows])

    return [_row_to_entry(row, tag_map.get(row["id"])) for row in rows]


def get_dish(dish_id: int) -> Optional[DishEntry]:
    with _get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, contributor, dish_name, dish_type, allergens, dietary_flags, notes, created_at
            FROM dishes
            WHERE id = ?
            """,
            (dish_id,),
        ).fetchone()
        tag_map = _load_tags_for_dishes(conn, [dish_id]) if row else {}
    return _row_to_entry(row, tag_map.get(dish_id)) if row else None


def load_tags() -> List[Tag]:
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, category, position
            FROM tags
            """
        ).fetchall()
    tags = [
        Tag(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            position=row["position"],
        )
        for row in rows
    ]
    tags.sort(key=_tag_sort_key)
    return tags


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
            f"""
            SELECT id, name, category, position
            FROM tags
            WHERE id IN ({placeholders})
            """,
            tuple(tag_ids),
        ).fetchall()
    tags = [
        Tag(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            position=row["position"],
        )
        for row in rows
    ]
    tags.sort(key=_tag_sort_key)
    return tags


def get_tag_categories() -> List[str]:
    return list(TAG_CATEGORY_ORDER)


def create_tag(name: str, category: str) -> Tag:
    cleaned_name = name.strip()
    if not cleaned_name:
        raise ValueError("Tag name cannot be empty")
    normalized_category = category.strip()
    if normalized_category not in TAG_CATEGORY_ORDER:
        raise ValueError("Unknown category")

    with _get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id FROM tags
            WHERE LOWER(name) = LOWER(?)
            """,
            (cleaned_name,),
        ).fetchone()
        if existing:
            raise ValueError("That tag already exists")
        row = conn.execute(
            """
            SELECT COALESCE(MAX(position), -1) AS max_position
            FROM tags
            WHERE category = ?
            """,
            (normalized_category,),
        ).fetchone()
        next_position = row["max_position"] + 1
        cursor = conn.execute(
            """
            INSERT INTO tags (name, category, position)
            VALUES (?, ?, ?)
            """,
            (cleaned_name, normalized_category, next_position),
        )
        tag_id = cursor.lastrowid

    return Tag(id=tag_id, name=cleaned_name, category=normalized_category, position=next_position)


def delete_tag(tag_id: int) -> None:
    with _get_connection() as conn:
        conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))


def add_dish(entry: DishEntry) -> None:
    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO dishes (
                contributor,
                dish_name,
                dish_type,
                allergens,
                dietary_flags,
                notes,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.contributor,
                entry.dish_name,
                entry.dish_type,
                json.dumps(entry.allergens),
                json.dumps(entry.dietary_flags),
                entry.notes,
                entry.created_at.isoformat(),
            ),
        )
        dish_id = cursor.lastrowid
        _replace_dish_tags(conn, dish_id, entry.tag_ids)


def update_dish(dish_id: int, entry: DishEntry) -> None:
    with _get_connection() as conn:
        conn.execute(
            """
            UPDATE dishes
            SET contributor = ?,
                dish_name = ?,
                dish_type = ?,
                allergens = ?,
                dietary_flags = ?,
                notes = ?,
                created_at = ?
            WHERE id = ?
            """,
            (
                entry.contributor,
                entry.dish_name,
                entry.dish_type,
                json.dumps(entry.allergens),
                json.dumps(entry.dietary_flags),
                entry.notes,
                entry.created_at.isoformat(),
                dish_id,
            ),
        )
        _replace_dish_tags(conn, dish_id, entry.tag_ids)


def delete_dish(dish_id: int) -> None:
    with _get_connection() as conn:
        conn.execute("DELETE FROM dishes WHERE id = ?", (dish_id,))
        conn.execute("DELETE FROM dish_tags WHERE dish_id = ?", (dish_id,))


def load_app_config_from_db() -> Optional[Tuple[AppConfig, datetime]]:
    """Fetch the admin/dish-type config stored in SQLite."""

    with _get_connection() as conn:
        dish_rows = conn.execute(
            """
            SELECT value, position, updated_at
            FROM config_entries
            WHERE category = ?
            ORDER BY position ASC, id ASC
            """,
            (CONFIG_CATEGORY_DISH_TYPES,),
        ).fetchall()
        admin_rows = conn.execute(
            """
            SELECT value, position, updated_at
            FROM config_entries
            WHERE category = ?
            ORDER BY position ASC, id ASC
            """,
            (CONFIG_CATEGORY_ADMIN_NETWORKS,),
        ).fetchall()

    if not dish_rows and not admin_rows:
        return None

    dish_types = [row["value"] for row in dish_rows]
    admin_networks = [row["value"] for row in admin_rows]
    latest_updated = _latest_updated_at(dish_rows + admin_rows)

    return AppConfig(dish_types=dish_types, admin_networks=admin_networks), latest_updated


def save_app_config_to_db(config: AppConfig) -> None:
    """Persist admin/dish-type config to SQLite."""

    timestamp = datetime.utcnow().isoformat()
    with _get_connection() as conn:
        conn.execute(
            """
            DELETE FROM config_entries WHERE category IN (?, ?)
            """,
            (CONFIG_CATEGORY_DISH_TYPES, CONFIG_CATEGORY_ADMIN_NETWORKS),
        )
        _bulk_insert_config_entries(
            conn,
            CONFIG_CATEGORY_DISH_TYPES,
            config.dish_types,
            timestamp,
        )
        _bulk_insert_config_entries(
            conn,
            CONFIG_CATEGORY_ADMIN_NETWORKS,
            config.admin_networks,
            timestamp,
        )


def _bulk_insert_config_entries(conn: sqlite3.Connection, category: str, values: List[str], timestamp: str) -> None:
    if not values:
        return

    conn.executemany(
        """
        INSERT INTO config_entries (category, value, position, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        [
            (
                category,
                value,
                idx,
                timestamp,
            )
            for idx, value in enumerate(values)
        ],
    )


def _latest_updated_at(rows: List[sqlite3.Row]) -> datetime:
    if not rows:
        return datetime.utcfromtimestamp(0)
    latest = max(datetime.fromisoformat(row["updated_at"]) for row in rows)
    return latest


def _seed_or_migrate_config_entries(conn: sqlite3.Connection) -> None:
    """Backfill config entries from legacy table or defaults."""

    row_count = conn.execute("SELECT COUNT(*) as count FROM config_entries").fetchone()["count"]
    if row_count:
        return

    legacy_table_exists = conn.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'app_config'
        """
    ).fetchone()

    timestamp = datetime.utcnow().isoformat()
    if legacy_table_exists:
        legacy_row = conn.execute(
            """
            SELECT dish_types, admin_networks FROM app_config WHERE id = 1
            """
        ).fetchone()
        if legacy_row:
            dish_types = json.loads(legacy_row["dish_types"])
            admin_networks = json.loads(legacy_row["admin_networks"])
            _bulk_insert_config_entries(conn, CONFIG_CATEGORY_DISH_TYPES, dish_types, timestamp)
            _bulk_insert_config_entries(conn, CONFIG_CATEGORY_ADMIN_NETWORKS, admin_networks, timestamp)
            return

    defaults = AppConfig()
    _bulk_insert_config_entries(conn, CONFIG_CATEGORY_DISH_TYPES, defaults.dish_types, timestamp)
    _bulk_insert_config_entries(conn, CONFIG_CATEGORY_ADMIN_NETWORKS, defaults.admin_networks, timestamp)


def _seed_or_migrate_tags(conn: sqlite3.Connection) -> None:
    tag_count = conn.execute("SELECT COUNT(*) AS count FROM tags").fetchone()["count"]
    if tag_count == 0:
        _insert_default_tags(conn)
    _backfill_dish_tags(conn)
    _normalize_existing_tag_categories(conn)


def _insert_default_tags(conn: sqlite3.Connection) -> None:
    for category in TAG_CATEGORY_ORDER:
        default_tags = DEFAULT_TAG_GROUPS.get(category, [])
        for position, name in enumerate(default_tags):
            conn.execute(
                """
                INSERT INTO tags (name, category, position)
                VALUES (?, ?, ?)
                """,
                (name, category, position),
            )


def _backfill_dish_tags(conn: sqlite3.Connection) -> None:
    dish_rows = conn.execute("SELECT id, dietary_flags FROM dishes").fetchall()
    if not dish_rows:
        return
    tag_rows = conn.execute("SELECT id, name FROM tags").fetchall()
    lookup = {row["name"].strip().lower(): row["id"] for row in tag_rows}
    for dish in dish_rows:
        has_tags = conn.execute(
            "SELECT 1 FROM dish_tags WHERE dish_id = ? LIMIT 1",
            (dish["id"],),
        ).fetchone()
        if has_tags:
            continue
        try:
            flags = json.loads(dish["dietary_flags"])
        except json.JSONDecodeError:
            continue
        tag_ids = []
        for flag in flags:
            tag_id = lookup.get(flag.strip().lower())
            if tag_id:
                tag_ids.append(tag_id)
        if tag_ids:
            _replace_dish_tags(conn, dish["id"], tag_ids)


def _normalize_existing_tag_categories(conn: sqlite3.Connection) -> None:
    for name, desired_category in CATEGORY_NORMALIZATION.items():
        row = conn.execute(
            """
            SELECT id, category FROM tags WHERE name = ?
            """,
            (name,),
        ).fetchone()
        if not row or row["category"] == desired_category:
            continue
        pos_row = conn.execute(
            """
            SELECT COALESCE(MAX(position), -1) AS max_position
            FROM tags
            WHERE category = ?
            """,
            (desired_category,),
        ).fetchone()
        next_position = pos_row["max_position"] + 1
        conn.execute(
            """
            UPDATE tags
            SET category = ?, position = ?
            WHERE id = ?
            """,
            (desired_category, next_position, row["id"]),
        )
