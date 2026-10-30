"""Tests for the "find my events and dishes by email" feature."""

import pytest

from app import ratelimit
from app.storage import (
    find_events_by_host_email,
    find_submissions_by_contributor_email,
    get_event_by_management_token,
)

from .test_email_routes import _add_dish, _create, _slug_for

GENERIC = "If an event or dish is associated with this email, you will receive an email with details."


def _lookup(client, email):
    return client.post("/find", data={"email": email}, follow_redirects=False)


def _lookup_to_end(client, email):
    resp = client.post("/find", data={"email": email}, follow_redirects=True)
    assert resp.status_code == 200
    return resp


@pytest.fixture()
def seeded(client, email_on, sent):
    """One event hosted by host@, plus a dish from guest@ at that event."""
    token = _create(client, host_email="host@example.com")
    slug = _slug_for(token)
    _add_dish(client, slug, contributor_email="guest@example.com")
    sent.clear()
    ratelimit.limiter.reset()
    return token, slug


class TestStorageLookups:
    def test_events_by_host_email_case_insensitive(self, client, email_on, sent):
        token = _create(client, host_email="Host@Example.com")
        found = find_events_by_host_email("  host@example.COM ")
        assert [e.management_token for e in found] == [token]

    def test_unknown_address_finds_nothing(self, seeded):
        assert find_events_by_host_email("nobody@example.com") == []
        assert find_submissions_by_contributor_email("nobody@example.com") == []

    def test_submissions_pair_dish_with_event(self, seeded):
        token, slug = seeded
        found = find_submissions_by_contributor_email("GUEST@example.com")
        assert len(found) == 1
        dish, event = found[0]
        assert dish.dish_name == "Mac & Cheese"
        assert event.slug == slug

    def test_host_items_are_not_submissions(self, client, email_on, sent):
        _create(
            client,
            host_email="host@example.com",
            host_item_names=["Turkey"],
            host_item_types=["Main"],
            host_item_notes=[""],
        )
        assert find_submissions_by_contributor_email("host@example.com") == []


class TestFindPage:
    def test_form_available_when_email_configured(self, client, email_on):
        resp = client.get("/find")
        assert resp.status_code == 200
        assert 'name="email"' in resp.text

    def test_404_when_email_not_configured(self, client, email_off):
        assert client.get("/find").status_code == 404
        assert _lookup(client, "a@b.co").status_code == 404

    def test_landing_links_only_when_configured(self, client, email_on):
        assert "/find" in client.get("/").text

    def test_landing_has_no_link_when_unconfigured(self, client, email_off):
        assert "/find" not in client.get("/").text

    def test_done_message(self, client, email_on):
        assert GENERIC in client.get("/find?done=1").text
        assert GENERIC not in client.get("/find").text


class TestLookupEmails:
    def test_host_gets_public_and_management_links(self, client, seeded, sent):
        token, slug = seeded
        _lookup(client, "host@example.com")
        assert [m["to"] for m in sent] == ["host@example.com"]
        msg = sent[0]
        assert f"https://dish.example.com/e/{slug}" in msg["text"]
        assert f"https://dish.example.com/manage/{token}" in msg["text"]
        assert f"https://dish.example.com/manage/{token}" in msg["html"]

    def test_guest_gets_event_link_but_never_management_link(self, client, seeded, sent):
        token, slug = seeded
        _lookup(client, "guest@example.com")
        assert [m["to"] for m in sent] == ["guest@example.com"]
        msg = sent[0]
        assert "Mac & Cheese" in msg["text"]
        assert f"https://dish.example.com/e/{slug}" in msg["text"]
        assert token not in msg["text"] and token not in msg["html"]
        assert "/manage/" not in msg["text"]
        assert "reach out to the event host" in msg["text"].lower()

    def test_one_email_when_address_is_both_host_and_guest(self, client, email_on, sent):
        token = _create(client, host_email="both@example.com")
        slug = _slug_for(token)
        other = _create(client, name="Other Potluck")
        _add_dish(client, _slug_for(other), contributor_email="both@example.com")
        sent.clear()
        ratelimit.limiter.reset()
        _lookup(client, "both@example.com")
        assert len(sent) == 1
        text = sent[0]["text"]
        assert f"/manage/{token}" in text and "Other Potluck" in text and slug in text

    def test_lookup_matches_case_insensitively(self, client, seeded, sent):
        _lookup(client, "HOST@Example.com")
        assert [m["to"] for m in sent] == ["HOST@Example.com"]

    def test_unknown_address_sends_nothing(self, client, seeded, sent):
        _lookup(client, "typo@example.com")
        assert sent == []

    def test_html_is_escaped(self, client, email_on, sent):
        token = _create(client, name="<script>alert(1)</script>", host_email="x@example.com")
        sent.clear()
        ratelimit.limiter.reset()
        _lookup(client, "x@example.com")
        assert "<script>" not in sent[0]["html"]

    def test_closed_event_is_no_longer_found(self, client, seeded, sent):
        token, _ = seeded
        client.post(
            f"/manage/{token}",
            data={"name": "Mail Potluck", "dish_types_input": "Main\nSide"},
        )  # no is_active -> closes -> emails purged
        sent.clear()
        _lookup(client, "host@example.com")
        _lookup(client, "guest@example.com")
        assert sent == []


