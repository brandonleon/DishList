from __future__ import annotations

import ipaddress
import json
import os
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlencode
from importlib import metadata

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore

from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import AppConfig, DATA_DIR, load_config, save_config
from .metrics import (
    DISHES_TOTAL,
    EVENTS_TOTAL,
    PrometheusMiddleware,
    render_metrics,
)
from .models import DishEntry, Event
from .storage import (
    add_dish,
    create_event,
    create_tag,
    delete_dish,
    delete_event,
    delete_tag,
    get_dish,
    get_tag_counts,
    load_tags,
    reset_tags_to_defaults,
    set_tag_keywords,
    toggle_tag_visibility,
    update_tag,
    get_event_by_management_token,
    get_event_by_slug,
    get_tag_categories,
    get_tags_by_ids,
    init_db,
    load_all_dishes,
    load_dishes_for_event,
    load_events,
    load_tag_groups,
    update_dish,
    update_event,
)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

ADMIN_PATH = "/pantry-admin"
METRICS_PATH = "/metrics"
PID_PATH = DATA_DIR / "dishlist.pid"

app = FastAPI(title="DishList")
app.add_middleware(PrometheusMiddleware, exclude_paths=(METRICS_PATH,))
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

PLANT_BASED_FLAGS = {"vegan", "vegetarian", "pescatarian"}
TAG_CATEGORY_CLASSES = {
    # Current categories
    "Dietary preferences": "tag-pill-patterns",
    "Allergen warnings": "tag-pill-avoidances",
    "Content & serving": "tag-pill-logistics",
    # Legacy
    "Allergens": "tag-pill-avoidances",
    # Legacy category names (kept so old data still renders)
    "Dietary patterns": "tag-pill-patterns",
    "Ingredient avoidances": "tag-pill-avoidances",
    "Preparation and cross-contact": "tag-pill-prep",
    "Additives and content": "tag-pill-additives",
    "Spice and suitability": "tag-pill-spice",
    "Serving logistics": "tag-pill-logistics",
}
DEFAULT_TAG_CLASS = "tag-pill-generic"
APP_VERSION = None


def _dietary_badge_class(flag: str) -> str:
    normalized = flag.strip().lower()
    if normalized in PLANT_BASED_FLAGS:
        return "bg-success-subtle text-success"
    if normalized.startswith("contains "):
        return "bg-warning-subtle text-warning-emphasis"
    return "bg-secondary-subtle text-secondary"


def _tag_category_class(category: str) -> str:
    return TAG_CATEGORY_CLASSES.get(category, DEFAULT_TAG_CLASS)


templates.env.filters["dietary_badge_class"] = _dietary_badge_class


def _format_dish_timestamp(value: datetime | str) -> str:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone().strftime("%b %d, %Y %I:%M %p")


def _load_app_version() -> str:
    try:
        return metadata.version("dishlist")
    except metadata.PackageNotFoundError:
        pyproject = BASE_DIR.parent / "pyproject.toml"
        if tomllib and pyproject.exists():
            try:
                with pyproject.open("rb") as fh:
                    data = tomllib.load(fh)
                return data.get("project", {}).get("version", "0.0.0")
            except Exception:
                return "0.0.0"
        return "0.0.0"


APP_VERSION = _load_app_version()

templates.env.filters["format_dish_timestamp"] = _format_dish_timestamp
templates.env.filters["tag_category_class"] = _tag_category_class
templates.env.globals["app_version"] = APP_VERSION


def _do_reload_config() -> None:
    """Force-refresh the in-memory config from the persisted store."""
    app.state.config = load_config()


def _handle_sigusr1(signum, frame) -> None:  # noqa: ANN001
    """SIGUSR1 handler: reload config without restarting the server."""
    _do_reload_config()


@app.on_event("startup")
def _startup() -> None:
    init_db()
    app.state.config = load_config()
    # Write PID so `dishlist admin reload` can signal us.
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        PID_PATH.write_text(str(os.getpid()))
    except OSError:  # pragma: no cover
        pass
    # Install SIGUSR1 → config reload.
    # Guards: SIGUSR1 absent on Windows; signal() requires the main thread.
    try:
        signal.signal(signal.SIGUSR1, _handle_sigusr1)
    except (OSError, AttributeError, ValueError):
        # ValueError: "signal only works in main thread" (e.g. tests)
        pass


