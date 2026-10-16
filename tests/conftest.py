"""Shared fixtures for DishList tests.

Tests run against PostgreSQL. ``TEST_DATABASE_URL`` names a server and a
database to connect to for administration (default: the compose service's
``postgres`` database). A template database is migrated once per session, and
every test gets its own clone of it, so tests never share state.

Start the server with ``docker compose up -d postgres``.
"""

import itertools
import os
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from app import migrations, storage

DEFAULT_TEST_DATABASE_URL = "postgresql://dishlist:dishlist@127.0.0.1:5432/postgres"
TEMPLATE_DB = "dishlist_test_template"
_db_counter = itertools.count()


def _url_for(base_url: str, dbname: str) -> str:
    parts = urlsplit(base_url)
    return urlunsplit(parts._replace(path=f"/{dbname}"))


def _admin_connect(base_url: str) -> psycopg.Connection:
    return psycopg.connect(base_url, autocommit=True, connect_timeout=3)


def _drop_database(conn: psycopg.Connection, dbname: str) -> None:
    conn.execute(
        sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
            sql.Identifier(dbname)
        )
    )


@pytest.fixture(scope="session")
def postgres_server():
    """Admin URL of the test server, with a freshly migrated template database."""
    base_url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    try:
        conn = _admin_connect(base_url)
    except psycopg.OperationalError as exc:
        pytest.skip(
            f"PostgreSQL is not reachable at TEST_DATABASE_URL ({exc}). "
            "Start it with `docker compose up -d postgres`."
        )
    with conn:
        _drop_database(conn, TEMPLATE_DB)
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEMPLATE_DB)))
    migrations.upgrade(_url_for(base_url, TEMPLATE_DB))
    yield base_url
    with _admin_connect(base_url) as conn:
        _drop_database(conn, TEMPLATE_DB)


@pytest.fixture
def fresh_database(postgres_server):
    """Create an empty, unmigrated database and return its URL."""
    dbname = f"dishlist_test_{os.getpid()}_{next(_db_counter)}"
    with _admin_connect(postgres_server) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    yield _url_for(postgres_server, dbname)
    storage.close_pool()
    with _admin_connect(postgres_server) as conn:
        _drop_database(conn, dbname)


@pytest.fixture(autouse=True)
def isolated_db(request, monkeypatch):
    """Point DATABASE_URL at a private clone of the migrated template."""
    if request.node.get_closest_marker("no_db"):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        yield None
        return
    base_url = request.getfixturevalue("postgres_server")
    dbname = f"dishlist_test_{os.getpid()}_{next(_db_counter)}"
    with _admin_connect(base_url) as conn:
        conn.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(dbname), sql.Identifier(TEMPLATE_DB)
            )
        )
    url = _url_for(base_url, dbname)
    storage.close_pool()
    monkeypatch.setenv("DATABASE_URL", url)
    yield url
    storage.close_pool()
    with _admin_connect(base_url) as conn:
        _drop_database(conn, dbname)


@pytest.fixture
def client(isolated_db):
    """FastAPI TestClient with a clean DB.

    The client peer is fixed to 127.0.0.1 so tests can exercise the
    IP-allowlist gates without bypass.
    """
    from app.main import app

    with TestClient(
        app, raise_server_exceptions=True, client=("127.0.0.1", 50000)
    ) as c:
        yield c
