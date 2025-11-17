"""Application configuration helpers."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

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


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> AppConfig:
    """Load config preferring SQLite but staying in sync with config.json."""

    _ensure_data_dir()
    db_entry = _load_config_from_db()
    db_config: Optional[AppConfig]
    db_updated_at: Optional[datetime]
    if db_entry:
        db_config, db_updated_at = db_entry
    else:
        db_config, db_updated_at = None, None

    file_config = _load_config_from_file()
    file_updated_at = _get_file_updated_at()

    if file_config and db_config:
        file_newer = _is_file_newer(file_updated_at, db_updated_at)
        if file_newer:
            if file_config != db_config:
                _save_config_to_db(file_config)
            return file_config

        if file_config != db_config:
            _write_config_to_file(db_config)
        return db_config

    if file_config:
        _save_config_to_db(file_config)
        return file_config

    if db_config:
        _write_config_to_file(db_config)
        return db_config

    config = AppConfig()
    _write_config_to_file(config)
    _save_config_to_db(config)
    return config


def save_config(config: AppConfig) -> None:
    """Persist config to disk and SQLite."""

    _ensure_data_dir()
    _write_config_to_file(config)
    _save_config_to_db(config)


def _load_config_from_file() -> Optional[AppConfig]:
    if not CONFIG_PATH.exists():
        return None

    with CONFIG_PATH.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    return AppConfig(**data)


def _write_config_to_file(config: AppConfig) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as fp:
        json.dump(config.model_dump(), fp, indent=2)


def _get_file_updated_at() -> Optional[datetime]:
    if not CONFIG_PATH.exists():
        return None
    return datetime.fromtimestamp(CONFIG_PATH.stat().st_mtime)


def _load_config_from_db() -> Optional[Tuple[AppConfig, datetime]]:
    from .storage import load_app_config_from_db

    return load_app_config_from_db()


def _save_config_to_db(config: AppConfig) -> None:
    from .storage import save_app_config_to_db

    save_app_config_to_db(config)


def _is_file_newer(file_updated_at: Optional[datetime], db_updated_at: Optional[datetime]) -> bool:
    if file_updated_at and db_updated_at:
        return file_updated_at > db_updated_at
    if file_updated_at and not db_updated_at:
        return True
    return False
