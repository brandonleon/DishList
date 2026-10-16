"""Unit tests for app/config.py — load/save against the database."""

import pytest

import app.storage as storage_mod
from app.config import (
    AppConfig,
    DatabaseNotConfiguredError,
    database_url,
    load_config,
    save_config,
)


@pytest.fixture
def empty_db_config(isolated_db):
    """Clear the config entries seeded by the baseline migration."""
    with storage_mod._get_connection() as conn:
        conn.execute("DELETE FROM config_entries")
    return isolated_db


class TestSaveConfig:
    def test_writes_to_db(self):
        cfg = AppConfig(dish_types=["Dessert"])
        save_config(cfg)
        db_entry = storage_mod.load_app_config_from_db()
        assert db_entry is not None
        assert db_entry[0].dish_types == ["Dessert"]


class TestLoadConfig:
    def test_migrated_db_has_default_config(self):
        cfg = load_config()
        assert cfg == AppConfig()

    def test_empty_db_returns_default_and_seeds_db(self, empty_db_config):
        cfg = load_config()
        assert cfg == AppConfig()
        assert storage_mod.load_app_config_from_db() is not None

    def test_db_present_returns_db_value(self):
        db_cfg = AppConfig(dish_types=["Main", "Dessert"])
        storage_mod.save_app_config_to_db(db_cfg)
        assert load_config() == db_cfg


@pytest.mark.no_db
class TestDatabaseUrl:
    def test_missing_database_url_raises(self):
        with pytest.raises(DatabaseNotConfiguredError, match="DATABASE_URL"):
            database_url()

    def test_blank_database_url_raises(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "  ")
        with pytest.raises(DatabaseNotConfiguredError):
            database_url()
