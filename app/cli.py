"""DishList command-line management tool.

Usage:
    dishlist serve                        Start the web server
    dishlist admin status                 Show current configuration
    dishlist admin web enable             Enable /pantry-admin (optionally add a network)
    dishlist admin web disable            Disable /pantry-admin
    dishlist admin networks list          List allowed admin networks
    dishlist admin networks add <cidr>    Add an IP/CIDR to the allowlist
    dishlist admin networks remove <cidr> Remove an IP/CIDR from the allowlist
    dishlist admin dish-types list        List default dish categories
    dishlist admin dish-types add <name>  Add a dish category
    dishlist admin dish-types remove <n>  Remove a dish category
    dishlist admin tags list              List dietary tags
    dishlist admin tags add <name> <cat>  Add a dietary tag
    dishlist admin tags remove <id>       Remove a dietary tag by ID
    dishlist admin tags reset             Reset tag library to defaults
    dishlist admin events list            List all events
    dishlist admin events delete <id>     Delete an event and all its dishes
"""
from __future__ import annotations

import ipaddress
import sys
from typing import Optional

import click


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load():
    from app.config import load_config
    return load_config()


def _save(config):
    from app.config import save_config
    save_config(config)


def _ok(msg: str) -> None:
    click.echo(click.style("✓ ", fg="green") + msg)


def _err(msg: str) -> None:
    click.echo(click.style("Error: ", fg="red") + msg, err=True)


def _validate_network(value: str) -> str:
    try:
        ipaddress.ip_network(value, strict=False)
        return value
    except ValueError:
        raise click.BadParameter(
            f"'{value}' is not a valid IP address or CIDR range "
            f"(examples: 192.168.1.5  or  10.0.0.0/24)"
        )


# ── Root ──────────────────────────────────────────────────────────────────────

@click.group()
def cli() -> None:
    """DishList — potluck planner management CLI."""


# ── serve ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--host", default="0.0.0.0", show_default=True, help="Bind address.")
@click.option("--port", default=8000, show_default=True, help="Bind port.")
@click.option(
    "--reload/--no-reload",
    default=None,
    help="Enable live reload (default: on unless DISHLIST_RELOAD=0).",
)
def serve(host: str, port: int, reload: Optional[bool]) -> None:
    """Start the DishList web server."""
    import os
    import uvicorn

    if reload is None:
        raw = os.getenv("DISHLIST_RELOAD")
        reload = raw is None or raw.lower() in {"1", "true", "yes", "on"}

    click.echo(f"Starting DishList on http://{host}:{port}")
    try:
        uvicorn.run("app.main:app", host=host, port=port, reload=reload,
                    proxy_headers=True, forwarded_allow_ips="*")
    except PermissionError:
        if not reload:
            raise
        click.echo("Live reload blocked; starting without reload.", err=True)
        uvicorn.run("app.main:app", host=host, port=port, reload=False,
                    proxy_headers=True, forwarded_allow_ips="*")


# ── admin ─────────────────────────────────────────────────────────────────────

@cli.group()
def admin() -> None:
    """Manage DishList configuration."""


@admin.command("status")
def admin_status() -> None:
    """Show current configuration and system status."""
    from app.storage import load_events, load_tag_groups

    config = _load()
    events = load_events()

    click.echo()
    click.echo(click.style("DishList Status", bold=True))
    click.echo("─" * 44)

    web_label = (
        click.style("enabled", fg="green")
        if config.web_admin_enabled
        else click.style("disabled", fg="yellow")
    )
    click.echo(f"  Web admin    {web_label}")
    if not config.web_admin_enabled:
        click.echo(
            click.style("               Run: ", dim=True)
            + "dishlist admin web enable"
        )
    click.echo(f"  Events       {len(events)}")
    click.echo()

    click.echo(click.style("Allowed admin networks:", bold=True))
    for net in config.admin_networks:
        click.echo(f"  • {net}")
    click.echo()

    click.echo(click.style("Default dish categories:", bold=True))
    for dt in config.dish_types:
        click.echo(f"  • {dt}")
    click.echo()

    click.echo(click.style("Dietary tag library:", bold=True))
    for category, tag_list in load_tag_groups():
        click.echo(f"  {click.style(category, bold=True)}  ({len(tag_list)})")
        for tag in tag_list:
            click.echo(f"    [{tag.id:>3}]  {tag.name}")
    click.echo()


# ── admin web ─────────────────────────────────────────────────────────────────

@admin.group()
def web() -> None:
    """Enable or disable the /pantry-admin web panel."""


@web.command("enable")
@click.option(
    "--network",
    default=None,
    metavar="IP_OR_CIDR",
    help="Add an IP or CIDR to the allowlist at the same time.",
)
def web_enable(network: Optional[str]) -> None:
    """Enable the web admin panel at /pantry-admin."""
    config = _load()

    if network:
        network = _validate_network(network)
        if network not in config.admin_networks:
            config.admin_networks.append(network)
            _ok(f"Added network: {network}")

    if not config.admin_networks:
        _err(
            "No allowed networks configured.\n"
            "       Add one first:  dishlist admin networks add <ip-or-cidr>\n"
            "       Or combine:     dishlist admin web enable --network 192.168.1.5"
        )
        sys.exit(1)

    config.web_admin_enabled = True
    _save(config)
    _ok("Web admin enabled at /pantry-admin")
    click.echo(f"  Allowed from: {', '.join(config.admin_networks)}")


@web.command("disable")
def web_disable() -> None:
    """Disable the web admin panel."""
    config = _load()
    config.web_admin_enabled = False
    _save(config)
    _ok("Web admin disabled.")
    click.echo("  Use  dishlist admin  commands to manage settings from the CLI.")


