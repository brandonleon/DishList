"""Integration tests for the FastAPI routes via TestClient."""

import pytest

from app.storage import create_event, load_tags, get_tag_counts


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


# ── Admin reload endpoint ─────────────────────────────────────────────────────


class TestAdminReloadEndpoint:
    def _enable_admin(self, app_state):
        from app.config import AppConfig, save_config
        from app.main import app

        cfg = AppConfig(web_admin_enabled=True, admin_networks=["127.0.0.1/32"])
        save_config(cfg)
        app.state.config = cfg

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

        # Change config on disk without touching app.state
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
