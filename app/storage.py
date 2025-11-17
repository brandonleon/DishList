"""SQLite-backed persistence for submissions and config."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple

from .config import AppConfig, DATA_DIR
from .models import DishEntry

DB_PATH = DATA_DIR / "dishlist.db"
CONFIG_CATEGORY_DISH_TYPES = "dish_type"
CONFIG_CATEGORY_ADMIN_NETWORKS = "admin_network"


def _get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
        _seed_or_migrate_config_entries(conn)


def _row_to_entry(row: sqlite3.Row) -> DishEntry:
    return DishEntry(
        id=row["id"],
        contributor=row["contributor"],
        dish_name=row["dish_name"],
        dish_type=row["dish_type"],
        allergens=json.loads(row["allergens"]),
        dietary_flags=json.loads(row["dietary_flags"]),
        notes=row["notes"],
        created_at=row["created_at"],
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

    return [_row_to_entry(row) for row in rows]


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
    return _row_to_entry(row) if row else None


def add_dish(entry: DishEntry) -> None:
    with _get_connection() as conn:
        conn.execute(
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


def delete_dish(dish_id: int) -> None:
    with _get_connection() as conn:
        conn.execute("DELETE FROM dishes WHERE id = ?", (dish_id,))


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
