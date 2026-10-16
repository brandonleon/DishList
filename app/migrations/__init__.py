"""Alembic schema migrations for DishList.

Alembic is configured in code rather than through an ``alembic.ini`` so the
migrations ship inside the ``app`` package and ``dishlist db upgrade`` works
from any directory.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

MIGRATIONS_DIR = Path(__file__).resolve().parent


def alembic_config(database_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    # Passed as an attribute, not a main option: ConfigParser would try to
    # interpolate any "%" in a password.
    cfg.attributes["database_url"] = database_url
    return cfg


def head_revision() -> str | None:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    return ScriptDirectory.from_config(cfg).get_current_head()


def upgrade(database_url: str) -> None:
    """Apply every pending migration to the database at ``database_url``."""
    command.upgrade(alembic_config(database_url), "head")
