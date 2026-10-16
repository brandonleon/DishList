"""DishList command-line management tool.

Usage:
    dishlist serve                        Start the web server
    dishlist db upgrade                   Apply pending database migrations
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
    dishlist admin events token <id>      Print the management URL for an event
    dishlist admin events delete <id>     Delete an event and all its dishes
    dishlist admin metrics status         Show /metrics endpoint status
    dishlist admin metrics enable         Enable the Prometheus /metrics endpoint
    dishlist admin metrics disable        Disable the Prometheus /metrics endpoint
    dishlist admin metrics networks list  List allowed metrics scrape networks
    dishlist admin metrics networks add <cidr>
    dishlist admin metrics networks remove <cidr>

Every command that touches data uses the PostgreSQL database named by the
DATABASE_URL environment variable, so a remote deployment can be managed from
any machine by pointing DATABASE_URL at its database.
"""

from __future__ import annotations

import ipaddress
import sys

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
        ) from None


# ── Root ──────────────────────────────────────────────────────────────────────


class _Cli(click.Group):
    def invoke(self, ctx: click.Context):
        from app.config import DatabaseNotConfiguredError
        from app.storage import close_pool

        try:
            return super().invoke(ctx)
        except DatabaseNotConfiguredError as exc:
            _err(str(exc))
            ctx.exit(1)
        finally:
            # Release the pool's worker threads, or exit waits ~5s on each.
            close_pool()


@click.group(cls=_Cli)
def cli() -> None:
    """DishList — potluck planner management CLI."""


# ── serve ─────────────────────────────────────────────────────────────────────


@cli.command()
@click.option(
    "--host",
    default="0.0.0.0",  # noqa: S104 - container-friendly default; binding is the operator's choice
    show_default=True,
    help="Bind address.",
)
@click.option("--port", default=8000, show_default=True, help="Bind port.")
@click.option(
    "--reload/--no-reload",
    default=None,
    help="Enable live reload (default: on unless DISHLIST_RELOAD=0).",
)
@click.option(
    "--forwarded-allow-ips",
    default=None,
    help=(
        "Comma-separated proxy IPs trusted for X-Forwarded-* headers "
        "(default: $FORWARDED_ALLOW_IPS, else '*' = trust any proxy)."
    ),
)
def serve(
    host: str, port: int, reload: bool | None, forwarded_allow_ips: str | None
) -> None:
    """Start the DishList web server."""
    import os

    import uvicorn

    if reload is None:
        raw = os.getenv("DISHLIST_RELOAD")
        reload = raw is None or raw.lower() in {"1", "true", "yes", "on"}
    trusted_proxies = forwarded_allow_ips or os.getenv("FORWARDED_ALLOW_IPS") or "*"

    click.echo(f"Starting DishList on http://{host}:{port}")
    try:
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=reload,
            proxy_headers=True,
            forwarded_allow_ips=trusted_proxies,
        )
    except PermissionError:
        if not reload:
            raise
        click.echo("Live reload blocked; starting without reload.", err=True)
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=False,
            proxy_headers=True,
            forwarded_allow_ips=trusted_proxies,
        )


# ── db ────────────────────────────────────────────────────────────────────────


@cli.group()
def db() -> None:
    """Manage the database schema."""


@db.command("upgrade")
def db_upgrade() -> None:
    """Apply pending schema migrations to the DATABASE_URL database."""
    from app import migrations
    from app.config import database_url
    from app.storage import current_schema_revision

    url = database_url()
    before = current_schema_revision()
    head = migrations.head_revision()
    if before == head:
        _ok(f"Database is already at the latest revision ({head}).")
        return
    click.echo(f"Upgrading database from {before or 'empty'} to {head}…")
    try:
        migrations.upgrade(url)
    except Exception as exc:  # noqa: BLE001 - report any migration failure, then exit non-zero
        after = current_schema_revision()
        _err(f"Migration failed: {exc}")
        click.echo(f"  Database left at revision {after or 'empty'}.", err=True)
        sys.exit(1)
    after = current_schema_revision()
    _ok(f"Database upgraded to {after}.")


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
            click.style("               Run: ", dim=True) + "dishlist admin web enable"
        )
    click.echo(f"  Events       {len(events)}")
    click.echo()

    click.echo(click.style("Allowed admin networks:", bold=True))
    for net in config.admin_networks:
        click.echo(f"  • {net}")
    click.echo()

    metrics_label = (
        click.style("enabled", fg="green")
        if config.metrics_enabled
        else click.style("disabled", fg="yellow")
    )
    click.echo(f"  Metrics      {metrics_label}")
    if not config.metrics_enabled:
        click.echo(
            click.style("               Run: ", dim=True)
            + "dishlist admin metrics enable"
        )
    click.echo(click.style("Allowed metrics networks:", bold=True))
    if config.metrics_networks:
        for net in config.metrics_networks:
            click.echo(f"  • {net}")
    else:
        click.echo("  (none — endpoint will reject all clients)")
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
def web_enable(network: str | None) -> None:
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
        status = (
            click.style("Open  ", fg="green")
            if event.is_active
            else click.style("Closed", fg="yellow")
        )
        date_str = str(event.event_date) if event.event_date else "—"
        click.echo(
            f"  {event.id:>3}  {event.name:<32}  {date_str:<12}  {status}  {len(dishes)}"
        )


