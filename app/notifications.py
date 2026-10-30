"""Builds and sends DishList's transactional emails.

Each ``send_*`` function renders a text + HTML template pair from
``templates/email/`` and hands it to :mod:`app.mailer`. They are written to run
as FastAPI background tasks, so they take plain values rather than a request.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from typing import Tuple

from . import mailer
from .models import DishEntry, Event
from .storage import find_events_by_host_email, find_submissions_by_contributor_email

_env = Environment(
    loader=FileSystemLoader(
        str(Path(__file__).resolve().parent / "templates" / "email")
    ),
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


def send_lookup_email(address: str, base_url: str) -> bool:
    """Email everything stored under ``address``, or do nothing if there is nothing.

    Sending nothing for an unknown address is deliberate: it avoids mailing
    people who mistyped, and, together with an identical web response, stops
    the form from revealing which addresses are in use. Hosts get the public
    and management links; Guests get the public link of each Event they
    submitted to (never a management link).
    """

    events = find_events_by_host_email(address)
    submissions = find_submissions_by_contributor_email(address)
    if not events and not submissions:
        return False
    hosted = [{"event": event, **_links(event, base_url)} for event in events]
    dishes = [
        {
            "dish": dish,
            "event": event,
            "board_url": _links(event, base_url)["board_url"],
        }
        for dish, event in submissions
    ]
    text, html = _render("email_lookup", hosted=hosted, dishes=dishes)
    return mailer.send_email(address, "Your DishList events and dishes", text, html)


def send_admin_recovery(address: str, recovery_url: str) -> bool:
    """Email the operator a one-time link for setting a new admin password."""

    text, html = _render("admin_recovery", recovery_url=recovery_url)
    return mailer.send_email(address, "Reset your DishList admin password", text, html)
