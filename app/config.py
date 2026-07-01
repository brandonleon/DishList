"""Application configuration helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = DATA_DIR / "config.json"


class AppConfig(BaseModel):
    """Serializable config that the admin screen can modify."""

    dish_types: List[str] = Field(
        default_factory=lambda: [
            "Main Dish",
            "Side Dish",
            "Dessert",
            "Beverage",
        ]
    )
    admin_networks: List[str] = Field(default_factory=lambda: ["127.0.0.1/32"])
    # False by default — use `dishlist admin web enable` to turn on.
    web_admin_enabled: bool = False


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> AppConfig:
    """Load config from SQLite. Migrates from config.json on first run if needed."""

    _ensure_data_dir()
    db_entry = _load_config_from_db()
    if db_entry:
        return db_entry[0]

    # One-time migration: seed DB from config.json if it exists
    file_config = _migrate_from_file()
    if file_config:
        _save_config_to_db(file_config)
        return file_config

    config = AppConfig()
    _save_config_to_db(config)
    return config


def save_config(config: AppConfig) -> None:
    """Persist config to SQLite."""

    _ensure_data_dir()
    _save_config_to_db(config)


def _migrate_from_file() -> Optional[AppConfig]:
    """Read config.json once to seed the DB. Only called when DB has no config."""
    if not CONFIG_PATH.exists():
        return None

    with CONFIG_PATH.open("r", encoding="utf-8") as fp:
        data = json.load(fp)

    # Migration: existing config.json files without this key and with custom
    # networks are treated as enabled to preserve prior behaviour.
    if "web_admin_enabled" not in data and data.get("admin_networks"):
        data["web_admin_enabled"] = True

    return AppConfig(**data)


def _load_config_from_db() -> Optional[tuple]:
    from .storage import load_app_config_from_db

    return load_app_config_from_db()


def _save_config_to_db(config: AppConfig) -> None:
    from .storage import save_app_config_to_db

    save_app_config_to_db(config)
