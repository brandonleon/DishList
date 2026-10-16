"""Baseline schema and default data.

Creates every table DishList 0.6.0 needs and seeds the default dish types,
admin config and dietary tag library. The seed values are frozen here on
purpose: later changes to the defaults in ``app/storage.py`` must not rewrite
what this revision did.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

DEFAULT_DISH_TYPES = ["Main Dish", "Side Dish", "Dessert", "Beverage"]
DEFAULT_ADMIN_NETWORKS = ["127.0.0.1/32"]

# (name, category, position, is_hidden, keywords)
DEFAULT_TAGS = [
    ("Contains peanuts", "Allergen warnings", 0, False, ["peanut", "groundnut"]),
    (
        "Contains tree nuts",
        "Allergen warnings",
        1,
        False,
        [
            "nut",
            "nuts",
            "almond",
            "cashew",
            "walnut",
            "pecan",
            "hazelnut",
            "pistachio",
            "macadamia",
        ],
    ),
    (
        "Contains dairy",
        "Allergen warnings",
        2,
        False,
        ["dairy", "milk", "cream", "cheese", "butter", "yogurt", "yoghurt", "whey"],
    ),
    ("Contains eggs", "Allergen warnings", 3, False, ["egg", "eggs"]),
    (
        "Contains gluten / wheat",
        "Allergen warnings",
        4,
        False,
        ["gluten", "wheat", "flour"],
    ),
    ("Contains soy", "Allergen warnings", 5, False, ["soy", "tofu", "edamame"]),
    ("Contains sesame", "Allergen warnings", 6, False, ["sesame", "tahini"]),
    (
        "Contains shellfish",
        "Allergen warnings",
        7,
        False,
        [
            "shellfish",
            "shrimp",
            "prawn",
            "crab",
            "lobster",
            "scallop",
            "mussel",
            "oyster",
            "clam",
        ],
    ),
    (
        "Contains fish",
        "Allergen warnings",
        8,
        False,
        [
            "fish",
            "salmon",
            "tuna",
            "cod",
            "anchovy",
            "anchovies",
            "herring",
            "tilapia",
            "trout",
        ],
    ),
    (
        "Contains coconut",
        "Allergen warnings",
        9,
        False,
        [
            "coconut",
            "coconut milk",
            "coconut cream",
            "coconut oil",
            "desiccated coconut",
            "shredded coconut",
        ],
    ),
    (
        "Contains corn",
        "Allergen warnings",
        10,
        False,
        [
            "corn",
            "cornstarch",
            "cornmeal",
            "polenta",
            "grits",
            "corn syrup",
            "sweet corn",
        ],
    ),
    (
        "Contains mustard",
        "Allergen warnings",
        11,
        False,
        ["mustard", "dijon", "whole grain mustard"],
    ),
    ("Vegan", "Dietary preferences", 0, False, ["vegan"]),
    ("Vegetarian", "Dietary preferences", 1, False, ["vegetarian", "veggie"]),
    ("Pescatarian", "Dietary preferences", 2, False, ["pescatarian"]),
    ("Kosher", "Dietary preferences", 3, False, ["kosher"]),
    ("Halal", "Dietary preferences", 4, False, ["halal"]),
    (
        "Gluten-free",
        "Dietary preferences",
        5,
        True,
        ["gluten-free", "gluten free", "gf"],
    ),
    ("Dairy-free", "Dietary preferences", 6, True, ["dairy-free", "dairy free"]),
    ("Nut-free", "Dietary preferences", 7, True, ["nut-free", "nut free"]),
    ("Egg-free", "Dietary preferences", 8, True, ["egg-free", "egg free", "no eggs"]),
    (
        "Keto / Low-carb",
        "Dietary preferences",
        9,
        True,
        ["keto", "ketogenic", "low-carb", "low carb", "keto-friendly"],
    ),
    ("Paleo", "Dietary preferences", 10, True, ["paleo"]),
    (
        "Low-sodium",
        "Dietary preferences",
        11,
        True,
        ["low sodium", "low-sodium", "low salt"],
    ),
    (
        "Sugar-free",
        "Dietary preferences",
        12,
        True,
        ["sugar-free", "sugar free", "no sugar", "no added sugar"],
    ),
    (
        "Contains alcohol",
        "Content & serving",
        0,
        False,
        [
            "alcohol",
            "wine",
            "beer",
            "whiskey",
            "whisky",
            "vodka",
            "rum",
            "brandy",
            "bourbon",
            "liqueur",
        ],
    ),
    (
        "Contains pork",
        "Content & serving",
        1,
        False,
        ["pork", "bacon", "ham", "prosciutto", "pancetta", "chorizo", "salami", "lard"],
    ),
    (
        "Spicy",
        "Content & serving",
        2,
        False,
        [
            "spicy",
            "chili",
            "chilli",
            "jalapeño",
            "jalapeno",
            "sriracha",
            "cayenne",
            "habanero",
        ],
    ),
    ("Kid-friendly", "Content & serving", 3, False, ["for kids", "for children"]),
    (
        "Keep chilled",
        "Content & serving",
        4,
        False,
        ["chilled", "refrigerate", "refrigerated"],
    ),
    (
        "Prepared in a GF kitchen",
        "Content & serving",
        5,
        False,
        ["gf kitchen", "gluten-free kitchen", "gluten free kitchen"],
    ),
    (
        "Reheat: stovetop",
        "Content & serving",
        6,
        False,
        ["stovetop", "stove top", "hob"],
    ),
    ("Reheat: oven", "Content & serving", 7, False, ["oven", "bake"]),
    ("Reheat: microwave", "Content & serving", 8, False, ["microwave"]),
    (
        "Reheat: grill",
        "Content & serving",
        9,
        False,
        ["grill", "bbq", "barbecue", "broil"],
    ),
    (
        "Finger food",
        "Content & serving",
        10,
        True,
        ["finger food", "nibbles", "bites", "bite size", "bite-size"],
    ),
    (
        "Best served warm",
        "Content & serving",
        11,
        True,
        ["best served warm", "best warm", "serve warm"],
    ),
    ("Reheat: air fryer", "Content & serving", 12, True, ["air fryer", "airfryer"]),
]

SCHEMA = """
CREATE TABLE events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    management_token TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    event_date DATE,
    host_name TEXT NOT NULL DEFAULT 'The House',
    dish_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE dishes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    contributor TEXT NOT NULL,
    dish_name TEXT NOT NULL,
    dish_type TEXT NOT NULL,
    notes TEXT,
    is_host_item BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_dishes_event_id ON dishes (event_id, is_host_item, created_at);

