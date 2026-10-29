"""Shared fixtures for DishList tests."""

import pytest
from fastapi.testclient import TestClient

from app import mailer
from app.main import app
from app.storage import (
    init_db,
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


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from app.ratelimit import limiter

    limiter.reset()
    yield
    limiter.reset()


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


@pytest.fixture()
def email_on(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("RESEND_FROM", "DishList <hi@example.com>")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://dish.example.com")


@pytest.fixture()
def sent(monkeypatch):
    """Capture outgoing mail instead of calling Resend."""
    messages = []

    def fake_send(to, subject, text, html=None):
        messages.append({"to": to, "subject": subject, "text": text, "html": html})
        return True

    monkeypatch.setattr(mailer, "send_email", fake_send)
    return messages


@pytest.fixture()
def email_off(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("RESEND_FROM", raising=False)
