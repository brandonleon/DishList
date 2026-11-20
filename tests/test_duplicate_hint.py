"""Duplicate-dish nudge: similarity matching and the /add/similar htmx partial."""

import pytest

from app.main import _dish_name_similarity, _dish_name_tokens, _similar_dishes
from app.models import DishEntry
from app.storage import get_event_by_management_token


def _dish(name, contributor="Guest", dish_type="Main", is_host_item=False):
    return DishEntry(
        contributor=contributor,
        dish_name=name,
        dish_type=dish_type,
        is_host_item=is_host_item,
    )


# ── Pure matching ──────────────────────────────────────────────────────────────


class TestNormalize:
    def test_casefold_punctuation_and_filler(self):
        assert _dish_name_tokens("Mac & Cheese!") == ["mac", "cheese"]
        assert _dish_name_tokens("mac n' cheese") == ["mac", "cheese"]

    def test_simple_plural(self):
        assert _dish_name_tokens("Brownies") == ["brownie"]
        assert _dish_name_tokens("Peas") == ["pea"]
        assert _dish_name_tokens("Glass") == ["glass"]  # "ss" kept
        assert _dish_name_tokens("Gas") == ["gas"]  # too short to strip

    def test_empty(self):
        assert _dish_name_tokens("  &  ") == []


class TestSimilarity:
    @pytest.mark.parametrize(
        "a, b",
        [
            ("mac n cheese", "Mac and Cheese"),
            ("brownie", "Brownies"),
            ("Deviled eggs", "deviled egg"),
            ("potato salad", "Potato Salad!"),
            ("Chocolate chip cookies", "chocolate-chip cookie"),
            ("lasagna", "Lasagne"),
            ("chips", "Chips and salsa"),
        ],
    )
    def test_matches(self, a, b):
        assert _dish_name_similarity(a, b) > 0

    @pytest.mark.parametrize(
        "a, b",
        [
            ("Apple Pie", "Apple Juice"),
            ("Green salad", "Fruit salad"),
            ("salsa", "salad"),
            ("rice", "Chicken pot pie"),
            ("chicken", "Chicken pot pie with peas"),
            ("", "Brownies"),
        ],
    )
    def test_non_matches(self, a, b):
        assert _dish_name_similarity(a, b) == 0

    def test_exact_beats_partial(self):
        assert _dish_name_similarity("chips", "Chips") > _dish_name_similarity(
            "chips", "Chips and salsa"
        )


class TestSimilarDishes:
    def test_short_query_returns_nothing(self):
        assert _similar_dishes([_dish("Pie")], "pi") == []
        assert _similar_dishes([_dish("Pie")], "  p  ") == []

    def test_best_first_and_limited(self):
        dishes = [
            _dish("Chips and salsa"),
            _dish("Chips"),
            _dish("Potato chips"),
            _dish("Tortilla chips"),
            _dish("Brownies"),
        ]
        result = _similar_dishes(dishes, "chips")
        assert len(result) == 3
        assert result[0].dish_name == "Chips"
        assert all("Brownies" != d.dish_name for d in result)

    def test_apple_pie_does_not_match_juice(self):
        dishes = [_dish("Apple Juice"), _dish("Apple pie")]
        assert [d.dish_name for d in _similar_dishes(dishes, "Apple Pie")] == [
            "Apple pie"
        ]


# ── Route ──────────────────────────────────────────────────────────────────────


def _make_event(client, host_name="Grandma June"):
    resp = client.post(
        "/create",
        data={
            "name": "Dup Test",
            "dish_types_input": "Main\nSide\nDessert",
            "host_name": host_name,
        },
        follow_redirects=False,
    )
    token = resp.headers["location"].split("/manage/")[1].split("?")[0]
    event = get_event_by_management_token(token)
    assert event is not None
    return token, event


