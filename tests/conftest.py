"""Shared fixtures for DishList tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import (
    DB_PATH,
    _get_connection,
    init_db,
    reset_tags_to_defaults,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point the DB and config file at fresh temp paths for every test."""
    import app.config as config_mod
    import app.storage as storage_mod

    test_db = tmp_path / "test_dishlist.db"
    test_config = tmp_path / "test_config.json"
    monkeypatch.setattr(storage_mod, "DB_PATH", test_db)
    monkeypatch.setattr(config_mod, "CONFIG_PATH", test_config)
    init_db()
    yield test_db


@pytest.fixture()
def client(isolated_db):
    """FastAPI TestClient with a clean DB.

    The client peer is fixed to 127.0.0.1 so tests can exercise the
    IP-allowlist gates without bypass.
    """
    with TestClient(
        app, raise_server_exceptions=True, client=("127.0.0.1", 50000)
    ) as c:
        yield c
