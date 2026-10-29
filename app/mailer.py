"""Optional transactional email via the Resend HTTP API.

Email is off unless ``RESEND_API_KEY`` and ``RESEND_FROM`` are both set. Callers
should check :func:`is_configured` before offering email fields, and can call
:func:`send_email` unconditionally: it never raises, so a mail failure can never
break an event or dish submission.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

import httpx

RESEND_API_URL = "https://api.resend.com/emails"
SEND_TIMEOUT_SECONDS = 10.0

logger = logging.getLogger("dishlist.mailer")

# Deliberately loose: one "@", no whitespace, a dot in the domain. Resend does
# the real validation; this only rejects obvious typos before we store anything.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _api_key() -> str:
    return os.environ.get("RESEND_API_KEY", "").strip()


def _from_address() -> str:
    return os.environ.get("RESEND_FROM", "").strip()


def is_configured() -> bool:
    return bool(_api_key() and _from_address())


def status_summary() -> str:
    """One line saying whether email is on, and what is missing if not. No secrets."""

    if is_configured():
        base = os.environ.get("PUBLIC_BASE_URL", "").strip()
        return "Email enabled (Resend); links use " + (
            base if base else "the request URL (PUBLIC_BASE_URL not set)"
        )
    missing = [
        name
        for name, value in (
            ("RESEND_API_KEY", _api_key()),
            ("RESEND_FROM", _from_address()),
        )
        if not value
    ]
    return "Email disabled: missing " + ", ".join(missing)


def public_base_url(fallback: str = "") -> str:
    """Absolute site URL for links in emails, without a trailing slash."""

    configured = os.environ.get("PUBLIC_BASE_URL", "").strip()
    return (configured or fallback).rstrip("/")


def clean_email(value: Optional[str]) -> Optional[str]:
    """Return a normalized address, or None if blank. Raises ValueError if malformed."""

    if value is None or not value.strip():
        return None
    address = value.strip()
    if len(address) > 254 or not _EMAIL_RE.match(address):
        raise ValueError("Invalid email address")
    return address


def send_email(
    to: str, subject: str, text: str, html: Optional[str] = None
) -> bool:
    """Send one email through Resend. Returns True on success; never raises."""

    if not is_configured():
        return False
    payload = {"from": _from_address(), "to": [to], "subject": subject, "text": text}
    if html:
        payload["html"] = html
    try:
        response = httpx.post(
            RESEND_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {_api_key()}"},
            timeout=SEND_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Resend email to recipient failed: %s", exc)
        return False
    return True
