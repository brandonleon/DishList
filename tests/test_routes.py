"""Integration tests for the FastAPI routes via TestClient."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.config import AppConfig
from app.storage import load_tags

# ── Helpers ────────────────────────────────────────────────────────────────────


def _create_event(client, name="Test Potluck", dish_types="Main\nSide\nDessert"):
    resp = client.post(
        "/create",
        data={
            "name": name,
            "dish_types_input": dish_types,
            "host_name": "The Host",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    token = resp.headers["location"].split("/manage/")[1]
    return token


def _event_with_host_dish(client):
    from app.storage import get_event_by_management_token, load_dishes_for_event

    token = _create_event(client)
    client.post(
        f"/manage/{token}/host-items",
        data={"dish_name": "Turkey", "dish_type": "Side"},
    )
    event = get_event_by_management_token(token)
    assert event is not None
    host_dish = next(d for d in load_dishes_for_event(event.id) if d.is_host_item)
    return token, event, host_dish


def _event_with_guest_dish(client):
    from app.storage import get_event_by_management_token, load_dishes_for_event

    token = _create_event(client)
    event = get_event_by_management_token(token)
    assert event is not None
    client.post(
        f"/e/{event.slug}/add",
        data={"contributor": "Alice", "dish_name": "Pasta", "dish_type": "Main"},
    )
    guest_dish = next(d for d in load_dishes_for_event(event.id) if not d.is_host_item)
    return token, event, guest_dish


# ── Landing & create ───────────────────────────────────────────────────────────


class TestPublicRoutes:
    def test_landing_200(self, client):
        assert client.get("/").status_code == 200

    def test_create_form_200(self, client):
        assert client.get("/create").status_code == 200

    def test_create_event_redirects(self, client):
        resp = client.post(
            "/create",
            data={
                "name": "Friendsgiving",
                "dish_types_input": "Main\nSide",
                "host_name": "Host",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "/manage/" in resp.headers["location"]

    def test_create_event_missing_dish_types_400(self, client):
        # FastAPI returns 422 for missing required fields, 400 for app-level validation
        resp = client.post(
            "/create",
            data={
                "name": "Bad Event",
                "dish_types_input": "   ",  # whitespace only → app strips to empty list
                "host_name": "Host",
            },
        )
        assert resp.status_code == 400


# ── Event pages ────────────────────────────────────────────────────────────────


class TestEventRoutes:
    def test_event_home_200(self, client):
        token = _create_event(client)
        # Derive slug from manage page
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        resp = client.get(f"/e/{event.slug}")
        assert resp.status_code == 200

    def test_event_home_unknown_slug_404(self, client):
        assert client.get("/e/does-not-exist-xyz").status_code == 404

    def test_add_dish_form_200(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        resp = client.get(f"/e/{event.slug}/add")
        assert resp.status_code == 200

    def test_add_dish_form_contains_hidden_hint(self, client):
        """Hidden tags should be absent from initial rendered HTML (d-none)."""
        token = _create_event(client)
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        html = client.get(f"/e/{event.slug}/add").text
        # All hidden tag option divs must carry d-none
        import re

        hidden_options = re.findall(
            r'<div class="([^"]*)"[^>]*data-tag-hidden="true"', html
        )
        for classes in hidden_options:
            assert "d-none" in classes.split(), (
                f"Hidden tag option missing d-none: classes={classes!r}"
            )

    def test_submit_dish_redirects(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        resp = client.post(
            f"/e/{event.slug}/add",
            data={
                "contributor": "Alice",
                "dish_name": "Pasta",
                "dish_type": "Main",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_submit_unknown_dish_type_400(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        resp = client.post(
            f"/e/{event.slug}/add",
            data={
                "contributor": "Alice",
                "dish_name": "Pasta",
                "dish_type": "NotARealType",
            },
        )
        assert resp.status_code == 400


# ── Manage routes ──────────────────────────────────────────────────────────────


class TestManageRoutes:
    def test_manage_page_200(self, client):
        token = _create_event(client)
        assert client.get(f"/manage/{token}").status_code == 200

    def test_manage_bad_token_404(self, client):
        assert client.get("/manage/notavalidtoken").status_code == 404

    def test_update_event_settings(self, client):
        token = _create_event(client)
        resp = client.post(
            f"/manage/{token}",
            data={
                "name": "Updated Name",
                "dish_types_input": "Main\nSide",
                "host_name": "New Host",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        assert event.name == "Updated Name"


# ── Tag keyword JSON in add form ───────────────────────────────────────────────


class TestTagKeywordsInAddForm:
    def test_tag_keywords_json_present(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        html = client.get(f"/e/{event.slug}/add").text
        assert "const TAG_KEYWORDS" in html

    def test_hidden_tag_keywords_included(self, client):
        """Hidden tags' keywords must be in TAG_KEYWORDS for auto-detection."""
        import json
        import re

        token = _create_event(client)
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        html = client.get(f"/e/{event.slug}/add").text
        match = re.search(r"const TAG_KEYWORDS = ({.*?});", html, re.DOTALL)
        assert match, "TAG_KEYWORDS not found in page"
        kw_map = json.loads(match.group(1))
        # Gluten-free is hidden with keywords — must appear
        all_keywords = [kw for kws in kw_map.values() for kw in kws]
        assert "gluten-free" in all_keywords

    def test_cache_busting_on_static_assets(self, client):
        html = client.get("/").text
        assert "tag-picker.js?v=" in html
        assert "styles.css?v=" in html


