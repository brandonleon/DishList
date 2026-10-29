"""Builds and sends DishList's transactional emails.

Each ``send_*`` function renders a text + HTML template pair from
``templates/email/`` and hands it to :mod:`app.mailer`. They are written to run
as FastAPI background tasks, so they take plain values rather than a request.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import mailer
from .models import DishEntry, Event

_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parent / "templates" / "email")),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _render(name: str, **context) -> tuple[str, str]:
    return (
        _env.get_template(f"{name}.txt").render(**context).strip() + "\n",
        _env.get_template(f"{name}.html").render(**context),
    )


def _links(event: Event, base_url: str) -> dict:
    return {
        "board_url": f"{base_url}/e/{event.slug}",
        "manage_url": f"{base_url}/manage/{event.management_token}",
    }


def send_host_welcome(
    event: Event, host_dishes: List[DishEntry], base_url: str, resend: bool = False
) -> bool:
    """Email the Host their private management link plus an event summary."""

    if not event.host_email:
        return False
    text, html = _render(
        "host_welcome",
        event=event,
        host_dishes=host_dishes,
        resend=resend,
        **_links(event, base_url),
    )
    subject = (
        f"Your management link for {event.name}"
        if resend
        else f"Your DishList event is ready: {event.name}"
    )
    return mailer.send_email(event.host_email, subject, text, html)


def send_guest_confirmation(event: Event, dish: DishEntry, base_url: str) -> bool:
    """Confirm a Guest's Submission and tell them to ask the Host for changes."""

    if not dish.contributor_email:
        return False
    text, html = _render(
        "guest_confirmation", event=event, dish=dish, **_links(event, base_url)
    )
    return mailer.send_email(
        dish.contributor_email,
        f"You're bringing {dish.dish_name} to {event.name}",
        text,
        html,
    )


def send_host_dish_notice(event: Event, dish: DishEntry, base_url: str) -> bool:
    """Tell the Host a Guest added a dish, if they opted in."""

    if not (event.host_email and event.notify_host):
        return False
    text, html = _render(
        "host_dish_notice", event=event, dish=dish, **_links(event, base_url)
    )
    return mailer.send_email(
        event.host_email,
        f"{dish.contributor} is bringing {dish.dish_name} to {event.name}",
        text,
        html,
    )