@events.command("token")
@click.argument("event_id", type=int)
def events_token(event_id: int) -> None:
    """Print the management URL path for an event (for token recovery)."""
    from app.storage import get_event_by_id

    event = get_event_by_id(event_id)
    if not event:
        _err(f"No event found with ID {event_id}.")
        sys.exit(1)

    click.echo(f"  Event:  {event.name}")
    click.echo(f"  Path:   /manage/{event.management_token}")
    click.echo(
        click.style(
            "  Prepend your server's base URL to get the full management link.",
            dim=True,
        )
    )


@events.command("delete")
@click.argument("event_id", type=int)
@click.confirmation_option(prompt="Delete this event and all its dishes?")
def events_delete(event_id: int) -> None:
    """Delete an event and all its dishes by ID."""
    from app.storage import delete_event

    delete_event(event_id)
    _ok(f"Deleted event {event_id}")


# ── admin metrics ─────────────────────────────────────────────────────────────


@admin.group()
def metrics() -> None:
    """Enable, disable, and gate the Prometheus /metrics endpoint."""


@metrics.command("status")
def metrics_status() -> None:
    """Show the /metrics endpoint state and its IP allowlist."""
    config = _load()
    state = (
        click.style("enabled", fg="green")
        if config.metrics_enabled
        else click.style("disabled", fg="yellow")
    )
    click.echo(f"  /metrics  {state}")
    click.echo()
    click.echo(click.style("Allowed metrics networks:", bold=True))
    if not config.metrics_networks:
        click.echo("  (none — endpoint will reject every client)")
    else:
        for net in config.metrics_networks:
            click.echo(f"  • {net}")


@metrics.command("enable")
@click.option(
    "--network",
    default=None,
    metavar="IP_OR_CIDR",
    help="Add an IP or CIDR to the metrics allowlist at the same time.",
)
def metrics_enable(network: str | None) -> None:
    """Enable the Prometheus /metrics endpoint."""
    config = _load()

    if network:
        network = _validate_network(network)
        if network not in config.metrics_networks:
            config.metrics_networks.append(network)
            _ok(f"Added metrics network: {network}")

    if not config.metrics_networks:
        _err(
            "No allowed metrics networks configured.\n"
            "       Add one first:  dishlist admin metrics networks add <ip-or-cidr>\n"
            "       Or combine:     dishlist admin metrics enable --network 10.0.0.5"
        )
        sys.exit(1)

    config.metrics_enabled = True
    _save(config)
    _ok("Prometheus /metrics enabled")
    click.echo(f"  Allowed from: {', '.join(config.metrics_networks)}")


@metrics.command("disable")
def metrics_disable() -> None:
    """Disable the Prometheus /metrics endpoint."""
    config = _load()
    config.metrics_enabled = False
    _save(config)
    _ok("Prometheus /metrics disabled.")


@metrics.group("networks")
def metrics_networks_group() -> None:
    """Manage IP addresses and CIDR ranges allowed to scrape /metrics."""


@metrics_networks_group.command("list")
def metrics_networks_list() -> None:
    """List allowed metrics networks."""
    config = _load()
    if not config.metrics_networks:
        click.echo("No metrics networks configured.")
        return
    click.echo(click.style("Allowed metrics networks:", bold=True))
    for net in config.metrics_networks:
        click.echo(f"  {net}")


@metrics_networks_group.command("add")
@click.argument("network")
def metrics_networks_add(network: str) -> None:
    """Add an IP address or CIDR range to the metrics allowlist."""
    network = _validate_network(network)
    config = _load()
    if network in config.metrics_networks:
        click.echo(f"'{network}' is already in the metrics allowlist.")
        return
    config.metrics_networks.append(network)
    _save(config)
    _ok(f"Added {network}")


@metrics_networks_group.command("remove")
@click.argument("network")
def metrics_networks_remove(network: str) -> None:
    """Remove an IP address or CIDR range from the metrics allowlist."""
    network = _validate_network(network)
    config = _load()
    if network not in config.metrics_networks:
        _err(f"'{network}' is not in the metrics allowlist.")
        sys.exit(1)
    config.metrics_networks.remove(network)
    _save(config)
    _ok(f"Removed {network}")
