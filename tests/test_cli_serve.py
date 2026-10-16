"""`dishlist serve` proxy-trust configuration."""

import pytest
import uvicorn
from click.testing import CliRunner

from app.cli import cli


@pytest.fixture
def run_calls(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    monkeypatch.delenv("DISHLIST_RELOAD", raising=False)
    return calls


def _serve(*args, env=None):
    return CliRunner().invoke(cli, ["serve", "--no-reload", *args], env=env)


def test_default_trusts_all_proxies(run_calls):
    result = _serve()
    assert result.exit_code == 0, result.output
    assert run_calls[0]["forwarded_allow_ips"] == "*"
    assert run_calls[0]["proxy_headers"] is True


def test_env_var_restricts_trusted_proxies(run_calls):
    result = _serve(env={"FORWARDED_ALLOW_IPS": "127.0.0.1"})
    assert result.exit_code == 0, result.output
    assert run_calls[0]["forwarded_allow_ips"] == "127.0.0.1"


def test_option_overrides_env_var(run_calls):
    result = _serve(
        "--forwarded-allow-ips",
        "10.0.0.0/8",
        env={"FORWARDED_ALLOW_IPS": "127.0.0.1"},
    )
    assert result.exit_code == 0, result.output
    assert run_calls[0]["forwarded_allow_ips"] == "10.0.0.0/8"


def test_empty_env_var_falls_back_to_default(run_calls):
    result = _serve(env={"FORWARDED_ALLOW_IPS": ""})
    assert result.exit_code == 0, result.output
    assert run_calls[0]["forwarded_allow_ips"] == "*"


def test_setting_is_kept_on_no_reload_fallback(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(kwargs)
        if kwargs.get("reload"):
            raise PermissionError("no inotify")

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.delenv("DISHLIST_RELOAD", raising=False)
    result = CliRunner().invoke(
        cli, ["serve", "--reload", "--forwarded-allow-ips", "10.0.0.0/8"]
    )
    assert result.exit_code == 0, result.output
    assert [c["reload"] for c in calls] == [True, False]
    assert [c["forwarded_allow_ips"] for c in calls] == ["10.0.0.0/8", "10.0.0.0/8"]