# ── Admin fixture ──────────────────────────────────────────────────────────────


@pytest.fixture
def admin_client(client, monkeypatch):
    """TestClient with IP/web-admin gate bypassed."""
    monkeypatch.setattr("app.main._check_admin_access", lambda req, cfg: None)
    return client


# ── Helper function unit tests ─────────────────────────────────────────────────


class TestHelperFunctions:
    def test_format_dish_timestamp_string_input(self):
        from app.main import _format_dish_timestamp

        assert "Jan" in _format_dish_timestamp("2024-01-15T12:30:00")

    def test_format_dish_timestamp_naive_datetime(self):
        from app.main import _format_dish_timestamp

        assert "Jun" in _format_dish_timestamp(datetime(2024, 6, 1, 12, 0, 0))

    def test_filter_dishes_empty_query_returns_all(self):
        from app.main import _filter_dishes
        from app.models import DishEntry

        dishes = [
            DishEntry(event_id=1, contributor="A", dish_name="Pasta", dish_type="Main")
        ]
        assert _filter_dishes(dishes, "") == dishes

    def test_filter_dishes_matches_name(self):
        from app.main import _filter_dishes
        from app.models import DishEntry

        dishes = [
            DishEntry(
                event_id=1, contributor="Alice", dish_name="Pasta", dish_type="Main"
            ),
            DishEntry(
                event_id=1, contributor="Bob", dish_name="Salad", dish_type="Side"
            ),
        ]
        result = _filter_dishes(dishes, "pasta")
        assert len(result) == 1
        assert result[0].dish_name == "Pasta"

    def test_is_ip_allowed_matching_network(self):
        from app.main import _is_ip_allowed

        req = MagicMock()
        req.client.host = "127.0.0.1"
        assert _is_ip_allowed(req, ["127.0.0.1/32"]) is True

    def test_is_ip_allowed_rejected_ip(self):
        from app.main import _is_ip_allowed

        req = MagicMock()
        req.client.host = "10.0.0.1"
        assert _is_ip_allowed(req, ["192.168.1.0/24"]) is False

    def test_is_ip_allowed_invalid_host(self):
        from app.main import _is_ip_allowed

        req = MagicMock()
        req.client.host = "not-an-ip"
        assert _is_ip_allowed(req, ["127.0.0.1/32"]) is False

    def test_check_admin_access_disabled_raises_404(self):
        from fastapi import HTTPException

        from app.main import _check_admin_access

        req = MagicMock()
        req.client.host = "127.0.0.1"
        cfg = AppConfig(web_admin_enabled=False)
        with pytest.raises(HTTPException) as exc:
            _check_admin_access(req, cfg)
        assert exc.value.status_code == 404

    def test_check_admin_access_forbidden_ip_raises_403(self):
        from fastapi import HTTPException

        from app.main import _check_admin_access

        req = MagicMock()
        req.client.host = "10.10.10.10"
        cfg = AppConfig(web_admin_enabled=True, admin_networks=["192.168.0.0/16"])
        with pytest.raises(HTTPException) as exc:
            _check_admin_access(req, cfg)
        assert exc.value.status_code == 403


# ── Create event extended ──────────────────────────────────────────────────────