@app.on_event("shutdown")
def _shutdown() -> None:
    try:
        PID_PATH.unlink(missing_ok=True)
    except OSError:  # pragma: no cover
        pass


def get_config() -> AppConfig:
    return getattr(app.state, "config", load_config())


def _parse_allergens(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [chunk.strip() for chunk in raw.split(",") if chunk.strip()]


def _normalize_tag_ids(raw_ids: List[int]) -> List[int]:
    return list(dict.fromkeys(raw_ids))


def _filter_dishes(dishes: List[DishEntry], query: str) -> List[DishEntry]:
    search = query.strip().lower()
    if not search:
        return dishes
    filtered: List[DishEntry] = []
    for dish in dishes:
        searchable = [
            dish.dish_name, dish.contributor, dish.dish_type,
            dish.notes or "", ", ".join(dish.allergens), ", ".join(dish.dietary_flags),
        ]
        if any(search in chunk.lower() for chunk in searchable if chunk):
            filtered.append(dish)
    return filtered


def _check_admin_access(request: Request, config: AppConfig) -> None:
    """Raise 404 if web admin is disabled, 403 if IP is not allowed."""
    if not config.web_admin_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    if not _is_ip_allowed(request, config.admin_networks):
        raise HTTPException(status_code=403, detail="Admin access restricted")


def _check_metrics_access(request: Request, config: AppConfig) -> None:
    """Raise 404 if metrics are disabled, 403 if IP is not allowed."""
    if not config.metrics_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    if not _is_ip_allowed(request, config.metrics_networks):
        raise HTTPException(status_code=403, detail="Metrics access restricted")


def _is_ip_allowed(request: Request, networks: List[str]) -> bool:
    client_host = request.client.host if request.client else "127.0.0.1"
    try:
        client_ip = ipaddress.ip_address(client_host)
    except ValueError:
        return False
    for network in networks:
        try:
            if client_ip in ipaddress.ip_network(network, strict=False):
                return True
        except ValueError:
            continue
    return False


def _get_event_by_slug_or_404(slug: str) -> Event:
    event = get_event_by_slug(slug)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def _get_event_by_token_or_404(token: str) -> Event:
    event = get_event_by_management_token(token)
    if not event:
        raise HTTPException(status_code=404, detail="Management link not found")
    return event


def _get_dish_or_404(dish_id: int) -> DishEntry:
    dish = get_dish(dish_id)
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    return dish


# ── Public routes ──────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
def landing(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "landing.html")


@app.get("/create", response_class=HTMLResponse)
def create_event_form(request: Request) -> HTMLResponse:
    config = get_config()
    return templates.TemplateResponse(
        request, "create_event.html", {"default_dish_types": config.dish_types}
    )


@app.post("/create")
def create_event_submit(
    request: Request,
    name: str = Form(..., min_length=1, max_length=120),
    description: Optional[str] = Form(None),
    event_date: Optional[str] = Form(None),
    host_name: Optional[str] = Form(None),
    dish_types_input: str = Form(...),
    use_random_slug: Optional[str] = Form(None),
    host_item_names: List[str] = Form(default=[]),
    host_item_types: List[str] = Form(default=[]),
    host_item_notes: List[str] = Form(default=[]),
) -> RedirectResponse:
    dish_types = [line.strip() for line in dish_types_input.splitlines() if line.strip()]
    if not dish_types:
        raise HTTPException(status_code=400, detail="At least one dish type is required")

    # Validate event_date if provided
    clean_date: Optional[str] = None
    if event_date and event_date.strip():
        try:
            from datetime import date
            date.fromisoformat(event_date.strip())
            clean_date = event_date.strip()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid event date format")

    event = create_event(
        name=name,
        description=description.strip() if description and description.strip() else None,
        event_date=clean_date,
        host_name=host_name.strip() if host_name and host_name.strip() else "The House",
        dish_types=dish_types,
        use_random_slug=bool(use_random_slug),
    )

    # Add host contributions
    for item_name, item_type, item_notes in zip(host_item_names, host_item_types, host_item_notes):
        item_name = item_name.strip()
        if not item_name:
            continue
        if item_type not in dish_types:
            item_type = dish_types[0]
        add_dish(
            DishEntry(
                event_id=event.id,
                contributor=event.host_name,
                dish_name=item_name,
                dish_type=item_type,
                notes=item_notes.strip() if item_notes and item_notes.strip() else None,
                is_host_item=True,
            )
        )

    return RedirectResponse(
        url=request.url_for("manage_event", token=event.management_token),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.ico", media_type="image/x-icon")


@app.get(METRICS_PATH, include_in_schema=False)
def metrics(request: Request) -> Response:
    config = get_config()
    _check_metrics_access(request, config)

    def _refresh() -> None:
        EVENTS_TOTAL.set(len(load_events()))
        DISHES_TOTAL.set(len(load_all_dishes()))

    return render_metrics(refresh_gauges=_refresh)


# ── Event public routes ────────────────────────────────────────────────────────


@app.get("/e/{slug}", response_class=HTMLResponse)
def event_home(request: Request, slug: str) -> HTMLResponse:
    event = _get_event_by_slug_or_404(slug)
    view_mode = request.query_params.get("view", "cards")
    if view_mode not in {"cards", "table"}:
        view_mode = "cards"
    search_query = request.query_params.get("search", "").strip()

    all_dishes = load_dishes_for_event(event.id)
    host_dishes = [d for d in all_dishes if d.is_host_item]
    guest_dishes = [d for d in all_dishes if not d.is_host_item]
    filtered_guests = _filter_dishes(guest_dishes, search_query) if search_query else guest_dishes

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "event": event,
            "host_dishes": host_dishes,
            "guest_dishes": guest_dishes,
            "table_dishes": filtered_guests,
            "card_dishes": filtered_guests,
            "view_mode": view_mode,
            "search_query": search_query,
        },
    )


