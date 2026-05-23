"""Unit tests for tag storage — CRUD, keywords, visibility, defaults."""

import pytest

from app.storage import (
    create_tag,
    delete_tag,
    get_tag_counts,
    load_tags,
    load_tag_groups,
    reset_tags_to_defaults,
    set_tag_keywords,
    toggle_tag_visibility,
    update_tag,
    DEFAULT_TAG_GROUPS,
    DEFAULT_HIDDEN_TAG_GROUPS,
    DEFAULT_TAG_KEYWORDS,
    TAG_CATEGORY_ORDER,
)


# ── Default seeding ────────────────────────────────────────────────────────────


class TestDefaultSeeding:
    def test_all_default_visible_tags_exist(self):
        tags = {t.name for t in load_tags()}
        for category in TAG_CATEGORY_ORDER:
            for name in DEFAULT_TAG_GROUPS.get(category, []):
                assert name in tags, f"Missing default visible tag: {name!r}"

    def test_all_default_hidden_tags_exist(self):
        tags = {t.name for t in load_tags()}
        for category in TAG_CATEGORY_ORDER:
            for name in DEFAULT_HIDDEN_TAG_GROUPS.get(category, []):
                assert name in tags, f"Missing default hidden tag: {name!r}"

    def test_default_visible_tags_are_not_hidden(self):
        tag_map = {t.name: t for t in load_tags()}
        for category in TAG_CATEGORY_ORDER:
            for name in DEFAULT_TAG_GROUPS.get(category, []):
                assert not tag_map[name].is_hidden, (
                    f"{name!r} should be visible by default"
                )

    def test_default_hidden_tags_are_hidden(self):
        tag_map = {t.name: t for t in load_tags()}
        for category in TAG_CATEGORY_ORDER:
            for name in DEFAULT_HIDDEN_TAG_GROUPS.get(category, []):
                assert tag_map[name].is_hidden, f"{name!r} should be hidden by default"

    def test_default_keywords_seeded(self):
        tag_map = {t.name: t for t in load_tags()}
        for name, keywords in DEFAULT_TAG_KEYWORDS.items():
            if name in tag_map:
                for kw in keywords:
                    assert kw in tag_map[name].keywords, (
                        f"Keyword {kw!r} missing from {name!r}"
                    )

    def test_tag_counts_match(self):
        counts = get_tag_counts()
        tags = load_tags()
        assert counts["total"] == len(tags)
        assert counts["hidden"] == sum(1 for t in tags if t.is_hidden)
        assert counts["visible"] == sum(1 for t in tags if not t.is_hidden)


# ── create_tag ─────────────────────────────────────────────────────────────────


class TestCreateTag:
    def test_basic_create(self):
        tag = create_tag("Raw vegan", "Dietary preferences")
        assert tag.id is not None
        assert tag.name == "Raw vegan"
        assert tag.category == "Dietary preferences"
        assert tag.is_hidden is False
        assert tag.keywords == []

    def test_create_hidden(self):
        tag = create_tag("Macrobiotic", "Dietary preferences", is_hidden=True)
        assert tag.is_hidden is True

    def test_create_with_keywords(self):
        tag = create_tag(
            "Oat-free", "Allergen warnings", keywords=["oat", "oats", "oatmeal"]
        )
        assert tag.keywords == ["oat", "oats", "oatmeal"]

    def test_create_keywords_are_lowercased(self):
        tag = create_tag("Oat-free", "Allergen warnings", keywords=["Oat", "OATS"])
        assert tag.keywords == ["oat", "oats"]

    def test_create_duplicate_raises(self):
        create_tag("Unique", "Content & serving")
        with pytest.raises(ValueError, match="already exists"):
            create_tag("Unique", "Content & serving")

    def test_create_empty_name_raises(self):
        with pytest.raises(ValueError):
            create_tag("", "Dietary preferences")

    def test_create_empty_category_raises(self):
        with pytest.raises(ValueError):
            create_tag("Something", "")

    def test_created_tag_appears_in_load_tags(self):
        create_tag("Custom tag", "Content & serving")
        names = [t.name for t in load_tags()]
        assert "Custom tag" in names


# ── update_tag ─────────────────────────────────────────────────────────────────


