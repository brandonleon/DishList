"""Alembic environment: runs migrations against ``DATABASE_URL`` via psycopg."""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, pool, text

# Arbitrary constant: every DishList migration run takes this advisory lock.
MIGRATION_LOCK_ID = 7_340_201


def _sqlalchemy_url(url: str) -> str:
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    raise RuntimeError("DATABASE_URL must be a postgresql:// URL")


def run_migrations_online() -> None:
    url = context.config.attributes["database_url"]
    engine = create_engine(
        _sqlalchemy_url(url),
        poolclass=pool.NullPool,
        # Works through Neon's PgBouncer pooler as well as a direct connection.
        connect_args={"prepare_threshold": None},
    )
    with engine.connect() as connection:
        # All pending revisions run in one transaction that first takes an
        # advisory lock, so concurrent runs (several instances bootstrapping an
        # empty database at once) wait for each other, and the second finds the
        # schema already current. The transaction-scoped lock also works through
        # a transaction-mode pooler. A failure rolls the whole run back.
        context.configure(connection=connection)
        with context.begin_transaction():
            connection.execute(
                text("SELECT pg_advisory_xact_lock(:id)"), {"id": MIGRATION_LOCK_ID}
            )
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline (--sql) migrations are not supported")
run_migrations_online()
