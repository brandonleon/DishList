"""The serve command must not trust forwarded headers from every client."""

from unittest.mock import patch

from click.testing import CliRunner

from app.cli import cli


def _serve_kwargs(monkeypatch, env_value=None):
    if env_value is None:
        monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    else:
        monkeypatch.setenv("FORWARDED_ALLOW_IPS", env_value)
    with patch("uvicorn.run") as run:
        result = CliRunner().invoke(cli, ["serve", "--no-reload"])
    assert result.exit_code == 0
    return run.call_args.kwargs, result.output


def test_serve_leaves_trust_to_uvicorn_env(monkeypatch):
    kwargs, _ = _serve_kwargs(monkeypatch)
    assert kwargs["proxy_headers"] is True
    # None makes uvicorn read FORWARDED_ALLOW_IPS, defaulting to 127.0.0.1.
    assert kwargs.get("forwarded_allow_ips") is None


def test_serve_reload_fallback_keeps_trust_setting(monkeypatch):
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    with patch("uvicorn.run", side_effect=[PermissionError, None]) as run:
        result = CliRunner().invoke(cli, ["serve", "--reload"])
    assert result.exit_code == 0
    assert run.call_count == 2
    assert run.call_args.kwargs.get("forwarded_allow_ips") is None


def test_serve_reports_trusted_proxies(monkeypatch):
    _, output = _serve_kwargs(monkeypatch, "10.0.0.2,172.16.0.0/12")
    assert "Trusted proxies: 10.0.0.2,172.16.0.0/12" in output


def test_serve_reports_default_trusted_proxy(monkeypatch):
    _, output = _serve_kwargs(monkeypatch)
    assert "Trusted proxies: 127.0.0.1" in output
