"""Unit tests for event and dish storage."""

from typing import Optional

from app.storage import (
    create_event,
    delete_event,
    get_event_by_management_token,
    get_event_by_slug,
    load_events,
    update_event,
    add_dish,
    delete_dish,
    get_dish,
    load_dishes_for_event,
    create_tag,
    get_tags_by_ids,
)
from app.models import DishEntry, Event


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_event(**kwargs) -> Event:
    return create_event(
        name=kwargs.get("name", "Test Potluck"),
        description=kwargs.get("description", None),
        event_date=kwargs.get("event_date", None),
        host_name=kwargs.get("host_name", "The Host"),
        dish_types=kwargs.get("dish_types", ["Main", "Side", "Dessert"]),
        use_random_slug=kwargs.get("use_random_slug", False),
    )


def _make_dish(event_id: int, **kwargs) -> int:
    return add_dish(DishEntry(
        event_id=event_id,
        contributor=kwargs.get("contributor", "Alice"),
        dish_name=kwargs.get("dish_name", "Pasta"),
        dish_type=kwargs.get("dish_type", "Main"),
    ))


# ── Events ─────────────────────────────────────────────────────────────────────

class TestCreateEvent:
    def test_creates_with_unique_slug(self):
        e1 = _make_event(name="Friendsgiving")
        e2 = _make_event(name="Friendsgiving")
        assert e1.slug != e2.slug

    def test_management_token_unique(self):
        e1 = _make_event()
        e2 = _make_event()
        assert e1.management_token != e2.management_token

    def test_is_active_by_default(self):
        event = _make_event()
        assert event.is_active is True

    def test_random_slug_option(self):
        event = create_event(
            name="Secret", description=None, event_date=None,
            host_name="Host", dish_types=["Main"], use_random_slug=True,
        )
        assert event.slug  # non-empty


class TestGetEvent:
    def test_get_by_slug(self):
        event = _make_event(name="Slug Test")
        fetched = get_event_by_slug(event.slug)
        assert fetched is not None
        assert fetched.id == event.id

    def test_get_by_token(self):
        event = _make_event()
        fetched = get_event_by_management_token(event.management_token)
        assert fetched is not None
        assert fetched.id == event.id

    def test_missing_slug_returns_none(self):
        assert get_event_by_slug("does-not-exist-xyz") is None

    def test_missing_token_returns_none(self):
        assert get_event_by_management_token("notavalidtoken") is None


class TestUpdateEvent:
    def test_update_name(self):
        event = _make_event(name="Old Name")
        update_event(
            event_id=event.id,
            name="New Name",
            description=None,
            event_date=None,
            host_name="Host",
            dish_types=["Main"],
            is_active=True,
        )
        fetched = get_event_by_slug(event.slug)
        assert fetched is not None
        assert fetched.name == "New Name"

    def test_deactivate(self):
        event = _make_event()
        update_event(
            event_id=event.id, name=event.name, description=None,
            event_date=None, host_name=event.host_name,
            dish_types=event.dish_types, is_active=False,
        )
        fetched = get_event_by_slug(event.slug)
        assert fetched is not None
        assert fetched.is_active is False


class TestDeleteEvent:
    def test_delete_removes_event(self):
        event = _make_event()
        delete_event(event.id)
        assert get_event_by_slug(event.slug) is None

    def test_delete_cascades_to_dishes(self):
        event = _make_event()
        dish_id = _make_dish(event.id)
        delete_event(event.id)
        assert get_dish(dish_id) is None


class TestLoadEvents:
    def test_returns_all_events(self):
        e1 = _make_event(name="A")
        e2 = _make_event(name="B")
        ids = {e.id for e in load_events()}
        assert e1.id in ids
        assert e2.id in ids

    def test_newest_first(self):
        _make_event(name="First")
        e2 = _make_event(name="Second")
        events = load_events()
        # e2 has a higher id; id DESC is used as tiebreaker for same-second inserts
        assert events[0].id == e2.id


# ── Dishes ─────────────────────────────────────────────────────────────────────

class TestAddDish:
    def test_add_returns_id(self):
        event = _make_event()
        dish_id = _make_dish(event.id)
        assert isinstance(dish_id, int)

    def test_dish_retrievable(self):
        event = _make_event()
        dish_id = _make_dish(event.id, dish_name="Lasagne", contributor="Bob")
        dish = get_dish(dish_id)
        assert dish is not None
        assert dish.dish_name == "Lasagne"
        assert dish.contributor == "Bob"

    def test_dish_with_tags(self):
        event = _make_event()
        tag = create_tag("Vegan test", "Dietary preferences")
        dish_id = add_dish(DishEntry(
            event_id=event.id,
            contributor="Alice",
            dish_name="Salad",
            dish_type="Side",
            tag_ids=[tag.id],
        ))
        dish = get_dish(dish_id)
        assert dish is not None
        assert tag.id in dish.tag_ids

    def test_host_item_flag(self):
        event = _make_event()
        dish_id = add_dish(DishEntry(
            event_id=event.id,
            contributor="Host",
            dish_name="Welcome snacks",
            dish_type="Main",
            is_host_item=True,
        ))
        dish = get_dish(dish_id)
        assert dish is not None
        assert dish.is_host_item is True


class TestLoadDishesForEvent:
    def test_host_items_first(self):
        event = _make_event()
        add_dish(DishEntry(event_id=event.id, contributor="Guest", dish_name="Salad", dish_type="Side"))
        add_dish(DishEntry(event_id=event.id, contributor="Host", dish_name="Snacks", dish_type="Main", is_host_item=True))
        dishes = load_dishes_for_event(event.id)
        assert dishes[0].is_host_item is True

    def test_only_returns_own_event_dishes(self):
        e1 = _make_event(name="Event 1")
        e2 = _make_event(name="Event 2")
        _make_dish(e1.id, dish_name="E1 dish")
        _make_dish(e2.id, dish_name="E2 dish")
        dishes = load_dishes_for_event(e1.id)
        assert all(d.event_id == e1.id for d in dishes)


class TestDeleteDish:
    def test_delete_removes_dish(self):
        event = _make_event()
        dish_id = _make_dish(event.id)
        delete_dish(dish_id)
        assert get_dish(dish_id) is None


class TestGetTagsByIds:
    def test_returns_correct_tags(self):
        t1 = create_tag("T1", "Content & serving")
        t2 = create_tag("T2", "Content & serving")
        fetched = get_tags_by_ids([t1.id, t2.id])
        ids = {t.id for t in fetched}
        assert t1.id in ids
        assert t2.id in ids

    def test_empty_input(self):
        assert get_tags_by_ids([]) == []

    def test_includes_is_hidden(self):
        tag = create_tag("Hidden test", "Content & serving", is_hidden=True)
        fetched = get_tags_by_ids([tag.id])
        assert fetched[0].is_hidden is True