@app.get("/e/{slug}/add", response_class=HTMLResponse)
def event_add_form(request: Request, slug: str) -> HTMLResponse:
    event = _get_event_by_slug_or_404(slug)
    if not event.is_active:
        raise HTTPException(status_code=403, detail="This event is no longer accepting submissions")
    tag_groups = load_tag_groups()
    # Build keyword map for client-side auto-detection: {tagId: ["kw1", "kw2"]}
    tag_kw_map = {
        tag.id: tag.keywords
        for _, tags in tag_groups
        for tag in tags
        if tag.keywords
    }
    hidden_count = sum(1 for _, tags in tag_groups for tag in tags if tag.is_hidden)
    return templates.TemplateResponse(
        request,
        "add.html",
        {
            "event": event,
            "dish_types": event.dish_types,
            "tag_groups": tag_groups,
            "tag_keywords_json": json.dumps(tag_kw_map),
            "hidden_tag_count": hidden_count,
        },
    )


@app.post("/e/{slug}/add")
def event_add_submission(
    request: Request,
    slug: str,
    contributor: str = Form(..., min_length=1, max_length=80),
    dish_name: str = Form(..., min_length=1, max_length=120),
    dish_type: str = Form(...),
    allergens: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    dietary_tags: List[int] = Form(default=[]),
) -> RedirectResponse:
    event = _get_event_by_slug_or_404(slug)
    if not event.is_active:
        raise HTTPException(status_code=403, detail="This event is no longer accepting submissions")
    if dish_type not in event.dish_types:
        raise HTTPException(status_code=400, detail="Unknown dish type")

    tag_ids = _normalize_tag_ids(dietary_tags)
    tags = get_tags_by_ids(tag_ids)
    if len(tags) != len(tag_ids):
        raise HTTPException(status_code=400, detail="Unknown dietary tag selected")

    add_dish(
        DishEntry(
            event_id=event.id,
            contributor=contributor.strip(),
            dish_name=dish_name.strip(),
            dish_type=dish_type,
            allergens=_parse_allergens(allergens),
            dietary_flags=[tag.name for tag in tags],
            tag_ids=[tag.id for tag in tags],
            tags=tags,
            notes=notes.strip() if notes else None,
        )
    )
    return RedirectResponse(
        url=request.url_for("event_home", slug=slug),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/e/{slug}/table/rows", response_class=HTMLResponse)
def event_table_rows_partial(request: Request, slug: str, search: str = "") -> HTMLResponse:
    event = _get_event_by_slug_or_404(slug)
    all_dishes = load_dishes_for_event(event.id)
    guest_dishes = [d for d in all_dishes if not d.is_host_item]
    filtered = _filter_dishes(guest_dishes, search)
    return templates.TemplateResponse(
        request, "partials/table_rows.html", {"table_dishes": filtered}
    )


@app.get("/e/{slug}/cards/grid", response_class=HTMLResponse)
def event_card_grid_partial(request: Request, slug: str, search: str = "") -> HTMLResponse:
    event = _get_event_by_slug_or_404(slug)
    all_dishes = load_dishes_for_event(event.id)
    guest_dishes = [d for d in all_dishes if not d.is_host_item]
    filtered = _filter_dishes(guest_dishes, search)
    return templates.TemplateResponse(
        request, "partials/card_grid.html", {"card_dishes": filtered}
    )


# ── Management routes (token-gated) ───────────────────────────────────────────


@app.get("/manage/{token}", response_class=HTMLResponse)
def manage_event(request: Request, token: str) -> HTMLResponse:
    event = _get_event_by_token_or_404(token)
    all_dishes = load_dishes_for_event(event.id)
    host_dishes = [d for d in all_dishes if d.is_host_item]
    guest_dishes = [d for d in all_dishes if not d.is_host_item]
    tag_success = request.query_params.get("tag_success")
    tag_error = request.query_params.get("tag_error")
    return templates.TemplateResponse(
        request,
        "manage.html",
        {
            "event": event,
            "host_dishes": host_dishes,
            "guest_dishes": guest_dishes,
            "tag_groups": load_tag_groups(),
            "tag_categories": get_tag_categories(),
            "tag_success": tag_success,
            "tag_error": tag_error,
        },
    )


@app.post("/manage/{token}")
def update_event_settings(
    request: Request,
    token: str,
    name: str = Form(..., min_length=1, max_length=120),
    description: Optional[str] = Form(None),
    event_date: Optional[str] = Form(None),
    host_name: Optional[str] = Form(None),
    dish_types_input: str = Form(...),
    is_active: Optional[str] = Form(None),
) -> RedirectResponse:
    event = _get_event_by_token_or_404(token)
    dish_types = [line.strip() for line in dish_types_input.splitlines() if line.strip()]
    if not dish_types:
        raise HTTPException(status_code=400, detail="At least one dish type is required")

    clean_date: Optional[str] = None
    if event_date and event_date.strip():
        try:
            from datetime import date
            date.fromisoformat(event_date.strip())
            clean_date = event_date.strip()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid event date format")

    update_event(
        event_id=event.id,
        name=name,
        description=description.strip() if description and description.strip() else None,
        event_date=clean_date,
        host_name=host_name.strip() if host_name and host_name.strip() else "The House",
        dish_types=dish_types,
        is_active=bool(is_active),
    )
    return RedirectResponse(
        url=request.url_for("manage_event", token=token),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/manage/{token}/host-items")
def add_host_item(
    request: Request,
    token: str,
    dish_name: str = Form(..., min_length=1, max_length=120),
    dish_type: str = Form(...),
    allergens: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
) -> RedirectResponse:
    event = _get_event_by_token_or_404(token)
    if dish_type not in event.dish_types:
        raise HTTPException(status_code=400, detail="Unknown dish type")
    add_dish(
        DishEntry(
            event_id=event.id,
            contributor=event.host_name,
            dish_name=dish_name.strip(),
            dish_type=dish_type,
            allergens=_parse_allergens(allergens),
            notes=notes.strip() if notes else None,
            is_host_item=True,
        )
    )
    return RedirectResponse(
        url=request.url_for("manage_event", token=token),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/manage/{token}/host-items/{dish_id}/delete")
def delete_host_item(request: Request, token: str, dish_id: int) -> RedirectResponse:
    event = _get_event_by_token_or_404(token)
    dish = _get_dish_or_404(dish_id)
    if dish.event_id != event.id:
        raise HTTPException(status_code=404, detail="Dish not found")
    delete_dish(dish_id)
    return RedirectResponse(
        url=request.url_for("manage_event", token=token),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/manage/{token}/dishes/{dish_id}", response_class=HTMLResponse)
def manage_edit_dish_form(request: Request, token: str, dish_id: int) -> HTMLResponse:
    event = _get_event_by_token_or_404(token)
    dish = _get_dish_or_404(dish_id)
    if dish.event_id != event.id:
        raise HTTPException(status_code=404, detail="Dish not found")
    return templates.TemplateResponse(
        request,
        "manage_edit_dish.html",
        {
            "event": event,
            "dish": dish,
            "dish_types": event.dish_types,
            "tag_groups": load_tag_groups(),
        },
    )


@app.post("/manage/{token}/dishes/{dish_id}")
def manage_edit_dish_submit(
    request: Request,
    token: str,
    dish_id: int,
    contributor: str = Form(..., min_length=1, max_length=80),
    dish_name: str = Form(..., min_length=1, max_length=120),
    dish_type: str = Form(...),
    allergens: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    dietary_tags: List[int] = Form(default=[]),
) -> RedirectResponse:
    event = _get_event_by_token_or_404(token)
    dish = _get_dish_or_404(dish_id)
    if dish.event_id != event.id:
        raise HTTPException(status_code=404, detail="Dish not found")
    if dish_type not in event.dish_types:
        raise HTTPException(status_code=400, detail="Unknown dish type")

    tag_ids = _normalize_tag_ids(dietary_tags)
    tags = get_tags_by_ids(tag_ids)
    if len(tags) != len(tag_ids):
        raise HTTPException(status_code=400, detail="Unknown dietary tag selected")

    update_dish(
        dish_id,
        dish.model_copy(
            update={
                "contributor": contributor.strip(),
                "dish_name": dish_name.strip(),
                "dish_type": dish_type,
                "allergens": _parse_allergens(allergens),
                "dietary_flags": [tag.name for tag in tags],
                "tag_ids": [tag.id for tag in tags],
                "tags": tags,
                "notes": notes.strip() if notes else None,
            }
        ),
    )
    return RedirectResponse(
        url=request.url_for("manage_event", token=token),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/manage/{token}/dishes/{dish_id}/delete")
def manage_delete_dish(request: Request, token: str, dish_id: int) -> RedirectResponse:
    event = _get_event_by_token_or_404(token)
    dish = _get_dish_or_404(dish_id)
    if dish.event_id != event.id:
        raise HTTPException(status_code=404, detail="Dish not found")
    delete_dish(dish_id)
    return RedirectResponse(
        url=request.url_for("manage_event", token=token),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ── System admin routes (IP-gated) ─────────────────────────────────────────────


def _redirect_to_admin(request: Request, success: Optional[str] = None, error: Optional[str] = None) -> RedirectResponse:
    target = str(request.url_for("admin_page"))
    params = {}
    if success:
        params["tag_success"] = success
    if error:
        params["tag_error"] = error
    if params:
        target = f"{target}?{urlencode(params)}"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


def _redirect_to_admin_tags(request: Request, success: Optional[str] = None, error: Optional[str] = None) -> RedirectResponse:
    target = str(request.url_for("admin_tags_page"))
    params = {}
    if success:
        params["tag_success"] = success
    if error:
        params["tag_error"] = error
    if params:
        target = f"{target}?{urlencode(params)}"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


@app.get(ADMIN_PATH, response_class=HTMLResponse)
def admin_page(request: Request) -> HTMLResponse:
    config = get_config()
    _check_admin_access(request, config)
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "config": config,
            "events": load_events(),
            "admin_path": ADMIN_PATH,
            "tag_counts": get_tag_counts(),
            "admin_tags_url": str(request.url_for("admin_tags_page")),
            "tag_success": request.query_params.get("tag_success"),
            "tag_error": request.query_params.get("tag_error"),
        },
    )


@app.post(f"{ADMIN_PATH}/reload")
def reload_config(request: Request) -> RedirectResponse:
    """Force a config reload from the persisted store into app.state."""
    config = get_config()
    _check_admin_access(request, config)
    _do_reload_config()
    return _redirect_to_admin(request, success="Configuration reloaded")


@app.get(f"{ADMIN_PATH}/tags", response_class=HTMLResponse)
def admin_tags_page(request: Request) -> HTMLResponse:
    config = get_config()
    _check_admin_access(request, config)
    tag_success = request.query_params.get("tag_success")
    tag_error = request.query_params.get("tag_error")
    return templates.TemplateResponse(
        request,
        "admin_tags.html",
        {
            "admin_path": ADMIN_PATH,
            "tag_groups": load_tag_groups(),
            "tag_categories": get_tag_categories(),
            "tag_counts": get_tag_counts(),
            "tag_success": tag_success,
            "tag_error": tag_error,
        },
    )


@app.post(ADMIN_PATH)
def update_admin_settings(
    request: Request,
    dish_types_input: str = Form(...),
    admin_networks_input: str = Form(...),
    metrics_networks_input: Optional[str] = Form(None),
) -> RedirectResponse:
    config = get_config()
    _check_admin_access(request, config)

    dish_types = [line.strip() for line in dish_types_input.splitlines() if line.strip()]
    networks = [line.strip() for line in admin_networks_input.splitlines() if line.strip()]
    if not dish_types:
        raise HTTPException(status_code=400, detail="At least one dish type is required")
    if not networks:
        raise HTTPException(status_code=400, detail="At least one network is required")

    if metrics_networks_input is not None:
        metrics_networks = [
            line.strip() for line in metrics_networks_input.splitlines() if line.strip()
        ]
    else:
        metrics_networks = config.metrics_networks

    new_config = AppConfig(
        dish_types=dish_types,
        admin_networks=networks,
        web_admin_enabled=config.web_admin_enabled,
        metrics_networks=metrics_networks,
        metrics_enabled=config.metrics_enabled,
    )
    save_config(new_config)
    app.state.config = new_config
    return RedirectResponse(url=request.url_for("admin_page"), status_code=status.HTTP_303_SEE_OTHER)


@app.post(f"{ADMIN_PATH}/tags")
def add_tag_action(
    request: Request,
    tag_name: str = Form(..., min_length=1, max_length=120),
    tag_category: str = Form(...),
    tag_keywords: Optional[str] = Form(None),
    tag_is_hidden: Optional[str] = Form(None),  # checkbox: present = hidden
) -> RedirectResponse:
    config = get_config()
    _check_admin_access(request, config)
    keywords = [kw.strip() for kw in (tag_keywords or "").split(",") if kw.strip()]
    try:
        create_tag(tag_name, tag_category, keywords=keywords or None, is_hidden=tag_is_hidden is not None)
    except ValueError as exc:
        return _redirect_to_admin_tags(request, error=str(exc))
    return _redirect_to_admin_tags(request, success="Tag added")


@app.post(f"{ADMIN_PATH}/tags/{{tag_id}}")
def update_tag_action(
    request: Request,
    tag_id: int,
    name: str = Form(...),
    category: str = Form(...),
    keywords: Optional[str] = Form(None),
    is_hidden: Optional[str] = Form(None),  # checkbox: present = hidden
) -> RedirectResponse:
    config = get_config()
    _check_admin_access(request, config)
    keyword_list = [kw.strip() for kw in (keywords or "").split(",") if kw.strip()]
    try:
        update_tag(tag_id, name, category, keywords=keyword_list, is_hidden=is_hidden is not None)
    except ValueError as exc:
        return _redirect_to_admin_tags(request, error=str(exc))
    return _redirect_to_admin_tags(request, success="Tag updated")


@app.post(f"{ADMIN_PATH}/tags/reset")
def reset_tags_action(request: Request) -> RedirectResponse:
    config = get_config()
    _check_admin_access(request, config)
    reset_tags_to_defaults()
    return _redirect_to_admin_tags(request, success="Tag library reset to defaults")


@app.post(f"{ADMIN_PATH}/tags/{{tag_id}}/delete")
def delete_tag_action(request: Request, tag_id: int) -> RedirectResponse:
    config = get_config()
    _check_admin_access(request, config)
    delete_tag(tag_id)
    return _redirect_to_admin_tags(request, success="Tag removed")


@app.post(f"{ADMIN_PATH}/tags/{{tag_id}}/visibility")
def toggle_tag_visibility_action(request: Request, tag_id: int) -> RedirectResponse:
    config = get_config()
    _check_admin_access(request, config)
    try:
        toggle_tag_visibility(tag_id)
    except ValueError as exc:
        return _redirect_to_admin_tags(request, error=str(exc))
    return _redirect_to_admin_tags(request, success="Tag visibility updated")


@app.post(f"{ADMIN_PATH}/events/{{event_id}}/delete")
def admin_delete_event(request: Request, event_id: int) -> RedirectResponse:
    config = get_config()
    _check_admin_access(request, config)
    delete_event(event_id)
    return RedirectResponse(url=request.url_for("admin_page"), status_code=status.HTTP_303_SEE_OTHER)
