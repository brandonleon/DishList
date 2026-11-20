"""Plain-language feedback for non-technical guests and hosts: friendly error
pages, a thank-you after adding a dish, and confirmations on the host page."""

from datetime import date

from app.main import _friendly_date
from app.storage import get_event_by_management_token

HTML = {"accept": "text/html,application/xhtml+xml"}


def _create_event(client, **extra):
    resp = client.post(
        "/create",
        data={
            "name": "UX Potluck",
            "dish_types_input": "Main\nSide",
            "host_name": "Sam",
            **extra,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    token = resp.headers["location"].split("/manage/")[1].split("?")[0]
    return token, get_event_by_management_token(token)


def _add_dish(client, slug, contributor="Alex", dish_name="Lemon Pasta"):
    return client.post(
        f"/e/{slug}/add",
        data={"contributor": contributor, "dish_name": dish_name, "dish_type": "Main"},
        follow_redirects=False,
    )


# ── Error pages ───────────────────────────────────────────────────────────────


class TestFriendlyErrors:
    def test_browser_gets_readable_page_for_bad_event_link(self, client):
        resp = client.get("/e/no-such-event", headers=HTML)
        assert resp.status_code == 404
        assert resp.headers["content-type"].startswith("text/html")
        assert (
            "We can&#39;t find that event" in resp.text
            or "We can't find that event" in resp.text
        )
        assert '"detail"' not in resp.text

    def test_api_clients_still_get_json(self, client):
        resp = client.get("/e/no-such-event")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Event not found"}

    def test_htmx_requests_still_get_json(self, client):
        resp = client.get("/e/nope/cards/grid", headers={**HTML, "hx-request": "true"})
        assert resp.headers["content-type"].startswith("application/json")

    def test_unknown_route_is_friendly(self, client):
        resp = client.get("/totally/made/up", headers=HTML)
        assert resp.status_code == 404
        assert "We can" in resp.text and "find that page" in resp.text

    def test_closed_event_links_back_to_board(self, client):
        token, event = _create_event(client)
        client.post(
            f"/manage/{token}",
            data={"name": event.name, "dish_types_input": "Main", "host_name": "Sam"},
        )
        resp = client.get(f"/e/{event.slug}/add", headers=HTML)
        assert resp.status_code == 403
        assert "closed to new dishes" in resp.text
        assert f'href="/e/{event.slug}"' in resp.text


# ── Guest thank-you ───────────────────────────────────────────────────────────


class TestGuestThanks:
    def test_add_redirects_with_added_id(self, client):
        _, event = _create_event(client)
        resp = _add_dish(client, event.slug)
        assert resp.status_code == 303
        assert f"/e/{event.slug}?added=" in resp.headers["location"]

    def test_board_thanks_and_highlights_new_dish(self, client):
        _, event = _create_event(client)
        _add_dish(client, event.slug, "Bea", "Garlic Bread")
        location = _add_dish(client, event.slug).headers["location"]
        added_id = location.split("added=")[1]
        for view in ("cards", "table"):
            html = client.get(f"{location}&view={view}").text
            assert "Thanks, Alex! You" in html
            assert f'href="#dish-{added_id}"' in html
            assert html.count("dish-just-added") == 1
            assert html.count("Just added") == 1

    def test_bogus_added_id_shows_nothing(self, client):
        _, event = _create_event(client)
        _add_dish(client, event.slug)
        for value in ("999999", "abc", ""):
            html = client.get(f"/e/{event.slug}?added={value}").text
            assert (
                "You&#39;re on the list" not in html
                and "You're on the list" not in html
            )
            assert "dish-just-added" not in html.replace(".dish-just-added", "")


# ── Host confirmations ────────────────────────────────────────────────────────


class TestHostNotices:
    def test_new_event_shows_next_steps(self, client):
        resp = client.post(
            "/create",
            data={"name": "Fresh", "dish_types_input": "Main", "host_name": "Sam"},
            follow_redirects=False,
        )
        assert resp.headers["location"].endswith("?notice=created")
        html = client.get(resp.headers["location"]).text
        assert "Your potluck is ready!" in html
        assert "Share the guest link" in html

    def test_management_link_box_has_no_query_string(self, client):
        token, _ = _create_event(client)
        html = client.get(f"/manage/{token}?notice=created").text
        manage_input = html.split('id="manage-link"')[1].split("/>")[0]
        assert f'/manage/{token}"' in manage_input
        assert "notice" not in manage_input

    def test_saving_settings_confirms(self, client):
        token, event = _create_event(client)
        resp = client.post(
            f"/manage/{token}",
            data={
                "name": event.name,
                "dish_types_input": "Main",
                "host_name": "Sam",
                "is_active": "1",
            },
        )
        assert "Your event settings are saved." in resp.text

    def test_host_item_add_and_remove_confirm(self, client):
        token, _ = _create_event(client)
        resp = client.post(
            f"/manage/{token}/host-items",
            data={"dish_name": "Turkey", "dish_type": "Main"},
        )
        assert "Added to your house contributions." in resp.text

    def test_unknown_notice_is_ignored(self, client):
        token, _ = _create_event(client)
        html = client.get(f"/manage/{token}?notice=<script>").text
        assert "alert-success" not in html


# ── Dates ─────────────────────────────────────────────────────────────────────


def test_friendly_date():
    assert _friendly_date(date(2026, 11, 26)) == "Thursday, November 26, 2026"
    assert _friendly_date("2026-07-04") == "Saturday, July 4, 2026"
    assert _friendly_date(None) == ""


def test_board_shows_friendly_date(client):
    _, event = _create_event(client, event_date="2026-11-26")
    html = client.get(f"/e/{event.slug}").text
    assert "Thursday, November 26, 2026" in html
    assert "2026-11-26" not in html.split("<h1")[1].split("</section>")[0]
