"""Rate limiter unit tests and email-abuse route tests."""

from app import ratelimit
from app.ratelimit import RateLimiter
from app.storage import get_event_by_management_token

from .test_email_routes import _add_dish, _create, _slug_for


def test_limiter_blocks_after_limit_and_recovers():
    rl = RateLimiter()
    assert all(rl.allow("k", 3, 60, now=0) for _ in range(3))
    assert rl.allow("k", 3, 60, now=1) is False
    assert rl.allow("other", 3, 60, now=1) is True
    assert rl.allow("k", 3, 60, now=61) is True


def test_limiter_sweeps_stale_keys(monkeypatch):
    monkeypatch.setattr(ratelimit, "_SWEEP_THRESHOLD", 2)
    rl = RateLimiter()
    for i in range(4):
        rl.allow(f"k{i}", 1, 10, now=0)
    rl.allow("fresh", 1, 10, now=100)
    assert set(rl._hits) == {"fresh"}


def test_same_address_is_capped(client, email_on, sent):
    for _ in range(ratelimit.ADDRESS_LIMIT + 2):
        _create(client, host_email="victim@example.com")
    assert len(sent) == ratelimit.ADDRESS_LIMIT


def test_address_comparison_is_case_insensitive(client, email_on, sent):
    for i in range(ratelimit.ADDRESS_LIMIT + 1):
        _create(client, host_email="Victim@Example.com" if i % 2 else "victim@example.com")
    assert len(sent) == ratelimit.ADDRESS_LIMIT


def test_ip_is_capped_and_request_still_succeeds(client, email_on, sent):
    tokens = [
        _create(client, host_email=f"user{i}@example.com")
        for i in range(ratelimit.IP_LIMIT + 2)
    ]
    assert len(sent) == ratelimit.IP_LIMIT
    # Over-limit events are still created, just without a stored address.
    assert get_event_by_management_token(tokens[-1]).host_email is None


def test_host_notices_capped_per_event(client, email_on, sent):
    token = _create(client, host_email="h@example.com", notify_host="1")
    slug = _slug_for(token)
    sent.clear()
    for _ in range(ratelimit.EVENT_NOTICE_LIMIT + 5):
        _add_dish(client, slug)
    assert len(sent) == ratelimit.EVENT_NOTICE_LIMIT


def test_link_resend_capped(client, email_on, sent):
    token = _create(client, host_email="h@example.com")
    codes = [
        client.post(f"/manage/{token}/email-link", follow_redirects=False).status_code
        for _ in range(ratelimit.LINK_RESEND_LIMIT + 1)
    ]
    assert codes == [303] * ratelimit.LINK_RESEND_LIMIT + [429]
