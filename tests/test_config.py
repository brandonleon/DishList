"""Unit tests for app/config.py — load/save logic and file migration."""

import json

import pytest

import app.storage as storage_mod
from app.config import (
    AppConfig,
    load_config,
    save_config,
)


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    """Point CONFIG_PATH at a temp file for each test."""
    path = tmp_path / "config.json"
    monkeypatch.setattr("app.config.CONFIG_PATH", path)
    return path


@pytest.fixture
def empty_db_config(isolated_db):
    """Clear config entries seeded by isolated_db so the DB looks brand-new."""
    with storage_mod._get_connection() as conn:
        conn.execute("DELETE FROM config_entries")
    return isolated_db


# ── save_config ────────────────────────────────────────────────────────────────


class TestSaveConfig:
    def test_writes_to_db(self, isolated_db):
        cfg = AppConfig(dish_types=["Dessert"])
        save_config(cfg)
        db_entry = storage_mod.load_app_config_from_db()
        assert db_entry is not None
        assert db_entry[0].dish_types == ["Dessert"]

    def test_does_not_write_to_file(self, isolated_db, config_path):
        cfg = AppConfig(dish_types=["Dessert"])
        save_config(cfg)
        assert not config_path.exists()


# ── load_config ────────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_no_file_no_db_returns_default_and_seeds_db(
        self, empty_db_config, config_path
    ):
        cfg = load_config()
        assert isinstance(cfg, AppConfig)
        assert cfg.dish_types
        assert storage_mod.load_app_config_from_db() is not None

    def test_db_present_returns_db_value(self, isolated_db, config_path):
        db_cfg = AppConfig(dish_types=["Main", "Dessert"])
        storage_mod.save_app_config_to_db(db_cfg)
        result = load_config()
        assert result == db_cfg

    def test_no_db_but_file_exists_migrates_to_db(self, empty_db_config, config_path):
        file_cfg = AppConfig(dish_types=["Main", "Side"])
        config_path.write_text(json.dumps(file_cfg.model_dump()))
        result = load_config()
        assert result == file_cfg
        assert storage_mod.load_app_config_from_db() is not None

    def test_migration_sets_web_admin_enabled_from_networks(
        self, empty_db_config, config_path
    ):
        data = {"dish_types": ["Main"], "admin_networks": ["10.0.0.1/32"]}
        config_path.write_text(json.dumps(data))
        result = load_config()
        assert result.web_admin_enabled is True

    def test_db_takes_priority_over_file(self, isolated_db, config_path):
        db_cfg = AppConfig(dish_types=["DB Only"])
        storage_mod.save_app_config_to_db(db_cfg)
        file_cfg = AppConfig(dish_types=["File Only"])
        config_path.write_text(json.dumps(file_cfg.model_dump()))
        result = load_config()
        assert result == db_cfg
