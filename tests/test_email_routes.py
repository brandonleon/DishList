"""Route-level tests for the optional email features."""

import pytest

from app import mailer
from app.storage import get_event_by_management_token


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


def _create(client, **extra):
    data = {"name": "Mail Potluck", "dish_types_input": "Main\nSide", "host_name": "Hosty"}
    data.update(extra)
    resp = client.post("/create", data=data, follow_redirects=False)
    assert resp.status_code == 303
    return resp.headers["location"].split("/manage/")[1]


class TestCreateEventEmail:
    def test_form_shows_email_fields_when_configured(self, client, email_on):
        assert 'name="host_email"' in client.get("/create").text

    def test_form_hides_email_fields_when_not_configured(self, client, email_off):
        assert 'name="host_email"' not in client.get("/create").text

    def test_host_gets_management_link(self, client, email_on, sent):
        token = _create(
            client,
            host_email="host@example.com",
            host_item_names=["Turkey"],
            host_item_types=["Main"],
            host_item_notes=[""],
        )
        assert len(sent) == 1
        msg = sent[0]
        assert msg["to"] == "host@example.com"
        assert f"https://dish.example.com/manage/{token}" in msg["text"]
        assert f"https://dish.example.com/manage/{token}" in msg["html"]
        assert "Turkey" in msg["text"]
        event = get_event_by_management_token(token)
        assert event.host_email == "host@example.com"
        assert event.notify_host is False

    def test_notify_checkbox_saved(self, client, email_on, sent):
        token = _create(client, host_email="h@example.com", notify_host="1")
        assert get_event_by_management_token(token).notify_host is True

    def test_no_email_when_field_blank(self, client, email_on, sent):
        token = _create(client, host_email="  ")
        assert sent == []
        assert get_event_by_management_token(token).host_email is None

    def test_invalid_email_400(self, client, email_on, sent):
        resp = client.post(
            "/create",
            data={"name": "X", "dish_types_input": "Main", "host_email": "nope"},
        )
        assert resp.status_code == 400
        assert sent == []

    def test_email_ignored_and_not_stored_when_unconfigured(
        self, client, email_off, sent
    ):
        token = _create(client, host_email="host@example.com")
        assert sent == []
        assert get_event_by_management_token(token).host_email is None

    def test_send_failure_does_not_break_creation(self, client, email_on, monkeypatch):
        import httpx

        def boom(*a, **k):
            raise httpx.ConnectError("down")

        monkeypatch.setattr(mailer.httpx, "post", boom)
        token = _create(client, host_email="host@example.com")
        assert get_event_by_management_token(token) is not None
