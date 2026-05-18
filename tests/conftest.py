"""Shared fixtures for DishList tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import (
    init_db,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point the DB at a fresh temp file for every test."""
    import app.storage as storage_mod

    test_db = tmp_path / "test_dishlist.db"
    monkeypatch.setattr(storage_mod, "DB_PATH", test_db)
    init_db()
    yield test_db


@pytest.fixture()
def client(isolated_db):
    """FastAPI TestClient with a clean DB."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