def _add_guest_dish(client, slug, contributor, dish_name, dish_type="Main", **extra):
    resp = client.post(
        f"/e/{slug}/add",
        data={
            "contributor": contributor,
            "dish_name": dish_name,
            "dish_type": dish_type,
            **extra,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


class TestSimilarRoute:
    def test_unknown_slug_404(self, client):
        assert client.get("/e/nope-xyz/add/similar?dish_name=pie").status_code == 404

    def test_short_or_missing_query_is_empty(self, client):
        _, event = _make_event(client)
        _add_guest_dish(client, event.slug, "Adam", "Pie")
        for url in ("/add/similar", "/add/similar?dish_name=pi"):
            resp = client.get(f"/e/{event.slug}{url}")
            assert resp.status_code == 200
            assert resp.text.strip() == ""

    def test_no_match_is_empty(self, client):
        _, event = _make_event(client)
        _add_guest_dish(client, event.slug, "Adam", "Mac and Cheese")
        resp = client.get(f"/e/{event.slug}/add/similar?dish_name=Apple+pie")
        assert resp.status_code == 200
        assert resp.text.strip() == ""

    def test_guest_match(self, client):
        _, event = _make_event(client)
        _add_guest_dish(client, event.slug, "Adam", "Mac and Cheese", "Side")
        resp = client.get(f"/e/{event.slug}/add/similar?dish_name=mac+n+cheese")
        assert resp.status_code == 200
        assert "Heads up" in resp.text
        assert "Adam is already bringing" in resp.text
        assert "Mac and Cheese" in resp.text
        assert "Side" in resp.text

    def test_host_contribution_labelled(self, client):
        token, event = _make_event(client, host_name="Grandma June")
        client.post(
            f"/manage/{token}/host-items",
            data={"dish_name": "Brownies", "dish_type": "Dessert"},
            follow_redirects=False,
        )
        resp = client.get(f"/e/{event.slug}/add/similar?dish_name=brownie")
        assert "Grandma June (host)" in resp.text
        assert "Brownies" in resp.text

    def test_never_leaks_private_fields(self, client):
        _, event = _make_event(client)
        _add_guest_dish(
            client,
            event.slug,
            "Adam",
            "Mac and Cheese",
            notes="secret family recipe",
            contributor_email="adam@example.com",
        )
        resp = client.get(f"/e/{event.slug}/add/similar?dish_name=mac+and+cheese")
        assert "Adam" in resp.text
        assert "adam@example.com" not in resp.text
        assert "secret family recipe" not in resp.text

    def test_escapes_names(self, client):
        _, event = _make_event(client)
        _add_guest_dish(client, event.slug, "<b>Eve</b>", "<script>x</script> pie")
        resp = client.get(f"/e/{event.slug}/add/similar?dish_name=script+pie")
        assert "<script>" not in resp.text
        assert "&lt;script&gt;" in resp.text

    def test_at_most_three(self, client):
        _, event = _make_event(client)
        for i, name in enumerate(["Chips", "Chips", "Chips", "Chips"]):
            _add_guest_dish(client, event.slug, f"Guest{i}", name)
        resp = client.get(f"/e/{event.slug}/add/similar?dish_name=chips")
        assert resp.text.count("<li>") == 3

    def test_empty_event_is_empty(self, client):
        _, event = _make_event(client)
        resp = client.get(f"/e/{event.slug}/add/similar?dish_name=anything")
        assert resp.status_code == 200
        assert resp.text.strip() == ""


class TestAddFormWiring:
    def test_form_has_htmx_hint_and_keeps_submit_enabled(self, client):
        _, event = _make_event(client)
        html = client.get(f"/e/{event.slug}/add").text
        assert f'hx-get="/e/{event.slug}/add/similar"' in html
        assert 'id="dish-similar"' in html
        assert 'aria-live="polite"' in html
        assert 'hx-params="dish_name"' in html
        # tag auto-detect script still present
        assert "TAG_KEYWORDS" in html
        assert "disabled" not in html.split('type="submit"')[1][:80]
