"""Unit tests for app/config.py — load/save logic, file helpers, migration."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import app.storage as storage_mod
from app.config import (
    AppConfig,
    _get_file_updated_at,
    _is_file_newer,
    _load_config_from_file,
    _write_config_to_file,
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


# ── _load_config_from_file ─────────────────────────────────────────────────────

class TestLoadConfigFromFile:
    def test_returns_none_when_no_file(self, config_path):
        assert _load_config_from_file() is None

    def test_loads_valid_file(self, config_path):
        cfg = AppConfig(dish_types=["Main", "Side"])
        config_path.write_text(json.dumps(cfg.model_dump()))
        assert _load_config_from_file() == cfg

# ── _write_config_to_file ──────────────────────────────────────────────────────

class TestWriteConfigToFile:
    def test_writes_json_to_config_path(self, config_path):
        cfg = AppConfig(dish_types=["Appetizer"])
        _write_config_to_file(cfg)
        data = json.loads(config_path.read_text())
        assert data["dish_types"] == ["Appetizer"]


# ── _get_file_updated_at ───────────────────────────────────────────────────────

class TestGetFileUpdatedAt:
    def test_returns_none_when_no_file(self, config_path):
        assert _get_file_updated_at() is None

    def test_returns_timezone_aware_datetime_when_file_exists(self, config_path):
        config_path.write_text("{}")
        result = _get_file_updated_at()
        assert isinstance(result, datetime)
        assert result.tzinfo is not None


# ── _is_file_newer ─────────────────────────────────────────────────────────────

class TestIsFileNewer:
    def test_file_newer_than_db(self):
        now = datetime.now(timezone.utc)
        assert _is_file_newer(now, now - timedelta(hours=1)) is True

    def test_db_newer_than_file(self):
        now = datetime.now(timezone.utc)
        assert _is_file_newer(now - timedelta(hours=1), now) is False

    def test_only_file_date_is_newer(self):
        assert _is_file_newer(datetime.now(timezone.utc), None) is True

    def test_only_db_date_returns_false(self):
        assert _is_file_newer(None, datetime.now(timezone.utc)) is False

    def test_neither_date_returns_false(self):
        assert _is_file_newer(None, None) is False


# ── save_config ────────────────────────────────────────────────────────────────

class TestSaveConfig:
    def test_writes_to_file_and_db(self, isolated_db, config_path):
        cfg = AppConfig(dish_types=["Dessert"])
        save_config(cfg)

        assert json.loads(config_path.read_text())["dish_types"] == ["Dessert"]
        db_entry = storage_mod.load_app_config_from_db()
        assert db_entry is not None
        assert db_entry[0].dish_types == ["Dessert"]


# ── load_config ────────────────────────────────────────────────────────────────

class TestLoadConfig:
    def test_no_file_no_db_returns_default_and_persists(self, empty_db_config, config_path):
        cfg = load_config()
        assert isinstance(cfg, AppConfig)
        assert cfg.dish_types
        # Both sinks should now exist
        assert config_path.exists()
        assert storage_mod.load_app_config_from_db() is not None

    def test_only_file_saves_to_db(self, empty_db_config, config_path):
        file_cfg = AppConfig(dish_types=["Main", "Side"])
        config_path.write_text(json.dumps(file_cfg.model_dump()))

        result = load_config()

        assert result == file_cfg
        assert storage_mod.load_app_config_from_db() is not None

    def test_only_db_writes_to_file(self, isolated_db, config_path):
        result = load_config()
        assert config_path.exists()
        assert isinstance(result, AppConfig)

    def test_both_file_newer_different_updates_db(self, isolated_db, config_path):
        db_cfg = AppConfig(dish_types=["Main"])
        storage_mod.save_app_config_to_db(db_cfg)

        file_cfg = AppConfig(dish_types=["Appetizer", "Main"])
        config_path.write_text(json.dumps(file_cfg.model_dump()))

        with patch("app.config._is_file_newer", return_value=True):
            result = load_config()

        assert result == file_cfg
        db_result = storage_mod.load_app_config_from_db()
        assert db_result is not None
        assert db_result[0] == file_cfg

    def test_both_file_newer_same_skips_db_write(self, isolated_db, config_path):
        cfg = AppConfig(dish_types=["Main"])
        storage_mod.save_app_config_to_db(cfg)
        config_path.write_text(json.dumps(cfg.model_dump()))

        with patch("app.config._is_file_newer", return_value=True), \
             patch("app.config._save_config_to_db") as mock_save:
            result = load_config()

        mock_save.assert_not_called()
        assert result == cfg

    def test_both_db_newer_different_updates_file(self, isolated_db, config_path):
        db_cfg = AppConfig(dish_types=["Main", "Dessert"])
        storage_mod.save_app_config_to_db(db_cfg)

        file_cfg = AppConfig(dish_types=["Side"])
        config_path.write_text(json.dumps(file_cfg.model_dump()))

        with patch("app.config._is_file_newer", return_value=False):
            result = load_config()

        assert result == db_cfg
        assert _load_config_from_file() == db_cfg
