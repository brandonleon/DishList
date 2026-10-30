"""Password login and email recovery for the web admin panel."""

import logging
import re
from datetime import datetime, timedelta, timezone

import pytest

from app import adminauth, storage
from app.models import Event  # noqa: F401

ADMIN = "/pantry-admin"
NEW_PASSWORD = "correct-horse-battery"


def _provision(caplog) -> str:
    with caplog.at_level(logging.WARNING, logger="test-admin"):
        adminauth.provision_temporary_password(logging.getLogger("test-admin"))
    return re.search(r"UTC: (\S+)$", caplog.text.strip().splitlines()[-1]).group(1)


def _auth(password):
    return {"Authorization": adminauth.basic_header(password)}


@pytest.fixture()
def login_on(monkeypatch):
    monkeypatch.setenv("ADMIN_LOGIN_ENABLED", "1")
    monkeypatch.delenv("ADMIN_PASSWORD_RESET", raising=False)


@pytest.fixture()
def recovery_on(login_on, email_on, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")


class TestProvisioning:
    def test_off_by_default(self, client, caplog):
        adminauth.provision_temporary_password(logging.getLogger("test-admin"))
        assert storage.get_admin_credentials() is None
        assert client.get(ADMIN).status_code == 404
        assert client.get(f"{ADMIN}/password").status_code == 404

    def test_second_startup_keeps_password(self, login_on, client, caplog):
        temporary = _provision(caplog)
        caplog.clear()
        adminauth.provision_temporary_password(logging.getLogger("test-admin"))
        assert caplog.text == ""
        assert adminauth.authenticate(adminauth.basic_header(temporary))

    def test_only_a_hash_is_stored(self, login_on, client, caplog):
        temporary = _provision(caplog)
        assert temporary not in str(storage.get_admin_credentials())

    def test_reset_marker_replaces_once(self, login_on, client, caplog, monkeypatch):
        old = _provision(caplog)
        monkeypatch.setenv("ADMIN_PASSWORD_RESET", "one")
        new = _provision(caplog)
        assert new != old
        caplog.clear()
        adminauth.provision_temporary_password(logging.getLogger("test-admin"))
        assert caplog.text == ""
        assert adminauth.authenticate(adminauth.basic_header(new))

    def test_expired_temporary_password_is_refused_and_replaced(
        self, login_on, client, caplog
    ):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        hashed = adminauth.hash_password("old-temporary")
        assert storage.provision_admin_password(hashed, past, None)
        assert adminauth.authenticate(adminauth.basic_header("old-temporary")) is None
        assert _provision(caplog) != "old-temporary"


class TestLogin:
    def test_no_credentials_prompts(self, login_on, client, caplog):
        _provision(caplog)
        resp = client.get(ADMIN)
        assert resp.status_code == 401
        assert resp.headers["www-authenticate"].startswith("Basic")

    def test_wrong_password(self, login_on, client, caplog):
        _provision(caplog)
        assert client.get(ADMIN, headers=_auth("nope")).status_code == 401

    @pytest.mark.parametrize("header", ["Basic !!!", "Bearer x", "Basic YWRtaW4="])
    def test_malformed_header(self, login_on, client, caplog, header):
        _provision(caplog)
        assert client.get(ADMIN, headers={"Authorization": header}).status_code == 401

    def test_wrong_username(self, login_on, client, caplog):
        temporary = _provision(caplog)
        headers = {"Authorization": adminauth.basic_header(temporary, "root")}
        assert client.get(ADMIN, headers=headers).status_code == 401

    def test_forged_forwarded_ip_does_not_help(self, login_on, client, caplog):
        _provision(caplog)
        resp = client.get(ADMIN, headers={"X-Forwarded-For": "127.0.0.1"})
        assert resp.status_code == 401

    def test_failed_logins_lock_out(self, login_on, client, caplog, monkeypatch):
        temporary = _provision(caplog)
        monkeypatch.setattr(adminauth, "FAILED_LOGIN_LIMIT", 2)
        for _ in range(2):
            assert client.get(ADMIN, headers=_auth("nope")).status_code == 401
        assert client.get(ADMIN, headers=_auth(temporary)).status_code == 429


class TestForcedChange:
    def test_redirected_until_changed(self, login_on, client, caplog):
        temporary = _provision(caplog)
        for path in (ADMIN, f"{ADMIN}/tags"):
            resp = client.get(path, headers=_auth(temporary), follow_redirects=False)
            assert resp.status_code == 303
            assert resp.headers["location"].endswith(f"{ADMIN}/password")

    def test_posts_blocked_until_changed(self, login_on, client, caplog):
        temporary = _provision(caplog)
        resp = client.post(
            f"{ADMIN}/tags/reset", headers=_auth(temporary), follow_redirects=False
        )
        assert resp.status_code == 303
        assert resp.headers["location"].endswith(f"{ADMIN}/password")

    def _change(self, client, current, new=NEW_PASSWORD, confirm=None, **kwargs):
        return client.post(
            f"{ADMIN}/password",
            headers=_auth(current),
            data={"new_password": new, "confirm_password": confirm or new},
            follow_redirects=False,
            **kwargs,
        )

    def test_change_then_login(self, login_on, client, caplog):
        temporary = _provision(caplog)
        assert self._change(client, temporary).status_code == 303
        assert client.get(ADMIN, headers=_auth(temporary)).status_code == 401
        assert client.get(ADMIN, headers=_auth(NEW_PASSWORD)).status_code == 200

    def test_requires_login(self, login_on, client, caplog):
        _provision(caplog)
        resp = client.post(
            f"{ADMIN}/password",
            data={"new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        )
        assert resp.status_code == 401

    def test_rejects_short_mismatched_and_same(self, login_on, client, caplog):
        temporary = _provision(caplog)
        assert self._change(client, temporary, new="short").status_code == 400
        assert (
            self._change(client, temporary, confirm="different-password").status_code
            == 400
        )
        assert self._change(client, temporary, new=temporary).status_code == 400


class TestCrossOrigin:
    def test_password_mode_refuses_other_sites(self, login_on, client, caplog):
        temporary = _provision(caplog)
        resp = client.post(
            f"{ADMIN}/password",
            headers={**_auth(temporary), "Origin": "https://evil.example"},
            data={"new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        )
        assert resp.status_code == 403

    def test_null_origin_refused(self, login_on, client, caplog):
        temporary = _provision(caplog)
        resp = client.post(
            f"{ADMIN}/password",
            headers={**_auth(temporary), "Origin": "null"},
            data={"new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
        )
        assert resp.status_code == 403

    def test_same_origin_allowed(self, login_on, client, caplog):
        temporary = _provision(caplog)
        resp = client.post(
            f"{ADMIN}/password",
            headers={**_auth(temporary), "Origin": "http://testserver"},
            data={"new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_ip_mode_refuses_other_sites(self, client):
        from app.config import AppConfig, save_config

        save_config(AppConfig(web_admin_enabled=True))
        client.app.state.config = AppConfig(web_admin_enabled=True)
        resp = client.post(
            f"{ADMIN}/reload", headers={"Origin": "https://evil.example"}
        )
        assert resp.status_code == 403


class TestRecovery:
    def _request_link(self, client, monkeypatch):
        sent = []
        monkeypatch.setattr(
            "app.notifications.mailer.send_email",
            lambda to, subject, text, html=None: sent.append((to, text)) or True,
        )
        resp = client.post(
            f"{ADMIN}/recover", headers={"Host": "evil.example"}, follow_redirects=False
        )
        assert resp.status_code == 303
        return sent

    def test_off_without_settings(self, login_on, client, caplog):
        _provision(caplog)
        assert client.get(f"{ADMIN}/recover").status_code == 404
        assert client.post(f"{ADMIN}/recover").status_code == 404
        assert "ADMIN_PASSWORD_RESET" in client.get(ADMIN).text

    def test_off_without_public_base_url(
        self, recovery_on, client, caplog, monkeypatch
    ):
        monkeypatch.delenv("PUBLIC_BASE_URL")
        _provision(caplog)
        assert client.get(f"{ADMIN}/recover").status_code == 404

    def test_login_page_links_to_recovery(self, recovery_on, client, caplog):
        _provision(caplog)
        assert f"{ADMIN}/recover" in client.get(ADMIN).text

    def test_link_ignores_host_header_and_goes_to_admin_email(
        self, recovery_on, client, caplog, monkeypatch
    ):
        _provision(caplog)
        sent = self._request_link(client, monkeypatch)
        assert sent[0][0] == "admin@example.com"
        assert "https://dish.example.com/pantry-admin/recover/" in sent[0][1]
        assert "evil.example" not in sent[0][1]

    def test_full_recovery_is_single_use(
        self, recovery_on, client, caplog, monkeypatch
    ):
        old = _provision(caplog)
        sent = self._request_link(client, monkeypatch)
        token = re.search(r"/recover/(\S+)", sent[0][1]).group(1)
        path = f"{ADMIN}/recover/{token}"
        page = client.get(path)
        assert page.status_code == 200
        assert page.headers["referrer-policy"] == "no-referrer"
        data = {"new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD}
        assert client.post(path, data=data, follow_redirects=False).status_code == 303
        assert client.get(ADMIN, headers=_auth(NEW_PASSWORD)).status_code == 200
        assert client.get(ADMIN, headers=_auth(old)).status_code == 401
        assert client.post(path, data=data).status_code == 404

    def test_request_alone_does_not_change_password(
        self, recovery_on, client, caplog, monkeypatch
    ):
        temporary = _provision(caplog)
        self._request_link(client, monkeypatch)
        assert adminauth.authenticate(adminauth.basic_header(temporary))

    def test_wrong_and_expired_tokens(self, recovery_on, client, caplog):
        _provision(caplog)
        assert client.get(f"{ADMIN}/recover/wrong").status_code == 404
        storage.set_admin_recovery(
            adminauth._token_hash("late"),
            datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        assert client.get(f"{ADMIN}/recover/late").status_code == 404

    def test_rate_limited_but_same_response(
        self, recovery_on, client, caplog, monkeypatch
    ):
        _provision(caplog)
        sent = []
        for _ in range(adminauth.RECOVERY_LIMIT + 2):
            sent = self._request_link(client, monkeypatch) + sent
        assert len(sent) == adminauth.RECOVERY_LIMIT

    def test_cross_origin_refused(self, recovery_on, client, caplog):
        _provision(caplog)
        resp = client.post(
            f"{ADMIN}/recover", headers={"Origin": "https://evil.example"}
        )
        assert resp.status_code == 403