class TestCreateEventExtended:
    def test_create_with_valid_event_date(self, client):
        resp = client.post(
            "/create",
            data={
                "name": "Date Party",
                "dish_types_input": "Main",
                "host_name": "Host",
                "event_date": "2025-12-25",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_create_with_invalid_date_400(self, client):
        resp = client.post(
            "/create",
            data={
                "name": "Bad Date Party",
                "dish_types_input": "Main",
                "host_name": "Host",
                "event_date": "not-a-date",
            },
        )
        assert resp.status_code == 400

    def test_create_with_host_items(self, client):
        resp = client.post(
            "/create",
            data={
                "name": "Host Items Party",
                "dish_types_input": "Main\nSide",
                "host_name": "Host",
                "host_item_names": "Bread",
                "host_item_types": "InvalidType",  # not in dish_types → falls back to first
                "host_item_notes": "Fresh",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_create_skips_blank_host_item(self, client):
        resp = client.post(
            "/create",
            data={
                "name": "Party",
                "dish_types_input": "Main",
                "host_name": "Host",
                "host_item_names": "   ",  # blank → skipped
                "host_item_types": "Main",
                "host_item_notes": "",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303


# ── Event view modes & inactive event ─────────────────────────────────────────


class TestEventViewModes:
    def test_invalid_view_mode_defaults_to_cards(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        resp = client.get(f"/e/{event.slug}?view=bogus")
        assert resp.status_code == 200

    def test_inactive_event_add_form_403(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        # Deactivate via manage POST
        client.post(
            f"/manage/{token}",
            data={
                "name": event.name,
                "dish_types_input": "\n".join(event.dish_types),
                "host_name": event.host_name or "Host",
            },
        )  # is_active not included → False
        resp = client.get(f"/e/{event.slug}/add")
        assert resp.status_code == 403

    def test_inactive_event_submission_403(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        client.post(
            f"/manage/{token}",
            data={
                "name": event.name,
                "dish_types_input": "\n".join(event.dish_types),
                "host_name": event.host_name or "Host",
            },
        )
        resp = client.post(
            f"/e/{event.slug}/add",
            data={
                "contributor": "Alice",
                "dish_name": "Pasta",
                "dish_type": "Main",
            },
        )
        assert resp.status_code == 403

    def test_submit_unknown_tag_id_400(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        resp = client.post(
            f"/e/{event.slug}/add",
            data={
                "contributor": "Alice",
                "dish_name": "Pasta",
                "dish_type": "Main",
                "dietary_tags": "999999",  # non-existent tag ID
            },
        )
        assert resp.status_code == 400


# ── Partial routes ─────────────────────────────────────────────────────────────


class TestPartialRoutes:
    def test_table_rows_partial_200(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        assert client.get(f"/e/{event.slug}/table/rows").status_code == 200

    def test_card_grid_partial_200(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        assert client.get(f"/e/{event.slug}/cards/grid").status_code == 200

    def test_table_rows_with_search(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        assert client.get(f"/e/{event.slug}/table/rows?search=pasta").status_code == 200


# ── Manage sub-routes ──────────────────────────────────────────────────────────


class TestManageSubRoutes:
    def test_add_host_item_redirects(self, client):
        token = _create_event(client)
        resp = client.post(
            f"/manage/{token}/host-items",
            data={
                "dish_name": "Host Bread",
                "dish_type": "Side",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_add_host_item_invalid_type_400(self, client):
        token = _create_event(client)
        resp = client.post(
            f"/manage/{token}/host-items",
            data={
                "dish_name": "Thing",
                "dish_type": "NotAType",
            },
        )
        assert resp.status_code == 400

    def test_add_host_item_blank_name_400(self, client):
        token = _create_event(client)
        resp = client.post(
            f"/manage/{token}/host-items",
            data={"dish_name": "   ", "dish_type": "Side"},
        )
        assert resp.status_code == 400

    def test_edit_guest_dish_blank_contributor_400_and_page_still_loads(self, client):
        token, _event, guest_dish = _event_with_guest_dish(client)
        resp = client.post(
            f"/manage/{token}/dishes/{guest_dish.id}",
            data={"contributor": "  ", "dish_name": "Ham", "dish_type": "Side"},
        )
        assert resp.status_code == 400
        assert client.get(f"/manage/{token}").status_code == 200

    def test_edit_guest_dish_missing_contributor_400(self, client):
        token, _event, guest_dish = _event_with_guest_dish(client)
        resp = client.post(
            f"/manage/{token}/dishes/{guest_dish.id}",
            data={"dish_name": "Ham", "dish_type": "Side"},
        )
        assert resp.status_code == 400

    def test_edit_guest_dish_form_still_shows_contributor_and_tags(self, client):
        token, _event, guest_dish = _event_with_guest_dish(client)
        resp = client.get(f"/manage/{token}/dishes/{guest_dish.id}")
        assert resp.status_code == 200
        assert 'name="contributor"' in resp.text
        assert 'id="edit-dietary-tags"' in resp.text

    def test_edit_dish_blank_name_400(self, client):
        token, _event, guest_dish = _event_with_guest_dish(client)
        resp = client.post(
            f"/manage/{token}/dishes/{guest_dish.id}",
            data={"contributor": "Alice", "dish_name": "   ", "dish_type": "Side"},
        )
        assert resp.status_code == 400

    def test_manage_page_offers_edit_for_host_items(self, client):
        token, _event, host_dish = _event_with_host_dish(client)
        html = client.get(f"/manage/{token}").text
        assert f"/manage/{token}/dishes/{host_dish.id}" in html

    def test_edit_host_dish_form_hides_contributor_and_tags(self, client):
        token, _event, host_dish = _event_with_host_dish(client)
        resp = client.get(f"/manage/{token}/dishes/{host_dish.id}")
        assert resp.status_code == 200
        assert 'name="contributor"' not in resp.text
        assert 'id="edit-dietary-tags"' not in resp.text
        assert "The Host" in resp.text

    def test_edit_host_dish_updates_name_type_notes_only(self, client):
        from app.storage import load_dishes_for_event

        token, event, host_dish = _event_with_host_dish(client)
        resp = client.post(
            f"/manage/{token}/dishes/{host_dish.id}",
            data={
                "dish_name": "  Smoked Ham ",
                "dish_type": "Main",
                "notes": "Hickory",
                "contributor": "Someone Else",  # ignored for house dishes
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        updated = next(
            d for d in load_dishes_for_event(event.id) if d.id == host_dish.id
        )
        assert updated.dish_name == "Smoked Ham"
        assert updated.dish_type == "Main"
        assert updated.notes == "Hickory"
        assert updated.contributor == host_dish.contributor == "The Host"
        assert updated.is_host_item is True

    def test_delete_host_item_redirects(self, client):
        token = _create_event(client)
        client.post(
            f"/manage/{token}/host-items",
            data={
                "dish_name": "Host Bread",
                "dish_type": "Side",
            },
        )
        from app.storage import get_event_by_management_token, load_dishes_for_event

        event = get_event_by_management_token(token)
        assert event is not None
        host_dish = next(
            d for d in load_dishes_for_event(event.id) if d.dish_name == "Host Bread"
        )
        resp = client.post(
            f"/manage/{token}/host-items/{host_dish.id}/delete", follow_redirects=False
        )
        assert resp.status_code == 303

    def test_manage_edit_dish_form_200(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token, load_dishes_for_event

        event = get_event_by_management_token(token)
        assert event is not None
        client.post(
            f"/e/{event.slug}/add",
            data={
                "contributor": "Alice",
                "dish_name": "Pasta",
                "dish_type": "Main",
            },
        )
        guest_dish = next(
            d for d in load_dishes_for_event(event.id) if not d.is_host_item
        )
        assert client.get(f"/manage/{token}/dishes/{guest_dish.id}").status_code == 200

    def test_manage_edit_dish_submit_redirects(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token, load_dishes_for_event

        event = get_event_by_management_token(token)
        assert event is not None
        client.post(
            f"/e/{event.slug}/add",
            data={
                "contributor": "Alice",
                "dish_name": "Pasta",
                "dish_type": "Main",
            },
        )
        guest_dish = next(
            d for d in load_dishes_for_event(event.id) if not d.is_host_item
        )
        resp = client.post(
            f"/manage/{token}/dishes/{guest_dish.id}",
            data={
                "contributor": "Alice Updated",
                "dish_name": "Updated Pasta",
                "dish_type": "Main",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_manage_edit_dish_submit_invalid_type_400(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token, load_dishes_for_event

        event = get_event_by_management_token(token)
        assert event is not None
        client.post(
            f"/e/{event.slug}/add",
            data={
                "contributor": "Alice",
                "dish_name": "Pasta",
                "dish_type": "Main",
            },
        )
        guest_dish = next(
            d for d in load_dishes_for_event(event.id) if not d.is_host_item
        )
        resp = client.post(
            f"/manage/{token}/dishes/{guest_dish.id}",
            data={
                "contributor": "Alice",
                "dish_name": "Pasta",
                "dish_type": "NotAType",
            },
        )
        assert resp.status_code == 400

    def test_manage_delete_dish_redirects(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token, load_dishes_for_event

        event = get_event_by_management_token(token)
        assert event is not None
        client.post(
            f"/e/{event.slug}/add",
            data={
                "contributor": "Alice",
                "dish_name": "Pasta",
                "dish_type": "Main",
            },
        )
        guest_dish = next(
            d for d in load_dishes_for_event(event.id) if not d.is_host_item
        )
        resp = client.post(
            f"/manage/{token}/dishes/{guest_dish.id}/delete", follow_redirects=False
        )
        assert resp.status_code == 303

    def test_update_event_settings_empty_dish_types_400(self, client):
        token = _create_event(client)
        resp = client.post(
            f"/manage/{token}",
            data={
                "name": "Event",
                "dish_types_input": "   ",
                "host_name": "Host",
            },
        )
        assert resp.status_code == 400

    def test_update_event_settings_invalid_date_400(self, client):
        token = _create_event(client)
        resp = client.post(
            f"/manage/{token}",
            data={
                "name": "Event",
                "dish_types_input": "Main",
                "host_name": "Host",
                "event_date": "not-a-date",
            },
        )
        assert resp.status_code == 400


# ── Admin routes ───────────────────────────────────────────────────────────────


class TestAdminRoutes:
    def test_admin_page_200(self, admin_client):
        assert admin_client.get("/pantry-admin").status_code == 200

    def test_admin_tags_page_200(self, admin_client):
        assert admin_client.get("/pantry-admin/tags").status_code == 200

    def test_update_admin_settings_redirects(self, admin_client):
        resp = admin_client.post(
            "/pantry-admin",
            data={
                "dish_types_input": "Main\nSide\nDessert",
                "admin_networks_input": "127.0.0.1/32",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_update_admin_settings_empty_dish_types_400(self, admin_client):
        resp = admin_client.post(
            "/pantry-admin",
            data={
                "dish_types_input": "   ",
                "admin_networks_input": "127.0.0.1/32",
            },
        )
        assert resp.status_code == 400

    def test_update_admin_settings_empty_networks_400(self, admin_client):
        resp = admin_client.post(
            "/pantry-admin",
            data={
                "dish_types_input": "Main",
                "admin_networks_input": "  ",
            },
        )
        assert resp.status_code == 400

    def test_add_tag_action_success(self, admin_client):
        resp = admin_client.post(
            "/pantry-admin/tags",
            data={
                "tag_name": "Brand New Tag",
                "tag_category": "Dietary preferences",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "flash_success" in resp.headers["location"]

    def test_add_tag_action_duplicate_redirects_with_error(self, admin_client):
        # "Vegan" already exists in defaults
        resp = admin_client.post(
            "/pantry-admin/tags",
            data={
                "tag_name": "Vegan",
                "tag_category": "Dietary preferences",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "flash_error" in resp.headers["location"]

    def test_update_tag_action_success(self, admin_client):
        vegan = next(t for t in load_tags() if t.name == "Vegan")
        resp = admin_client.post(
            f"/pantry-admin/tags/{vegan.id}",
            data={
                "name": "Vegan",
                "category": "Dietary preferences",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_update_tag_action_conflict_redirects_with_error(self, admin_client):
        tags = load_tags()
        vegan = next(t for t in tags if t.name == "Vegan")
        # Try to rename vegan to vegetarian (conflict)
        resp = admin_client.post(
            f"/pantry-admin/tags/{vegan.id}",
            data={
                "name": "Vegetarian",
                "category": "Dietary preferences",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "flash_error" in resp.headers["location"]

    def test_reset_tags_action_redirects(self, admin_client):
        resp = admin_client.post("/pantry-admin/tags/reset", follow_redirects=False)
        assert resp.status_code == 303

    def test_delete_tag_action_redirects(self, admin_client):
        from app.storage import create_tag

        tag = create_tag("Temp Tag", "Content & serving")
        resp = admin_client.post(
            f"/pantry-admin/tags/{tag.id}/delete", follow_redirects=False
        )
        assert resp.status_code == 303

    def test_toggle_tag_visibility_action_redirects(self, admin_client):
        tag = load_tags()[0]
        resp = admin_client.post(
            f"/pantry-admin/tags/{tag.id}/visibility", follow_redirects=False
        )
        assert resp.status_code == 303

    def test_admin_delete_event_redirects(self, admin_client):
        token = _create_event(admin_client)
        from app.storage import get_event_by_management_token

        event = get_event_by_management_token(token)
        assert event is not None
        resp = admin_client.post(
            f"/pantry-admin/events/{event.id}/delete", follow_redirects=False
        )
        assert resp.status_code == 303

    def test_admin_page_disabled_404(self, client):
        """Admin is off by default; web_admin_enabled=False → 404."""
        from app.main import app as fastapi_app

        original = getattr(fastapi_app.state, "config", None)
        try:
            fastapi_app.state.config = AppConfig(web_admin_enabled=False)
            assert client.get("/pantry-admin").status_code == 404
        finally:
            if original is None:
                del fastapi_app.state.config
            else:
                fastapi_app.state.config = original


# ── Admin reload endpoint ─────────────────────────────────────────────────────


class TestAdminReloadEndpoint:
    def test_reload_disabled_admin_returns_404(self, client):
        from app.config import AppConfig
        from app.main import app

        app.state.config = AppConfig(
            web_admin_enabled=False, admin_networks=["127.0.0.1/32"]
        )
        assert client.post("/pantry-admin/reload").status_code == 404

    def test_reload_blocked_ip_returns_403(self, client):
        from app.config import AppConfig, save_config
        from app.main import app

        cfg = AppConfig(web_admin_enabled=True, admin_networks=["10.0.0.0/24"])
        save_config(cfg)
        app.state.config = cfg

        assert client.post("/pantry-admin/reload").status_code == 403

    def test_reload_refreshes_config_and_redirects(self, client):
        from app.config import AppConfig, save_config
        from app.main import app

        cfg = AppConfig(web_admin_enabled=True, admin_networks=["127.0.0.1/32"])
        save_config(cfg)
        app.state.config = cfg

        # Change config in DB without touching app.state
        updated = AppConfig(
            web_admin_enabled=True,
            admin_networks=["127.0.0.1/32"],
            metrics_enabled=True,
            metrics_networks=["10.0.0.0/8"],
        )
        save_config(updated)

        resp = client.post("/pantry-admin/reload", follow_redirects=False)
        assert resp.status_code == 303
        assert "flash_success" in resp.headers["location"]

        # app.state should now reflect the updated config
        assert app.state.config.metrics_enabled is True
        assert "10.0.0.0/8" in app.state.config.metrics_networks


class TestConfigRefresh:
    """Config changed elsewhere (CLI, another instance) reaches this instance."""

    def _age_cache(self, app):
        from app.main import CONFIG_REFRESH_SECONDS

        app.state.config_loaded_at -= CONFIG_REFRESH_SECONDS + 1

    def test_out_of_band_change_applies_after_refresh_interval(self, client):
        from app.config import AppConfig, save_config
        from app.main import app

        assert client.get("/pantry-admin").status_code == 404
        save_config(AppConfig(web_admin_enabled=True, admin_networks=["127.0.0.1/32"]))
        # Still within the refresh interval: the cached config is served.
        assert client.get("/pantry-admin").status_code == 404
        self._age_cache(app)
        assert client.get("/pantry-admin").status_code == 200

    def test_disabling_on_another_instance_reaches_this_one(self, client):
        from app.config import AppConfig, save_config
        from app.main import app

        save_config(AppConfig(web_admin_enabled=True, admin_networks=["127.0.0.1/32"]))
        self._age_cache(app)
        assert client.get("/pantry-admin").status_code == 200
        save_config(AppConfig(web_admin_enabled=False))
        self._age_cache(app)
        assert client.get("/pantry-admin").status_code == 404

    def test_admin_save_applies_immediately(self, client):
        from app.config import AppConfig, save_config
        from app.main import app

        save_config(AppConfig(web_admin_enabled=True, admin_networks=["127.0.0.1/32"]))
        self._age_cache(app)
        resp = client.post(
            "/pantry-admin",
            data={
                "dish_types_input": "Soup",
                "admin_networks_input": "127.0.0.1/32",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert app.state.config.dish_types == ["Soup"]


# ── Prometheus metrics endpoint ───────────────────────────────────────────────


class TestMetricsEndpoint:
    def test_metrics_disabled_by_default_returns_404(self, client):
        assert client.get("/metrics").status_code == 404

    def test_metrics_enabled_allowed_ip_returns_prometheus(self, client):
        from app.config import AppConfig, save_config
        from app.main import app

        cfg = AppConfig(metrics_enabled=True, metrics_networks=["127.0.0.1/32"])
        save_config(cfg)
        app.state.config = cfg

        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        body = resp.text
        assert "dishlist_http_requests_total" in body
        assert "dishlist_events_total" in body

    def test_metrics_blocked_ip_returns_403(self, client):
        from app.config import AppConfig, save_config
        from app.main import app

        cfg = AppConfig(metrics_enabled=True, metrics_networks=["10.0.0.0/24"])
        save_config(cfg)
        app.state.config = cfg

        assert client.get("/metrics").status_code == 403

    def test_metrics_disable_returns_404_even_with_allowlist(self, client):
        from app.config import AppConfig, save_config
        from app.main import app

        cfg = AppConfig(metrics_enabled=False, metrics_networks=["127.0.0.1/32"])
        save_config(cfg)
        app.state.config = cfg

        assert client.get("/metrics").status_code == 404

    def test_metrics_record_requests(self, client):
        from app.config import AppConfig, save_config
        from app.main import app

        cfg = AppConfig(metrics_enabled=True, metrics_networks=["127.0.0.1/32"])
        save_config(cfg)
        app.state.config = cfg

        client.get("/")
        body = client.get("/metrics").text
        # The landing route should have been recorded with status 200.
        assert 'path="/"' in body
        assert 'status="200"' in body


# ── Blank / oversized input must never be saved ───────────────────────────────


class TestBlankInputRejected:
    def test_guest_add_blank_contributor_400(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token, load_dishes_for_event

        event = get_event_by_management_token(token)
        assert event is not None
        resp = client.post(
            f"/e/{event.slug}/add",
            data={"contributor": "   ", "dish_name": "Pasta", "dish_type": "Main"},
        )
        assert resp.status_code == 400
        assert load_dishes_for_event(event.id) == []

    def test_guest_add_blank_dish_name_400(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token, load_dishes_for_event

        event = get_event_by_management_token(token)
        assert event is not None
        resp = client.post(
            f"/e/{event.slug}/add",
            data={"contributor": "Alice", "dish_name": "\t ", "dish_type": "Main"},
        )
        assert resp.status_code == 400
        assert load_dishes_for_event(event.id) == []

    def test_create_event_blank_name_400_and_nothing_saved(self, client):
        from app.storage import load_events

        resp = client.post(
            "/create",
            data={"name": "   ", "dish_types_input": "Main", "host_name": "Host"},
            follow_redirects=False,
        )
        assert resp.status_code == 400
        assert load_events() == []

    def test_settings_blank_name_400_and_event_still_loads(self, client):
        token = _create_event(client)
        resp = client.post(
            f"/manage/{token}",
            data={"name": "   ", "dish_types_input": "Main", "host_name": "H"},
            follow_redirects=False,
        )
        assert resp.status_code == 400
        page = client.get(f"/manage/{token}")
        assert page.status_code == 200
        assert "Test Potluck" in page.text

    def test_create_event_overlong_host_name_rejected(self, client):
        from app.storage import load_events

        resp = client.post(
            "/create",
            data={
                "name": "Party",
                "dish_types_input": "Main",
                "host_name": "h" * 81,
            },
            follow_redirects=False,
        )
        assert resp.status_code == 422
        assert load_events() == []

    def test_settings_overlong_host_name_rejected_and_event_still_loads(self, client):
        token = _create_event(client)
        resp = client.post(
            f"/manage/{token}",
            data={
                "name": "Party",
                "dish_types_input": "Main",
                "host_name": "h" * 81,
            },
            follow_redirects=False,
        )
        assert resp.status_code == 422
        assert client.get(f"/manage/{token}").status_code == 200


# ── Renaming the host updates house dishes ────────────────────────────────────


class TestHostRename:
    def _setup(self, client):
        from app.storage import get_event_by_management_token

        token = _create_event(client)  # host_name = "The Host"
        event = get_event_by_management_token(token)
        assert event is not None
        client.post(
            f"/manage/{token}/host-items",
            data={"dish_name": "Turkey", "dish_type": "Main"},
        )
        client.post(
            f"/e/{event.slug}/add",
            data={"contributor": "Alice", "dish_name": "Pasta", "dish_type": "Main"},
        )
        return token, event

    def _rename(self, client, token, host_name):
        return client.post(
            f"/manage/{token}",
            data={
                "name": "Test Potluck",
                "dish_types_input": "Main\nSide\nDessert",
                "host_name": host_name,
                "is_active": "1",
            },
            follow_redirects=False,
        )

    def test_rename_updates_house_dishes_only(self, client):
        from app.storage import load_dishes_for_event

        token, event = self._setup(client)
        assert self._rename(client, token, "The Smokehouse").status_code == 303
        dishes = {d.dish_name: d for d in load_dishes_for_event(event.id)}
        assert dishes["Turkey"].contributor == "The Smokehouse"
        assert dishes["Pasta"].contributor == "Alice"

    def test_blank_host_name_falls_back_and_updates_house_dishes(self, client):
        from app.storage import load_dishes_for_event

        token, event = self._setup(client)
        self._rename(client, token, "   ")
        dishes = {d.dish_name: d for d in load_dishes_for_event(event.id)}
        assert dishes["Turkey"].contributor == "The House"

    def test_rename_does_not_touch_other_events(self, client):
        from app.storage import get_event_by_management_token, load_dishes_for_event

        token, _event = self._setup(client)
        other_token = _create_event(client, name="Other Party")
        other = get_event_by_management_token(other_token)
        assert other is not None
        client.post(
            f"/manage/{other_token}/host-items",
            data={"dish_name": "Ham", "dish_type": "Main"},
        )
        self._rename(client, token, "The Smokehouse")
        assert load_dishes_for_event(other.id)[0].contributor == "The Host"

    def test_same_name_is_a_noop(self, client):
        from app.storage import load_dishes_for_event

        token, event = self._setup(client)
        before = [d.model_dump() for d in load_dishes_for_event(event.id)]
        self._rename(client, token, "The Host")
        assert [d.model_dump() for d in load_dishes_for_event(event.id)] == before


# ── Error presentation ────────────────────────────────────────────────────────

BROWSER = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


class TestErrorPages:
    def _bad_host_item(self, client, token, headers=None):
        return client.post(
            f"/manage/{token}/host-items",
            data={"dish_name": "   ", "dish_type": "Side"},
            headers=headers or {},
        )

    def test_browser_gets_html_with_status_and_message(self, client):
        token = _create_event(client)
        resp = self._bad_host_item(client, token, BROWSER)
        assert resp.status_code == 400
        assert resp.headers["content-type"].startswith("text/html")
        assert "Dish name is required" in resp.text
        assert 'href="http://testserver/"' in resp.text

    def test_default_accept_keeps_json(self, client):
        token = _create_event(client)
        resp = self._bad_host_item(client, token)
        assert resp.status_code == 400
        assert resp.json() == {"detail": "Dish name is required"}

    def test_explicit_json_accept_keeps_json(self, client):
        resp = client.get("/e/no-such-event", headers={"Accept": "application/json"})
        assert resp.status_code == 404
        assert "detail" in resp.json()

    def test_json_listed_before_html_stays_json(self, client):
        resp = client.get(
            "/e/no-such-event",
            headers={"Accept": "application/json, text/html;q=0.5"},
        )
        assert resp.status_code == 404
        assert resp.headers["content-type"].startswith("application/json")

    def test_browser_404_is_html(self, client):
        resp = client.get("/e/no-such-event", headers=BROWSER)
        assert resp.status_code == 404
        assert resp.headers["content-type"].startswith("text/html")

    def test_message_markup_is_escaped(self, client):
        from fastapi import HTTPException

        from app.main import app

        @app.get("/_test_boom")
        def _boom():
            raise HTTPException(status_code=400, detail="<script>alert(1)</script>")

        try:
            resp = client.get("/_test_boom", headers=BROWSER)
        finally:
            app.router.routes[:] = [
                r for r in app.router.routes if getattr(r, "path", "") != "/_test_boom"
            ]
        assert resp.status_code == 400
        assert "<script>alert(1)</script>" not in resp.text
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in resp.text

    def test_browser_validation_error_is_html_422(self, client):
        resp = client.post(
            "/create",
            data={"name": "P", "dish_types_input": "Main", "host_name": "h" * 81},
            headers=BROWSER,
        )
        assert resp.status_code == 422
        assert resp.headers["content-type"].startswith("text/html")
        assert "host_name" in resp.text

    def test_validation_error_default_accept_keeps_json(self, client):
        resp = client.post(
            "/create",
            data={"name": "P", "dish_types_input": "Main", "host_name": "h" * 81},
        )
        assert resp.status_code == 422
        assert isinstance(resp.json()["detail"], list)


class TestManageFlash:
    def test_flash_messages_render_escaped(self, client):
        token = _create_event(client)
        resp = client.get(
            f"/manage/{token}",
            params={"flash_success": "Saved", "flash_error": "<b>bad</b>"},
        )
        assert resp.status_code == 200
        assert "Saved" in resp.text
        assert "<b>bad</b>" not in resp.text
        assert "&lt;b&gt;bad&lt;/b&gt;" in resp.text

    def test_no_flash_markup_without_params(self, client):
        token = _create_event(client)
        assert 'data-flash="' not in client.get(f"/manage/{token}").text
