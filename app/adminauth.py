"""Password login for the web admin panel, for hosts with no CLI or network control.

Off unless ``ADMIN_LOGIN_ENABLED`` is set. The first startup logs a temporary
password, which must be replaced at first login. Only scrypt hashes are stored.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from . import mailer, notifications
from .storage import (
    get_admin_credentials,
    provision_admin_password,
    set_admin_password,
    set_admin_recovery,
)

USERNAME = "admin"
MIN_PASSWORD_LENGTH = 12
TEMPORARY_PASSWORD_LIFETIME = timedelta(hours=24)
RECOVERY_LIFETIME = timedelta(hours=1)
RECOVERY_KEY = "admin-recovery"
RECOVERY_LIMIT = 3  # recovery emails per window

FAILED_LOGIN_KEY = "admin-login-failed"
FAILED_LOGIN_LIMIT = 20
FAILED_LOGIN_WINDOW = 300  # seconds

_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 3
_SCRYPT_MAXMEM = 64 * 1024 * 1024
# Each hash takes tens of MB, so a burst of login attempts must not run them all at once.
_hash_slots = threading.BoundedSemaphore(2)


def login_enabled() -> bool:
    raw = os.environ.get("ADMIN_LOGIN_ENABLED", "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def recovery_enabled() -> bool:
    """Email recovery needs a fixed public URL: a link built from the request's
    Host header could be pointed at an attacker's site by whoever asks for it."""
    return bool(
        login_enabled()
        and mailer.is_configured()
        and os.environ.get("ADMIN_EMAIL", "").strip()
        and os.environ.get("PUBLIC_BASE_URL", "").strip()
    )


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    with _hash_slots:
        return hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=_SCRYPT_MAXMEM
        )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    _, n, r, p, salt, digest = stored.split("$")
    candidate = _scrypt(password, bytes.fromhex(salt), int(n), int(r), int(p))
    return secrets.compare_digest(candidate, bytes.fromhex(digest))


def provision_temporary_password(log: logging.Logger) -> None:
    """Create and log a temporary password at startup if one is needed."""
    if not login_enabled():
        return
    password = secrets.token_urlsafe(18)
    expires_at = datetime.now(timezone.utc) + TEMPORARY_PASSWORD_LIFETIME
    marker = os.environ.get("ADMIN_PASSWORD_RESET", "").strip() or None
    if provision_admin_password(hash_password(password), expires_at, marker):
        log.warning(
            "Web admin temporary password for user '%s', valid until %s: %s",
            USERNAME,
            expires_at.strftime("%Y-%m-%d %H:%M UTC"),
            password,
        )


def basic_header(password: str, username: str = USERNAME) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def authenticate(header: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return the stored credentials if the Authorization header is valid."""
    if not header or not header.lower().startswith("basic "):
        return None
    try:
        decoded = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    username, separator, password = decoded.partition(":")
    if not separator:
        return None
    credentials = get_admin_credentials()
    if credentials is None:
        return None
    username_ok = secrets.compare_digest(username.encode(), USERNAME.encode())
    password_ok = verify_password(password, credentials["password_hash"])
    if not (username_ok and password_ok):
        return None
    if credentials["must_change"] and credentials["expires_at"] <= (
        datetime.now(timezone.utc).isoformat()
    ):
        return None
    return credentials


def password_problem(new_password: str, confirm_password: str) -> Optional[str]:
    if new_password != confirm_password:
        return "The passwords do not match."
    if len(new_password) < MIN_PASSWORD_LENGTH:
        return f"Use at least {MIN_PASSWORD_LENGTH} characters."
    return None


def change_password(new_password: str) -> None:
    set_admin_password(hash_password(new_password))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def send_recovery_email() -> bool:
    """Email a one-time recovery link to ADMIN_EMAIL. Runs as a background task."""
    token = secrets.token_urlsafe(32)
    set_admin_recovery(
        _token_hash(token), datetime.now(timezone.utc) + RECOVERY_LIFETIME
    )
    return notifications.send_admin_recovery(
        os.environ.get("ADMIN_EMAIL", "").strip(),
        f"{mailer.public_base_url()}/pantry-admin/recover/{token}",
    )


def recovery_token_valid(token: str) -> bool:
    credentials = get_admin_credentials()
    if not credentials or not credentials["recovery_hash"]:
        return False
    if credentials["recovery_expires_at"] <= datetime.now(timezone.utc).isoformat():
        return False
    return secrets.compare_digest(_token_hash(token), credentials["recovery_hash"])
