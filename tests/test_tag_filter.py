"""Guest Board tag filters: hide allergen warnings, show-only dietary tags."""

import re

import pytest

from app.models import DishEntry
from app.storage import add_dish, get_event_by_management_token, load_tags


def _tag(name):
    return next(t for t in load_tags() if t.name == name)


@pytest.fixture()
def board(client):
    resp = client.post(
        "/create",
        data={
            "name": "Tag Potluck",
            "dish_types_input": "Main\nSide\nDessert",
            "host_name": "The Host",
        },
        follow_redirects=False,
    )
    event = get_event_by_management_token(
        resp.headers["location"].split("/manage/")[1].split("?")[0]
    )
    peanuts = _tag("Contains peanuts")
    dairy = _tag("Contains dairy")
    vegan = _tag("Vegan")
    halal = _tag("Halal")
    for contributor, name, tags in [
        ("Ann", "Satay Skewers", [peanuts, halal]),
        ("Ben", "Mac and Cheese", [dairy]),
        ("Cat", "Lentil Salad", [vegan]),
        ("Dan", "Fruit Bowl", [vegan, halal]),
        ("Eve", "Mystery Casserole", []),
    ]:
        add_dish(
            DishEntry(
                event_id=event.id,
                contributor=contributor,
                dish_name=name,
                dish_type="Main",
                tag_ids=[t.id for t in tags],
            )
        )
    add_dish(
        DishEntry(
            event_id=event.id,
            contributor="The Host",
            dish_name="House Peanut Brittle",
            dish_type="Dessert",
            tag_ids=[peanuts.id],
            is_host_item=True,
        )
    )
    return {
        "slug": event.slug,
        "peanuts": peanuts.id,
        "dairy": dairy.id,
        "vegan": vegan.id,
        "halal": halal.id,
    }


GUESTS = {
    "Satay Skewers",
    "Mac and Cheese",
    "Lentil Salad",
    "Fruit Bowl",
    "Mystery Casserole",
}
PARTIALS = ("cards/grid", "table/rows")


def _shown(html):
    return {name for name in GUESTS if name in html}


@pytest.mark.parametrize("path", PARTIALS)
def test_hide_excludes_dishes_with_allergen(client, board, path):
    html = client.get(f"/e/{board['slug']}/{path}?hide={board['peanuts']}").text
    assert _shown(html) == GUESTS - {"Satay Skewers"}


@pytest.mark.parametrize("path", PARTIALS)
def test_multiple_hides_exclude_any_match(client, board, path):
    url = f"/e/{board['slug']}/{path}?hide={board['peanuts']}&hide={board['dairy']}"
    assert _shown(client.get(url).text) == GUESTS - {"Satay Skewers", "Mac and Cheese"}


@pytest.mark.parametrize("path", PARTIALS)
def test_only_requires_every_selected_dietary_tag(client, board, path):
    base = f"/e/{board['slug']}/{path}"
    assert _shown(client.get(f"{base}?only={board['vegan']}").text) == {
        "Lentil Salad",
        "Fruit Bowl",
    }
    both = client.get(f"{base}?only={board['vegan']}&only={board['halal']}").text
    assert _shown(both) == {"Fruit Bowl"}


def test_filters_combine_with_search_and_sort(client, board):
    url = (
        f"/e/{board['slug']}/table/rows?search=a&sort=name"
        f"&hide={board['dairy']}&only={board['halal']}"
    )
    html = client.get(url).text
    assert _shown(html) == {"Satay Skewers", "Fruit Bowl"}
    assert html.index("Fruit Bowl") < html.index("Satay Skewers")


def test_wrong_category_and_junk_ids_are_ignored(client, board):
    # A dietary tag can't be used to hide, an allergen can't be required,
    # and garbage values don't 422.
    url = (
        f"/e/{board['slug']}/cards/grid?hide={board['vegan']}"
        f"&only={board['peanuts']}&hide=abc&only=999999"
    )
    resp = client.get(url)
    assert resp.status_code == 200
    assert _shown(resp.text) == GUESTS


def test_empty_result_mentions_filters(client, board):
    html = client.get(f"/e/{board['slug']}/cards/grid?search=zzz").text
    assert "No dishes match this search yet." in html
    html = client.get(
        f"/e/{board['slug']}/table/rows?only={board['halal']}&search=lentil"
    ).text
    assert "No dishes match these filters yet." in html


def test_full_page_offers_only_used_tags(client, board):
    html = client.get(f"/e/{board['slug']}").text
    assert "Hide dishes containing" in html
    assert "Show only dishes tagged" in html
    assert f'id="filter-hide-{board["peanuts"]}"' in html
    assert f'id="filter-hide-{board["dairy"]}"' in html
    assert f'id="filter-only-{board["vegan"]}"' in html
    # Tags no dish carries are not offered.
    assert f'id="filter-hide-{_tag("Contains sesame").id}"' not in html
    # Dietary tags never appear as hide chips and vice versa.
    assert f'id="filter-hide-{board["vegan"]}"' not in html
    assert f'id="filter-only-{board["peanuts"]}"' not in html


def test_no_free_of_wording(client, board):
    html = client.get(f"/e/{board['slug']}?hide={board['peanuts']}").text.lower()
    assert re.search(r"\b\w+[- ]free\b", html) is None


def test_full_page_applies_filters_and_keeps_them_checked(client, board):
    html = client.get(
        f"/e/{board['slug']}?view=table&hide={board['peanuts']}&only={board['halal']}"
    ).text
    assert "Fruit Bowl" in html
    assert "Satay Skewers" not in html
    assert re.search(
        rf'value="{board["peanuts"]}"\s+id="filter-hide-[^"]+"[^>]*checked', html
    )
    assert re.search(
        rf'value="{board["halal"]}"\s+id="filter-only-[^"]+"[^>]*checked', html
    )
    # Cards/Table toggle links carry the active filters.
    assert (
        f"?view=cards&sort=type&hide={board['peanuts']}&only={board['halal']}" in html
    )


def test_host_dish_always_shown_but_flagged(client, board):
    plain = client.get(f"/e/{board['slug']}").text
    assert "House Peanut Brittle" in plain
    assert "border-primary-subtle host-card-flagged" not in plain

    html = client.get(f"/e/{board['slug']}?hide={board['peanuts']}").text
    assert "House Peanut Brittle" in html
    assert "border-primary-subtle host-card-flagged" in html
    flag = re.search(r"data-host-flag-names>([^<]*)<", html)
    assert flag and flag.group(1) == "Contains peanuts"


def test_filter_control_hidden_without_filterable_tags(client):
    resp = client.post(
        "/create",
        data={"name": "Plain", "dish_types_input": "Main", "host_name": "H"},
        follow_redirects=False,
    )
    event = get_event_by_management_token(
        resp.headers["location"].split("/manage/")[1].split("?")[0]
    )
    add_dish(
        DishEntry(
            event_id=event.id,
            contributor="Zed",
            dish_name="Plain Rice",
            dish_type="Main",
            tag_ids=[_tag("Spicy").id]
            if any(t.name == "Spicy" for t in load_tags())
            else [],
        )
    )
    html = client.get(f"/e/{event.slug}").text
    assert "Plain Rice" in html
    assert 'class="tag-filter' not in html