# ── admin networks ────────────────────────────────────────────────────────────

@admin.group()
def networks() -> None:
    """Manage IP addresses and CIDR ranges allowed to access web admin."""


@networks.command("list")
def networks_list() -> None:
    """List allowed admin networks."""
    config = _load()
    if not config.admin_networks:
        click.echo("No networks configured.")
        return
    click.echo(click.style("Allowed admin networks:", bold=True))
    for net in config.admin_networks:
        click.echo(f"  {net}")


@networks.command("add")
@click.argument("network")
def networks_add(network: str) -> None:
    """Add an IP address or CIDR range (e.g. 192.168.1.5 or 10.0.0.0/24)."""
    network = _validate_network(network)
    config = _load()
    if network in config.admin_networks:
        click.echo(f"'{network}' is already in the allowlist.")
        return
    config.admin_networks.append(network)
    _save(config)
    _ok(f"Added {network}")


@networks.command("remove")
@click.argument("network")
def networks_remove(network: str) -> None:
    """Remove an IP address or CIDR range from the allowlist."""
    config = _load()
    if network not in config.admin_networks:
        _err(f"'{network}' is not in the allowlist.")
        sys.exit(1)
    config.admin_networks.remove(network)
    _save(config)
    _ok(f"Removed {network}")


# ── admin dish-types ──────────────────────────────────────────────────────────

@admin.group("dish-types")
def dish_types() -> None:
    """Manage the default dish categories seeded into new events."""


@dish_types.command("list")
def dish_types_list() -> None:
    """List current default dish categories."""
    config = _load()
    click.echo(click.style("Default dish categories:", bold=True))
    for i, dt in enumerate(config.dish_types, 1):
        click.echo(f"  {i:>2}.  {dt}")


@dish_types.command("add")
@click.argument("name")
def dish_types_add(name: str) -> None:
    """Add a dish category."""
    config = _load()
    if name in config.dish_types:
        click.echo(f"'{name}' already exists.")
        return
    config.dish_types.append(name)
    _save(config)
    _ok(f"Added '{name}'")


@dish_types.command("remove")
@click.argument("name")
def dish_types_remove(name: str) -> None:
    """Remove a dish category."""
    config = _load()
    if name not in config.dish_types:
        _err(f"'{name}' not found in dish categories.")
        sys.exit(1)
    config.dish_types.remove(name)
    _save(config)
    _ok(f"Removed '{name}'")


# ── admin tags ────────────────────────────────────────────────────────────────

@admin.group()
def tags() -> None:
    """Manage the dietary tag library (shared across all events)."""


@tags.command("list")
def tags_list() -> None:
    """List all dietary tags grouped by category."""
    from app.storage import load_tag_groups

    click.echo(click.style("Dietary tag library:", bold=True))
    for category, tag_list in load_tag_groups():
        click.echo(f"\n  {click.style(category, bold=True)}")
        for tag in tag_list:
            click.echo(f"    [{tag.id:>3}]  {tag.name}")


@tags.command("add")
@click.argument("name")
@click.argument("category")
def tags_add(name: str, category: str) -> None:
    """Add a dietary tag to CATEGORY (existing or new)."""
    from app.storage import create_tag, get_tag_categories

    known = get_tag_categories()
    if category not in known:
        click.echo(f"  Known categories: {', '.join(known)}")
        if not click.confirm(f"Create new category '{category}'?"):
            return
    try:
        tag = create_tag(name, category)
        _ok(f"[{tag.id}] '{tag.name}'  →  {tag.category}")
    except ValueError as exc:
        _err(str(exc))
        sys.exit(1)


@tags.command("remove")
@click.argument("tag_id", type=int)
def tags_remove(tag_id: int) -> None:
    """Remove a dietary tag by its ID (see 'dishlist admin tags list')."""
    from app.storage import delete_tag

    delete_tag(tag_id)
    _ok(f"Removed tag {tag_id}")


@tags.command("reset")
@click.confirmation_option(
    prompt=(
        "This removes ALL tags and clears dietary tag associations from every dish.\n"
        "Continue?"
    )
)
def tags_reset() -> None:
    """Reset the tag library to the built-in defaults."""
    from app.storage import reset_tags_to_defaults

    reset_tags_to_defaults()
    _ok("Tag library reset to defaults.")


# ── admin events ──────────────────────────────────────────────────────────────

@admin.group()
def events() -> None:
    """View and manage events."""


@events.command("list")
def events_list() -> None:
    """List all events."""
    from app.storage import load_dishes_for_event, load_events

    event_list = load_events()
    if not event_list:
        click.echo("No events found.")
        return

    header = f"  {'ID':>3}  {'Name':<32}  {'Date':<12}  {'Status':<8}  Dishes"
    click.echo(click.style(header, bold=True))
    click.echo("  " + "─" * (len(header) - 2))
    for event in event_list:
        dishes = load_dishes_for_event(event.id)
        status = click.style("Open  ", fg="green") if event.is_active else click.style("Closed", fg="yellow")
        date_str = str(event.event_date) if event.event_date else "—"
        click.echo(
            f"  {event.id:>3}  {event.name:<32}  {date_str:<12}  {status}  {len(dishes)}"
        )


@events.command("delete")
@click.argument("event_id", type=int)
@click.confirmation_option(prompt="Delete this event and all its dishes?")
def events_delete(event_id: int) -> None:
    """Delete an event and all its dishes by ID."""
    from app.storage import delete_event

    delete_event(event_id)
    _ok(f"Deleted event {event_id}")