class TestNoEnumeration:
    """The response must not reveal whether an address is known."""

    def test_known_unknown_and_limited_responses_are_identical(self, client, seeded, sent):
        known = _lookup(client, "host@example.com")
        unknown = _lookup(client, "typo@example.com")
        # Exhaust this address's allowance, then hit it again while limited.
        for _ in range(ratelimit.LOOKUP_ADDRESS_LIMIT):
            _lookup(client, "guest@example.com")
        limited = _lookup(client, "guest@example.com")
        assert known.status_code == unknown.status_code == limited.status_code == 303
        assert known.headers["location"] == unknown.headers["location"] == limited.headers["location"]
        assert known.text == unknown.text == limited.text
        assert (
            _lookup_to_end(client, "host@example.com").text
            == _lookup_to_end(client, "typo2@example.com").text
        )
        assert GENERIC in _lookup_to_end(client, "typo3@example.com").text

    def test_malformed_address_rejected_with_no_send(self, client, email_on, sent):
        resp = _lookup(client, "not-an-email")
        assert resp.status_code == 400
        assert "valid email" in resp.text
        assert sent == []

    def test_blank_address_rejected(self, client, email_on, sent):
        assert _lookup(client, "   ").status_code == 400
        assert sent == []


class TestLookupRateLimits:
    def test_per_address_limit(self, client, seeded, sent):
        for _ in range(ratelimit.LOOKUP_ADDRESS_LIMIT + 3):
            _lookup(client, "host@example.com")
        assert len(sent) == ratelimit.LOOKUP_ADDRESS_LIMIT

    def test_per_ip_limit(self, client, seeded, sent):
        for i in range(ratelimit.LOOKUP_IP_LIMIT + 3):
            _lookup(client, f"someone{i}@example.com")
        # None exist, so nothing is sent, but the limiter must still have been hit.
        assert sent == []
        assert ratelimit.limiter.allow("lookup-ip:127.0.0.1", ratelimit.LOOKUP_IP_LIMIT) is False

    def test_lookup_limits_are_separate_from_creation_limits(self, client, email_on, sent):
        for _ in range(ratelimit.ADDRESS_LIMIT):
            _create(client, host_email="same@example.com")
        sent.clear()
        _lookup(client, "same@example.com")
        assert len(sent) == 1


def test_send_failure_is_swallowed(client, email_on, monkeypatch):
    import httpx

    from app import mailer

    _create(client, host_email="host@example.com")  # real mailer, Resend unreachable
    calls = []

    def boom(*args, **kwargs):
        calls.append(1)
        raise httpx.ConnectError("down")

    monkeypatch.setattr(mailer.httpx, "post", boom)
    ratelimit.limiter.reset()
    resp = _lookup(client, "host@example.com")
    assert resp.status_code == 303  # still the normal response
    assert calls, "the lookup should have attempted to send"