CREATE TABLE config_entries (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category TEXT NOT NULL,
    value TEXT NOT NULL,
    position INTEGER NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_config_entries_category ON config_entries (category);

CREATE TABLE tags (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    is_hidden BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX idx_tags_category_position ON tags (category, position, id);

CREATE TABLE tag_keywords (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tag_id BIGINT NOT NULL REFERENCES tags (id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    UNIQUE (tag_id, keyword)
);

CREATE TABLE dish_tags (
    dish_id BIGINT NOT NULL REFERENCES dishes (id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES tags (id) ON DELETE CASCADE,
    PRIMARY KEY (dish_id, tag_id)
);
CREATE INDEX idx_dish_tags_tag_id ON dish_tags (tag_id);
"""


def upgrade() -> None:
    op.execute(SCHEMA)
    bind = op.get_bind()

    config_rows = [
        ("dish_type", value, idx) for idx, value in enumerate(DEFAULT_DISH_TYPES)
    ]
    config_rows += [
        ("admin_network", value, idx)
        for idx, value in enumerate(DEFAULT_ADMIN_NETWORKS)
    ]
    config_rows.append(("web_admin", "false", 0))
    for category, value, position in config_rows:
        bind.execute(
            sa.text(
                "INSERT INTO config_entries (category, value, position, updated_at) "
                "VALUES (:category, :value, :position, NOW())"
            ),
            {"category": category, "value": value, "position": position},
        )

    for name, category, position, is_hidden, keywords in DEFAULT_TAGS:
        tag_id = bind.execute(
            sa.text(
                "INSERT INTO tags (name, category, position, is_hidden) "
                "VALUES (:name, :category, :position, :is_hidden) RETURNING id"
            ),
            {
                "name": name,
                "category": category,
                "position": position,
                "is_hidden": is_hidden,
            },
        ).scalar_one()
        for keyword in keywords:
            bind.execute(
                sa.text(
                    "INSERT INTO tag_keywords (tag_id, keyword) "
                    "VALUES (:tag_id, :keyword)"
                ),
                {"tag_id": tag_id, "keyword": keyword},
            )


def downgrade() -> None:
    op.execute(
        "DROP TABLE dish_tags, tag_keywords, tags, config_entries, dishes, events"
    )
