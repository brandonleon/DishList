"""Application configuration helpers."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field


class DatabaseNotConfiguredError(RuntimeError):
    """``DATABASE_URL`` is not set."""


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL must be set to a PostgreSQL connection URL, "
            "e.g. postgresql://dishlist:dishlist@localhost:5432/dishlist"
        )
    return url


class AppConfig(BaseModel):
    """Serializable config that the admin screen can modify."""

    dish_types: list[str] = Field(
        default_factory=lambda: [
            "Main Dish",
            "Side Dish",
            "Dessert",
            "Beverage",
        ]
    )
    admin_networks: list[str] = Field(default_factory=lambda: ["127.0.0.1/32"])
    # False by default — use `dishlist admin web enable` to turn on.
    web_admin_enabled: bool = False
    metrics_networks: list[str] = Field(default_factory=lambda: ["127.0.0.1/32"])
    # False by default — use `dishlist admin metrics enable` to turn on.
    metrics_enabled: bool = False


def load_config() -> AppConfig:
    """Load config from the database, seeding the defaults if none is stored."""

    db_entry = _load_config_from_db()
    if db_entry:
        return db_entry[0]

    config = AppConfig()
    _save_config_to_db(config)
    return config


def save_config(config: AppConfig) -> None:
    """Persist config to the database."""

    _save_config_to_db(config)


def _load_config_from_db() -> tuple | None:
    # Imported lazily: storage imports this module.
    from .storage import load_app_config_from_db  # noqa: PLC0415

    return load_app_config_from_db()


def _save_config_to_db(config: AppConfig) -> None:
    # Imported lazily: storage imports this module.
    from .storage import save_app_config_to_db  # noqa: PLC0415

    save_app_config_to_db(config)
