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


def _add_dish(client, slug, **extra):
    data = {
        "contributor": "Gus",
        "dish_name": "Mac & Cheese",
        "dish_type": "Main",
    }
    data.update(extra)
    return client.post(f"/e/{slug}/add", data=data, follow_redirects=False)


def _slug_for(token):
    return get_event_by_management_token(token).slug


class TestGuestEmail:
    def test_add_form_shows_email_field_when_configured(self, client, email_on, sent):
        slug = _slug_for(_create(client))
        assert 'name="contributor_email"' in client.get(f"/e/{slug}/add").text

    def test_add_form_hides_email_field_when_unconfigured(self, client, email_off):
        slug = _slug_for(_create(client))
        assert 'name="contributor_email"' not in client.get(f"/e/{slug}/add").text

    def test_guest_confirmation_sent(self, client, email_on, sent):
        token = _create(client)
        slug = _slug_for(token)
        resp = _add_dish(client, slug, contributor_email="gus@example.com")
        assert resp.status_code == 303
        assert len(sent) == 1
        msg = sent[0]
        assert msg["to"] == "gus@example.com"
        assert "Mac & Cheese" in msg["text"]
        assert "Hosty" in msg["text"]
        assert "reach out to the event host" in msg["text"].lower()
        # The management token must never reach a guest.
        assert token not in msg["text"] and token not in msg["html"]
        assert f"https://dish.example.com/e/{slug}" in msg["text"]

    def test_html_is_escaped(self, client, email_on, sent):
        slug = _slug_for(_create(client))
        _add_dish(
            client,
            slug,
            dish_name="<script>x</script>",
            contributor_email="gus@example.com",
        )
        assert "<script>" not in sent[0]["html"]

    def test_no_email_without_address(self, client, email_on, sent):
        slug = _slug_for(_create(client))
        _add_dish(client, slug)
        assert sent == []

    def test_invalid_guest_email_400(self, client, email_on, sent):
        slug = _slug_for(_create(client))
        assert _add_dish(client, slug, contributor_email="bad").status_code == 400

    def test_email_not_stored_when_unconfigured(self, client, email_off, sent):
        from app.storage import load_dishes_for_event

        token = _create(client)
        event = get_event_by_management_token(token)
        _add_dish(client, event.slug, contributor_email="gus@example.com")
        assert sent == []
        assert load_dishes_for_event(event.id)[0].contributor_email is None

    def test_host_notified_when_opted_in(self, client, email_on, sent):
        token = _create(client, host_email="host@example.com", notify_host="1")
        sent.clear()
        _add_dish(client, _slug_for(token))
        assert [m["to"] for m in sent] == ["host@example.com"]
        assert "Gus" in sent[0]["subject"]
        assert f"/manage/{token}" in sent[0]["text"]

    def test_host_not_notified_when_not_opted_in(self, client, email_on, sent):
        token = _create(client, host_email="host@example.com")
        sent.clear()
        _add_dish(client, _slug_for(token))
        assert sent == []

    def test_both_emails_when_both_apply(self, client, email_on, sent):
        token = _create(client, host_email="host@example.com", notify_host="1")
        sent.clear()
        _add_dish(client, _slug_for(token), contributor_email="gus@example.com")
        assert sorted(m["to"] for m in sent) == ["gus@example.com", "host@example.com"]
