"""Schema migrations: `dishlist db upgrade` and the startup schema check."""

import psycopg
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from app import migrations, storage
from app.cli import cli
from app.storage import SchemaOutOfDateError, check_schema, load_tags


def _upgrade(url: str):
    return CliRunner().invoke(cli, ["db", "upgrade"], env={"DATABASE_URL": url})


def _scalar(url: str, query: str):
    with psycopg.connect(url) as conn:
        return conn.execute(query).fetchone()[0]


class TestDbUpgrade:
    def test_empty_database_is_created_and_seeded(self, fresh_database):
        result = _upgrade(fresh_database)
        assert result.exit_code == 0, result.output
        assert "upgraded to" in result.output
        assert _scalar(fresh_database, "SELECT version_num FROM alembic_version") == (
            migrations.head_revision()
        )
        assert _scalar(fresh_database, "SELECT COUNT(*) FROM tags") > 0
        assert _scalar(fresh_database, "SELECT COUNT(*) FROM tag_keywords") > 0
        assert (
            _scalar(
                fresh_database,
                "SELECT COUNT(*) FROM config_entries WHERE category = 'dish_type'",
            )
            > 0
        )

    def test_second_run_is_a_no_op(self, fresh_database):
        assert _upgrade(fresh_database).exit_code == 0
        result = _upgrade(fresh_database)
        assert result.exit_code == 0, result.output
        assert "already at the latest revision" in result.output

    def test_failing_migration_exits_non_zero(self, fresh_database, monkeypatch):
        def boom(url):
            raise RuntimeError("syntax error in revision 0002")

        monkeypatch.setattr(migrations, "upgrade", boom)
        result = _upgrade(fresh_database)
        assert result.exit_code == 1
        assert "Migration failed" in result.output
        assert "left at revision empty" in result.output


class TestSeedDefaults:
    def test_baseline_tags_match_reset_defaults(self):
        """The frozen baseline seed and `tags reset` produce the same library."""

        def snapshot():
            return sorted(
                (t.name, t.category, t.position, t.is_hidden, tuple(t.keywords))
                for t in load_tags()
            )

        migrated = snapshot()
        storage.reset_tags_to_defaults()
        assert snapshot() == migrated


class TestStartupSchemaCheck:
    def test_current_schema_passes(self):
        check_schema()

    def test_unmigrated_database_refuses_to_start(self, fresh_database, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", fresh_database)
        storage.close_pool()
        from app.main import app

        with (
            pytest.raises(SchemaOutOfDateError, match="dishlist db upgrade"),
            TestClient(app),
        ):
            pass

    def test_outdated_schema_refuses_to_start(self, fresh_database, monkeypatch):
        with psycopg.connect(fresh_database) as conn:
            conn.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
            conn.execute("INSERT INTO alembic_version VALUES ('0000_older')")
        monkeypatch.setenv("DATABASE_URL", fresh_database)
        storage.close_pool()
        with pytest.raises(SchemaOutOfDateError, match="0000_older"):
            check_schema()


@pytest.mark.no_db
class TestCliWithoutDatabaseUrl:
    def test_admin_command_fails_with_clear_message(self):
        result = CliRunner().invoke(cli, ["admin", "status"])
        assert result.exit_code == 1
        assert "DATABASE_URL must be set" in result.output

    def test_db_upgrade_fails_with_clear_message(self):
        result = CliRunner().invoke(cli, ["db", "upgrade"])
        assert result.exit_code == 1
        assert "DATABASE_URL must be set" in result.output
