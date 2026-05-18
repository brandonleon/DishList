"""Integration tests for the FastAPI routes via TestClient."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.config import AppConfig
from app.storage import create_event, load_tags, get_tag_counts


# ── Helpers ────────────────────────────────────────────────────────────────────

def _create_event(client, name="Test Potluck", dish_types="Main\nSide\nDessert"):
    resp = client.post("/create", data={
        "name": name,
        "dish_types_input": dish_types,
        "host_name": "The Host",
    }, follow_redirects=False)
    assert resp.status_code == 303
    token = resp.headers["location"].split("/manage/")[1]
    return token


# ── Landing & create ───────────────────────────────────────────────────────────

class TestPublicRoutes:
    def test_landing_200(self, client):
        assert client.get("/").status_code == 200

    def test_create_form_200(self, client):
        assert client.get("/create").status_code == 200

    def test_create_event_redirects(self, client):
        resp = client.post("/create", data={
            "name": "Friendsgiving",
            "dish_types_input": "Main\nSide",
            "host_name": "Host",
        }, follow_redirects=False)
        assert resp.status_code == 303
        assert "/manage/" in resp.headers["location"]

    def test_create_event_missing_dish_types_400(self, client):
        # FastAPI returns 422 for missing required fields, 400 for app-level validation
        resp = client.post("/create", data={
            "name": "Bad Event",
            "dish_types_input": "   ",  # whitespace only → app strips to empty list
            "host_name": "Host",
        })
        assert resp.status_code == 400


# ── Event pages ────────────────────────────────────────────────────────────────

class TestEventRoutes:
    def test_event_home_200(self, client):
        token = _create_event(client)
        slug = client.get(f"/manage/{token}", follow_redirects=True).url.path
        # Derive slug from manage page
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
        resp = client.get(f"/e/{event.slug}")
        assert resp.status_code == 200

    def test_event_home_unknown_slug_404(self, client):
        assert client.get("/e/does-not-exist-xyz").status_code == 404

    def test_add_dish_form_200(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
        resp = client.get(f"/e/{event.slug}/add")
        assert resp.status_code == 200

    def test_add_dish_form_contains_hidden_hint(self, client):
        """Hidden tags should be absent from initial rendered HTML (d-none)."""
        token = _create_event(client)
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
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
        resp = client.post(f"/e/{event.slug}/add", data={
            "contributor": "Alice",
            "dish_name": "Pasta",
            "dish_type": "Main",
        }, follow_redirects=False)
        assert resp.status_code == 303

    def test_submit_unknown_dish_type_400(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
        resp = client.post(f"/e/{event.slug}/add", data={
            "contributor": "Alice",
            "dish_name": "Pasta",
            "dish_type": "NotARealType",
        })
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
        resp = client.post(f"/manage/{token}", data={
            "name": "Updated Name",
            "dish_types_input": "Main\nSide",
            "host_name": "New Host",
        }, follow_redirects=False)
        assert resp.status_code == 303
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
        assert event.name == "Updated Name"


# ── Tag keyword JSON in add form ───────────────────────────────────────────────

class TestTagKeywordsInAddForm:
    def test_tag_keywords_json_present(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
        html = client.get(f"/e/{event.slug}/add").text
        assert "const TAG_KEYWORDS" in html

    def test_hidden_tag_keywords_included(self, client):
        """Hidden tags' keywords must be in TAG_KEYWORDS for auto-detection."""
        import json, re
        token = _create_event(client)
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
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
    def test_dietary_badge_class_plant_based(self):
        from app.main import _dietary_badge_class
        assert "success" in _dietary_badge_class("Vegan")

    def test_dietary_badge_class_contains(self):
        from app.main import _dietary_badge_class
        assert "warning" in _dietary_badge_class("Contains peanuts")

    def test_dietary_badge_class_other(self):
        from app.main import _dietary_badge_class
        assert "secondary" in _dietary_badge_class("Spicy")

    def test_format_dish_timestamp_string_input(self):
        from app.main import _format_dish_timestamp
        assert "Jan" in _format_dish_timestamp("2024-01-15T12:30:00")

    def test_format_dish_timestamp_naive_datetime(self):
        from app.main import _format_dish_timestamp
        assert "Jun" in _format_dish_timestamp(datetime(2024, 6, 1, 12, 0, 0))

    def test_filter_dishes_empty_query_returns_all(self):
        from app.main import _filter_dishes
        from app.models import DishEntry
        dishes = [DishEntry(event_id=1, contributor="A", dish_name="Pasta", dish_type="Main")]
        assert _filter_dishes(dishes, "") == dishes

    def test_filter_dishes_matches_name(self):
        from app.main import _filter_dishes
        from app.models import DishEntry
        dishes = [
            DishEntry(event_id=1, contributor="Alice", dish_name="Pasta", dish_type="Main"),
            DishEntry(event_id=1, contributor="Bob", dish_name="Salad", dish_type="Side"),
        ]
        result = _filter_dishes(dishes, "pasta")
        assert len(result) == 1 and result[0].dish_name == "Pasta"

    def test_is_ip_allowed_matching_network(self):
        from app.main import _is_ip_allowed
        req = MagicMock()
        req.client.host = "127.0.0.1"
        cfg = AppConfig(web_admin_enabled=True, admin_networks=["127.0.0.1/32"])
        assert _is_ip_allowed(req, cfg) is True

    def test_is_ip_allowed_rejected_ip(self):
        from app.main import _is_ip_allowed
        req = MagicMock()
        req.client.host = "10.0.0.1"
        cfg = AppConfig(web_admin_enabled=True, admin_networks=["192.168.1.0/24"])
        assert _is_ip_allowed(req, cfg) is False

    def test_is_ip_allowed_invalid_host(self):
        from app.main import _is_ip_allowed
        req = MagicMock()
        req.client.host = "not-an-ip"
        cfg = AppConfig(web_admin_enabled=True, admin_networks=["127.0.0.1/32"])
        assert _is_ip_allowed(req, cfg) is False

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
        resp = client.post("/create", data={
            "name": "Date Party",
            "dish_types_input": "Main",
            "host_name": "Host",
            "event_date": "2025-12-25",
        }, follow_redirects=False)
        assert resp.status_code == 303

    def test_create_with_invalid_date_400(self, client):
        resp = client.post("/create", data={
            "name": "Bad Date Party",
            "dish_types_input": "Main",
            "host_name": "Host",
            "event_date": "not-a-date",
        })
        assert resp.status_code == 400

    def test_create_with_host_items(self, client):
        resp = client.post("/create", data={
            "name": "Host Items Party",
            "dish_types_input": "Main\nSide",
            "host_name": "Host",
            "host_item_names": "Bread",
            "host_item_types": "InvalidType",  # not in dish_types → falls back to first
            "host_item_notes": "Fresh",
        }, follow_redirects=False)
        assert resp.status_code == 303

    def test_create_skips_blank_host_item(self, client):
        resp = client.post("/create", data={
            "name": "Party",
            "dish_types_input": "Main",
            "host_name": "Host",
            "host_item_names": "   ",  # blank → skipped
            "host_item_types": "Main",
            "host_item_notes": "",
        }, follow_redirects=False)
        assert resp.status_code == 303


