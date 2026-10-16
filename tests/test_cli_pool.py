"""The CLI releases the connection pool when a command finishes."""

from click.testing import CliRunner

from app import storage
from app.cli import cli


def test_admin_command_closes_pool():
    result = CliRunner().invoke(cli, ["admin", "status"])
    assert result.exit_code == 0, result.output
    assert storage._pool is None
