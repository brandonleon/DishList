"""Tests for the Resend mailer."""

import httpx
import pytest

from app import mailer


@pytest.fixture()
def resend_env(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("RESEND_FROM", "DishList <hi@example.com>")


def test_not_configured_by_default(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("RESEND_FROM", raising=False)
    assert mailer.is_configured() is False
    assert mailer.send_email("a@b.co", "s", "t") is False


def test_requires_both_key_and_sender(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.delenv("RESEND_FROM", raising=False)
    assert mailer.is_configured() is False


def test_send_email_posts_to_resend(resend_env, monkeypatch):
    calls = []

    def fake_post(url, json, headers, timeout):
        calls.append((url, json, headers))
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(mailer.httpx, "post", fake_post)
    assert mailer.send_email("guest@example.com", "Hi", "body", "<p>body</p>") is True
    url, payload, headers = calls[0]
    assert url == mailer.RESEND_API_URL
    assert payload["to"] == ["guest@example.com"]
    assert payload["from"] == "DishList <hi@example.com>"
    assert payload["html"] == "<p>body</p>"
    assert headers["Authorization"] == "Bearer re_test"


def test_send_email_swallows_http_errors(resend_env, monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(mailer.httpx, "post", boom)
    assert mailer.send_email("guest@example.com", "Hi", "body") is False


def test_send_email_false_on_error_status(resend_env, monkeypatch):
    def fake_post(url, json, headers, timeout):
        return httpx.Response(403, request=httpx.Request("POST", url))

    monkeypatch.setattr(mailer.httpx, "post", fake_post)
    assert mailer.send_email("guest@example.com", "Hi", "body") is False


def test_clean_email():
    assert mailer.clean_email(None) is None
    assert mailer.clean_email("   ") is None
    assert mailer.clean_email(" a@b.co ") == "a@b.co"
    for bad in ("nope", "a@b", "a b@c.de", "@x.co"):
        with pytest.raises(ValueError):
            mailer.clean_email(bad)


def test_public_base_url(monkeypatch):
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    assert mailer.public_base_url("http://x/") == "http://x"
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://dish.example.com/")
    assert mailer.public_base_url("http://x") == "https://dish.example.com"