# ── Event view modes & inactive event ─────────────────────────────────────────

class TestEventViewModes:
    def test_invalid_view_mode_defaults_to_cards(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
        resp = client.get(f"/e/{event.slug}?view=bogus")
        assert resp.status_code == 200

    def test_inactive_event_add_form_403(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
        # Deactivate via manage POST
        client.post(f"/manage/{token}", data={
            "name": event.name,
            "dish_types_input": "\n".join(event.dish_types),
            "host_name": event.host_name or "Host",
        })  # is_active not included → False
        resp = client.get(f"/e/{event.slug}/add")
        assert resp.status_code == 403

    def test_inactive_event_submission_403(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
        client.post(f"/manage/{token}", data={
            "name": event.name,
            "dish_types_input": "\n".join(event.dish_types),
            "host_name": event.host_name or "Host",
        })
        resp = client.post(f"/e/{event.slug}/add", data={
            "contributor": "Alice",
            "dish_name": "Pasta",
            "dish_type": "Main",
        })
        assert resp.status_code == 403

    def test_submit_unknown_tag_id_400(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
        resp = client.post(f"/e/{event.slug}/add", data={
            "contributor": "Alice",
            "dish_name": "Pasta",
            "dish_type": "Main",
            "dietary_tags": "999999",  # non-existent tag ID
        })
        assert resp.status_code == 400


# ── Partial routes ─────────────────────────────────────────────────────────────

class TestPartialRoutes:
    def test_table_rows_partial_200(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
        assert client.get(f"/e/{event.slug}/table/rows").status_code == 200

    def test_card_grid_partial_200(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
        assert client.get(f"/e/{event.slug}/cards/grid").status_code == 200

    def test_table_rows_with_search(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
        assert client.get(f"/e/{event.slug}/table/rows?search=pasta").status_code == 200


# ── Manage sub-routes ──────────────────────────────────────────────────────────

class TestManageSubRoutes:
    def test_add_host_item_redirects(self, client):
        token = _create_event(client)
        resp = client.post(f"/manage/{token}/host-items", data={
            "dish_name": "Host Bread",
            "dish_type": "Side",
        }, follow_redirects=False)
        assert resp.status_code == 303

    def test_add_host_item_invalid_type_400(self, client):
        token = _create_event(client)
        resp = client.post(f"/manage/{token}/host-items", data={
            "dish_name": "Thing",
            "dish_type": "NotAType",
        })
        assert resp.status_code == 400

    def test_delete_host_item_redirects(self, client):
        token = _create_event(client)
        client.post(f"/manage/{token}/host-items", data={
            "dish_name": "Host Bread",
            "dish_type": "Side",
        })
        from app.storage import get_event_by_management_token, load_dishes_for_event
        event = get_event_by_management_token(token)
        host_dish = next(d for d in load_dishes_for_event(event.id) if d.dish_name == "Host Bread")
        resp = client.post(f"/manage/{token}/host-items/{host_dish.id}/delete", follow_redirects=False)
        assert resp.status_code == 303

    def test_manage_edit_dish_form_200(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token, load_dishes_for_event
        event = get_event_by_management_token(token)
        client.post(f"/e/{event.slug}/add", data={
            "contributor": "Alice", "dish_name": "Pasta", "dish_type": "Main",
        })
        guest_dish = next(d for d in load_dishes_for_event(event.id) if not d.is_host_item)
        assert client.get(f"/manage/{token}/dishes/{guest_dish.id}").status_code == 200

    def test_manage_edit_dish_submit_redirects(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token, load_dishes_for_event
        event = get_event_by_management_token(token)
        client.post(f"/e/{event.slug}/add", data={
            "contributor": "Alice", "dish_name": "Pasta", "dish_type": "Main",
        })
        guest_dish = next(d for d in load_dishes_for_event(event.id) if not d.is_host_item)
        resp = client.post(f"/manage/{token}/dishes/{guest_dish.id}", data={
            "contributor": "Alice Updated",
            "dish_name": "Updated Pasta",
            "dish_type": "Main",
        }, follow_redirects=False)
        assert resp.status_code == 303

    def test_manage_edit_dish_submit_invalid_type_400(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token, load_dishes_for_event
        event = get_event_by_management_token(token)
        client.post(f"/e/{event.slug}/add", data={
            "contributor": "Alice", "dish_name": "Pasta", "dish_type": "Main",
        })
        guest_dish = next(d for d in load_dishes_for_event(event.id) if not d.is_host_item)
        resp = client.post(f"/manage/{token}/dishes/{guest_dish.id}", data={
            "contributor": "Alice",
            "dish_name": "Pasta",
            "dish_type": "NotAType",
        })
        assert resp.status_code == 400

    def test_manage_delete_dish_redirects(self, client):
        token = _create_event(client)
        from app.storage import get_event_by_management_token, load_dishes_for_event
        event = get_event_by_management_token(token)
        client.post(f"/e/{event.slug}/add", data={
            "contributor": "Alice", "dish_name": "Pasta", "dish_type": "Main",
        })
        guest_dish = next(d for d in load_dishes_for_event(event.id) if not d.is_host_item)
        resp = client.post(f"/manage/{token}/dishes/{guest_dish.id}/delete", follow_redirects=False)
        assert resp.status_code == 303

    def test_update_event_settings_empty_dish_types_400(self, client):
        token = _create_event(client)
        resp = client.post(f"/manage/{token}", data={
            "name": "Event",
            "dish_types_input": "   ",
            "host_name": "Host",
        })
        assert resp.status_code == 400

    def test_update_event_settings_invalid_date_400(self, client):
        token = _create_event(client)
        resp = client.post(f"/manage/{token}", data={
            "name": "Event",
            "dish_types_input": "Main",
            "host_name": "Host",
            "event_date": "not-a-date",
        })
        assert resp.status_code == 400


# ── Admin routes ───────────────────────────────────────────────────────────────

class TestAdminRoutes:
    def test_admin_page_200(self, admin_client):
        assert admin_client.get("/pantry-admin").status_code == 200

    def test_admin_tags_page_200(self, admin_client):
        assert admin_client.get("/pantry-admin/tags").status_code == 200

    def test_update_admin_settings_redirects(self, admin_client):
        resp = admin_client.post("/pantry-admin", data={
            "dish_types_input": "Main\nSide\nDessert",
            "admin_networks_input": "127.0.0.1/32",
        }, follow_redirects=False)
        assert resp.status_code == 303

    def test_update_admin_settings_empty_dish_types_400(self, admin_client):
        resp = admin_client.post("/pantry-admin", data={
            "dish_types_input": "   ",
            "admin_networks_input": "127.0.0.1/32",
        })
        assert resp.status_code == 400

    def test_update_admin_settings_empty_networks_400(self, admin_client):
        resp = admin_client.post("/pantry-admin", data={
            "dish_types_input": "Main",
            "admin_networks_input": "  ",
        })
        assert resp.status_code == 400

    def test_add_tag_action_success(self, admin_client):
        resp = admin_client.post("/pantry-admin/tags", data={
            "tag_name": "Brand New Tag",
            "tag_category": "Dietary preferences",
        }, follow_redirects=False)
        assert resp.status_code == 303
        assert "tag_success" in resp.headers["location"]

    def test_add_tag_action_duplicate_redirects_with_error(self, admin_client):
        # "Vegan" already exists in defaults
        resp = admin_client.post("/pantry-admin/tags", data={
            "tag_name": "Vegan",
            "tag_category": "Dietary preferences",
        }, follow_redirects=False)
        assert resp.status_code == 303
        assert "tag_error" in resp.headers["location"]

    def test_update_tag_action_success(self, admin_client):
        vegan = next(t for t in load_tags() if t.name == "Vegan")
        resp = admin_client.post(f"/pantry-admin/tags/{vegan.id}", data={
            "name": "Vegan",
            "category": "Dietary preferences",
        }, follow_redirects=False)
        assert resp.status_code == 303

    def test_update_tag_action_conflict_redirects_with_error(self, admin_client):
        tags = load_tags()
        vegan = next(t for t in tags if t.name == "Vegan")
        vegetarian = next(t for t in tags if t.name == "Vegetarian")
        # Try to rename vegan to vegetarian (conflict)
        resp = admin_client.post(f"/pantry-admin/tags/{vegan.id}", data={
            "name": "Vegetarian",
            "category": "Dietary preferences",
        }, follow_redirects=False)
        assert resp.status_code == 303
        assert "tag_error" in resp.headers["location"]

    def test_reset_tags_action_redirects(self, admin_client):
        resp = admin_client.post("/pantry-admin/tags/reset", follow_redirects=False)
        assert resp.status_code == 303

    def test_delete_tag_action_redirects(self, admin_client):
        from app.storage import create_tag
        tag = create_tag("Temp Tag", "Content & serving")
        resp = admin_client.post(f"/pantry-admin/tags/{tag.id}/delete", follow_redirects=False)
        assert resp.status_code == 303

    def test_toggle_tag_visibility_action_redirects(self, admin_client):
        tag = load_tags()[0]
        resp = admin_client.post(f"/pantry-admin/tags/{tag.id}/visibility", follow_redirects=False)
        assert resp.status_code == 303

    def test_admin_delete_event_redirects(self, admin_client):
        token = _create_event(admin_client)
        from app.storage import get_event_by_management_token
        event = get_event_by_management_token(token)
        resp = admin_client.post(f"/pantry-admin/events/{event.id}/delete", follow_redirects=False)
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
