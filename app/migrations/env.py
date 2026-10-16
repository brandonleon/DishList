"""Alembic environment: runs migrations against ``DATABASE_URL`` via psycopg."""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, pool


def _sqlalchemy_url(url: str) -> str:
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    raise RuntimeError("DATABASE_URL must be a postgresql:// URL")


def run_migrations_online() -> None:
    url = context.config.attributes["database_url"]
    engine = create_engine(_sqlalchemy_url(url), poolclass=pool.NullPool)
    with engine.connect() as connection:
        # One transaction per revision, so a failure leaves the database at the
        # last revision that applied cleanly.
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline (--sql) migrations are not supported")
run_migrations_online()
