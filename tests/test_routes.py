"""Integration tests for the FastAPI routes via TestClient."""

import pytest

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
