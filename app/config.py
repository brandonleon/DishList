"""Application configuration helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

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
    """Load config from disk, falling back to defaults."""

    _ensure_data_dir()
    if not CONFIG_PATH.exists():
        config = AppConfig()
        save_config(config)
        return config

    with CONFIG_PATH.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    return AppConfig(**data)


def save_config(config: AppConfig) -> None:
    """Persist config to disk."""

    _ensure_data_dir()
    with CONFIG_PATH.open("w", encoding="utf-8") as fp:
        json.dump(config.model_dump(), fp, indent=2)
