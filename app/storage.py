"""SQLite-backed persistence for submissions."""

from __future__ import annotations

import json
import sqlite3
from typing import List

from .config import DATA_DIR
from .models import DishEntry

DB_PATH = DATA_DIR / "dishlist.db"


def _get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the dishes table if it does not exist."""

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


def load_dishes() -> List[DishEntry]:
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT contributor, dish_name, dish_type, allergens, dietary_flags, notes, created_at
            FROM dishes
            ORDER BY datetime(created_at) DESC, id DESC
            """
        ).fetchall()

    dishes: List[DishEntry] = []
    for row in rows:
        dishes.append(
            DishEntry(
                contributor=row["contributor"],
                dish_name=row["dish_name"],
                dish_type=row["dish_type"],
                allergens=json.loads(row["allergens"]),
                dietary_flags=json.loads(row["dietary_flags"]),
                notes=row["notes"],
                created_at=row["created_at"],
            )
        )
    return dishes


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