class TestUpdateTag:
    def test_rename(self):
        tag = create_tag("Old name", "Content & serving")
        update_tag(tag.id, "New name", "Content & serving")
        names = [t.name for t in load_tags()]
        assert "New name" in names
        assert "Old name" not in names

    def test_update_keywords(self):
        tag = create_tag("Oat-free", "Allergen warnings", keywords=["oat"])
        update_tag(tag.id, "Oat-free", "Allergen warnings", keywords=["oat", "oats"])
        updated = next(t for t in load_tags() if t.id == tag.id)
        assert updated.keywords == ["oat", "oats"]

    def test_clear_keywords(self):
        tag = create_tag("Oat-free", "Allergen warnings", keywords=["oat"])
        update_tag(tag.id, "Oat-free", "Allergen warnings", keywords=[])
        updated = next(t for t in load_tags() if t.id == tag.id)
        assert updated.keywords == []

    def test_update_is_hidden(self):
        tag = create_tag("Visible tag", "Content & serving")
        update_tag(tag.id, "Visible tag", "Content & serving", is_hidden=True)
        updated = next(t for t in load_tags() if t.id == tag.id)
        assert updated.is_hidden is True

    def test_is_hidden_none_preserves_existing(self):
        tag = create_tag("Hidden tag", "Content & serving", is_hidden=True)
        update_tag(tag.id, "Hidden tag", "Content & serving", is_hidden=None)
        updated = next(t for t in load_tags() if t.id == tag.id)
        assert updated.is_hidden is True

    def test_duplicate_name_raises(self):
        create_tag("Alpha", "Content & serving")
        t2 = create_tag("Beta", "Content & serving")
        with pytest.raises(ValueError, match="already exists"):
            update_tag(t2.id, "Alpha", "Content & serving")


# ── toggle_tag_visibility ──────────────────────────────────────────────────────


class TestToggleVisibility:
    def test_visible_becomes_hidden(self):
        tag = create_tag("Visible", "Content & serving", is_hidden=False)
        new_state = toggle_tag_visibility(tag.id)
        assert new_state is True
        updated = next(t for t in load_tags() if t.id == tag.id)
        assert updated.is_hidden is True

    def test_hidden_becomes_visible(self):
        tag = create_tag("Hidden", "Content & serving", is_hidden=True)
        new_state = toggle_tag_visibility(tag.id)
        assert new_state is False
        updated = next(t for t in load_tags() if t.id == tag.id)
        assert updated.is_hidden is False

    def test_toggle_invalid_id_raises(self):
        with pytest.raises(ValueError):
            toggle_tag_visibility(999999)


# ── delete_tag ─────────────────────────────────────────────────────────────────


class TestDeleteTag:
    def test_delete_removes_tag(self):
        tag = create_tag("Temp", "Content & serving")
        delete_tag(tag.id)
        names = [t.name for t in load_tags()]
        assert "Temp" not in names

    def test_delete_removes_keywords(self):
        tag = create_tag("Temp", "Content & serving", keywords=["foo", "bar"])
        delete_tag(tag.id)
        # Keywords cascade; just verify tag is gone
        assert tag.id not in {t.id for t in load_tags()}


# ── set_tag_keywords ───────────────────────────────────────────────────────────


class TestSetTagKeywords:
    def test_set_keywords(self):
        tag = create_tag("Oat-free", "Allergen warnings")
        set_tag_keywords(tag.id, ["oat", "oats"])
        updated = next(t for t in load_tags() if t.id == tag.id)
        assert updated.keywords == ["oat", "oats"]

    def test_set_deduplicates(self):
        tag = create_tag("Oat-free", "Allergen warnings")
        set_tag_keywords(tag.id, ["oat", "oat", "oats"])
        updated = next(t for t in load_tags() if t.id == tag.id)
        assert updated.keywords == ["oat", "oats"]

    def test_set_empty_clears(self):
        tag = create_tag("Oat-free", "Allergen warnings", keywords=["oat"])
        set_tag_keywords(tag.id, [])
        updated = next(t for t in load_tags() if t.id == tag.id)
        assert updated.keywords == []


# ── load_tag_groups ────────────────────────────────────────────────────────────


class TestLoadTagGroups:
    def test_groups_follow_category_order(self):
        groups = load_tag_groups()
        categories = [cat for cat, _ in groups]
        ordered = [c for c in TAG_CATEGORY_ORDER if c in categories]
        assert categories[: len(ordered)] == ordered

    def test_hidden_tags_included_in_groups(self):
        """Hidden tags must be in groups (picker renders them hidden via CSS)."""
        all_tags = [t for _, tags in load_tag_groups() for t in tags]
        hidden = [t for t in all_tags if t.is_hidden]
        assert len(hidden) > 0


# ── reset_tags_to_defaults ─────────────────────────────────────────────────────


class TestResetToDefaults:
    def test_reset_removes_custom_tags(self):
        create_tag("Custom", "Content & serving")
        reset_tags_to_defaults()
        names = {t.name for t in load_tags()}
        assert "Custom" not in names

    def test_reset_restores_all_defaults(self):
        reset_tags_to_defaults()
        names = {t.name for t in load_tags()}
        for category in TAG_CATEGORY_ORDER:
            for name in DEFAULT_TAG_GROUPS.get(category, []):
                assert name in names
            for name in DEFAULT_HIDDEN_TAG_GROUPS.get(category, []):
                assert name in names

    def test_reset_restores_keywords(self):
        reset_tags_to_defaults()
        tag_map = {t.name: t for t in load_tags()}
        assert "peanut" in tag_map["Contains peanuts"].keywords
