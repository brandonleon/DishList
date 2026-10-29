"""PostgreSQL backend tests.

The translation tests always run. The rest need a throwaway database in
TEST_DATABASE_URL (see conftest.py) and are skipped without one.
"""

import os
import threading

import pytest

import app.storage as storage
from app.models import DishEntry
from app.storage import (
    add_dish,
    create_event,
    get_event_by_slug,
    init_db,
    load_dishes_for_event,
    load_events,
)

needs_postgres = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL to a throwaway PostgreSQL database",
)


class TestBackendSelection:
    @pytest.mark.parametrize(
        "url",
        ["postgresql://u:p@h/db", "postgres://u:p@h/db?sslmode=require", " postgresql://h/db "],
    )
    def test_postgres_urls_select_postgres(self, monkeypatch, url):
        monkeypatch.setenv("DATABASE_URL", url)
        assert storage._postgres_url() == url.strip()

    @pytest.mark.parametrize("url", ["", "sqlite:///data/dishlist.db", "mysql://h/db"])
    def test_everything_else_is_sqlite(self, monkeypatch, url):
        monkeypatch.setenv("DATABASE_URL", url)
        assert storage._postgres_url() is None

    def test_unset_is_sqlite(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert storage._postgres_url() is None


class TestSqlTranslation:
    def test_placeholders(self):
        assert (
            storage._pg_sql("SELECT * FROM t WHERE a = ? AND b IN (?, ?)")
            == "SELECT * FROM t WHERE a = %s AND b IN (%s, %s)"
        )

    def test_autoincrement_becomes_serial(self):
        sql = storage._pg_sql("CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        assert "SERIAL PRIMARY KEY" in sql and "AUTOINCREMENT" not in sql

    def test_literal_percent_is_escaped(self):
        assert storage._pg_sql("SELECT '100%' WHERE a = ?") == "SELECT '100%%' WHERE a = %s"


@needs_postgres
class TestPostgres:
    def test_backend_is_postgres(self):
        with storage._get_connection() as conn:
            assert conn.postgres is True

    def test_data_survives_reconnect(self):
        """What a redeploy does: new process, new pool, same database."""
        event = create_event("Persist", None, None, "Host", ["Main"])
        add_dish(
            DishEntry(event_id=event.id, contributor="G", dish_name="Pie", dish_type="Main")
        )
        storage.close_pool()
        reloaded = get_event_by_slug(event.slug)
        assert reloaded is not None and reloaded.name == "Persist"
        assert [d.dish_name for d in load_dishes_for_event(event.id)] == ["Pie"]

    def test_unicode_round_trips(self):
        event = create_event("Fête 🍂", "Crème brûlée & más", None, "Hôte", ["Plat"])
        add_dish(
            DishEntry(
                event_id=event.id,
                contributor="Zoë",
                dish_name="Gâteau 🎂",
                dish_type="Plat",
                notes="日本語",
            )
        )
        loaded = get_event_by_slug(event.slug)
        assert loaded.name == "Fête 🍂"
        dish = load_dishes_for_event(event.id)[0]
        assert (dish.contributor, dish.dish_name, dish.notes) == ("Zoë", "Gâteau 🎂", "日本語")

    def test_ids_are_sequential_and_returned(self):
        first = create_event("One", None, None, "H", ["Main"])
        second = create_event("Two", None, None, "H", ["Main"])
        assert second.id == first.id + 1
        assert [e.name for e in load_events()] == ["Two", "One"]

    def test_dishes_ordered_chronologically(self):
        from datetime import datetime, timedelta, timezone

        event = create_event("Order", None, None, "H", ["Main"])
        base = datetime(2030, 1, 1, tzinfo=timezone.utc)
        for name, offset in (("late", 2), ("early", 0), ("mid", 1)):
            add_dish(
                DishEntry(
                    event_id=event.id,
                    contributor="G",
                    dish_name=name,
                    dish_type="Main",
                    created_at=base + timedelta(hours=offset),
                )
            )
        assert [d.dish_name for d in load_dishes_for_event(event.id)] == [
            "early",
            "mid",
            "late",
        ]

    def test_cascade_delete(self):
        from app.storage import delete_event

        event = create_event("Gone", None, None, "H", ["Main"])
        add_dish(DishEntry(event_id=event.id, contributor="G", dish_name="X", dish_type="Main"))
        delete_event(event.id)
        assert load_dishes_for_event(event.id) == []

    def test_failed_transaction_rolls_back(self):
        with pytest.raises(RuntimeError):
            with storage._get_connection() as conn:
                conn.execute(
                    "INSERT INTO events (slug, management_token, name, dish_types, created_at)"
                    " VALUES ('rb', 'rbt', 'Rollback', '[]', '2030-01-01T00:00:00+00:00')"
                )
                raise RuntimeError("boom")
        assert get_event_by_slug("rb") is None

    def test_init_db_is_idempotent_and_concurrency_safe(self):
        errors = []

        def run():
            try:
                init_db()
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []

    def test_adds_columns_to_old_schema(self):
        import psycopg

        url = os.environ["TEST_DATABASE_URL"]
        storage.close_pool()
        with psycopg.connect(url, autocommit=True) as raw:
            raw.execute("DROP SCHEMA public CASCADE")
            raw.execute("CREATE SCHEMA public")
            raw.execute(
                "CREATE TABLE events (id SERIAL PRIMARY KEY, slug TEXT NOT NULL UNIQUE,"
                " management_token TEXT NOT NULL UNIQUE, name TEXT NOT NULL, description TEXT,"
                " event_date TEXT, host_name TEXT NOT NULL DEFAULT 'The House',"
                " dish_types TEXT NOT NULL DEFAULT '[]', is_active INTEGER NOT NULL DEFAULT 1,"
                " created_at TEXT NOT NULL)"
            )
            raw.execute(
                "CREATE TABLE dishes (id SERIAL PRIMARY KEY, event_id INTEGER NOT NULL"
                " REFERENCES events(id) ON DELETE CASCADE, contributor TEXT NOT NULL,"
                " dish_name TEXT NOT NULL, dish_type TEXT NOT NULL, notes TEXT,"
                " is_host_item INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)"
            )
            raw.execute(
                "INSERT INTO events (slug, management_token, name, dish_types, created_at)"
                " VALUES ('s', 't', 'Old', '[\"Main\"]', '2025-01-01T00:00:00+00:00')"
            )
        init_db()
        init_db()
        event = get_event_by_slug("s")
        assert event.host_email is None and event.notify_host is False


class TestDescribeBackend:
    def test_sqlite(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert storage.describe_backend().startswith("SQLite (")

    def test_postgres_hides_credentials(self, monkeypatch):
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql://user:s3cret@ep-cool-1234.neon.tech/dish?sslmode=require",
        )
        text = storage.describe_backend()
        assert text == "PostgreSQL (host=ep-cool-1234.neon.tech, database=dish)"
        assert "s3cret" not in text and "user" not in text
