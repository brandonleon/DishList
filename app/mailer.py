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
    """One line saying whether email is on, with the settings seen.

    Only the first 4 characters of the API key are shown, enough to check the
    right key was loaded without exposing it.
    """

    key = _api_key()
    sender = _from_address()
    base = os.environ.get("PUBLIC_BASE_URL", "").strip()
    state = "enabled" if is_configured() else "disabled"
    return (
        f"Email {state}: "
        f"RESEND_API_KEY={key[:4] + '...' if key else '(not set)'}, "
        f"RESEND_FROM={sender or '(not set)'}, "
        f"PUBLIC_BASE_URL={base or '(not set)'}"
    )


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
