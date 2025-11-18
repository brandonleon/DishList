from __future__ import annotations

import ipaddress
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import AppConfig, load_config, save_config
from .models import DishEntry
from .storage import (
    add_dish,
    create_tag,
    delete_dish,
    delete_tag,
    get_dish,
    get_tag_categories,
    get_tags_by_ids,
    init_db,
    load_dishes,
    load_tag_groups,
    update_dish,
)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

ADMIN_PATH = "/pantry-admin"

app = FastAPI(title="DishList")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

PLANT_BASED_FLAGS = {"vegan", "vegetarian"}
ALLERGEN_FREE_FLAGS = {"gluten-free", "dairy-free"}


def _dietary_badge_class(flag: str) -> str:
    """Return the Bootstrap badge classes for a dietary flag."""

    normalized = flag.strip().lower()
    if normalized in PLANT_BASED_FLAGS:
        return "bg-success-subtle text-success"
    if normalized in ALLERGEN_FREE_FLAGS:
        return "bg-info-subtle text-info"
    return "bg-secondary-subtle text-secondary"


templates.env.filters["dietary_badge_class"] = _dietary_badge_class


def _format_dish_timestamp(value: datetime | str) -> str:
    """Render timestamps in the server's local timezone."""

    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local_dt = parsed.astimezone()
    return local_dt.strftime("%b %d, %Y %I:%M %p")


templates.env.filters["format_dish_timestamp"] = _format_dish_timestamp


@app.on_event("startup")
def _startup() -> None:
    init_db()
    app.state.config = load_config()


def get_config() -> AppConfig:
    return getattr(app.state, "config", load_config())


def _parse_allergens(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [chunk.strip() for chunk in raw.split(",") if chunk.strip()]


def _normalize_tag_ids(raw_ids: List[int]) -> List[int]:
    seen = set()
    normalized: List[int] = []
    for tag_id in raw_ids:
        if tag_id in seen:
            continue
        seen.add(tag_id)
        normalized.append(tag_id)
    return normalized


def _filter_dishes(dishes: List[DishEntry], query: str) -> List[DishEntry]:
    search = query.strip().lower()
    if not search:
        return dishes

    filtered: List[DishEntry] = []
    for dish in dishes:
        searchable_chunks = [
            dish.dish_name,
            dish.contributor,
            dish.dish_type,
            dish.notes or "",
            ", ".join(dish.allergens),
            ", ".join(dish.dietary_flags),
        ]
        for chunk in searchable_chunks:
            if chunk and search in chunk.lower():
                filtered.append(dish)
                break
    return filtered


def _is_ip_allowed(request: Request, config: AppConfig) -> bool:
    client_host = request.client.host if request.client else "127.0.0.1"
    try:
        client_ip = ipaddress.ip_address(client_host)
    except ValueError:
        return False

    for network in config.admin_networks:
        try:
            if client_ip in ipaddress.ip_network(network, strict=False):
                return True
        except ValueError:
            continue
    return False


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    view_mode = request.query_params.get("view", "cards")
    if view_mode not in {"cards", "table"}:
        view_mode = "cards"

    dishes = load_dishes()
    search_query = request.query_params.get("search", "").strip()
    filtered_dishes = _filter_dishes(dishes, search_query) if search_query else dishes
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "dishes": dishes,
            "dish_types": get_config().dish_types,
            "admin_path": ADMIN_PATH,
            "view_mode": view_mode,
            "search_query": search_query,
            "table_dishes": filtered_dishes,
            "card_dishes": filtered_dishes,
        },
    )


@app.get("/add", response_class=HTMLResponse)
def add_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "add.html",
        {
            "request": request,
            "dish_types": get_config().dish_types,
            "admin_path": ADMIN_PATH,
            "tag_groups": load_tag_groups(),
        },
    )


@app.post("/add")
def add_submission(
    request: Request,
    contributor: str = Form(..., min_length=1, max_length=80),
    dish_name: str = Form(..., min_length=1, max_length=120),
    dish_type: str = Form(...),
    allergens: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    dietary_tags: List[int] = Form(default=[]),
) -> RedirectResponse:
    config = get_config()
    if dish_type not in config.dish_types:
        raise HTTPException(status_code=400, detail="Unknown dish type")

    tag_ids = _normalize_tag_ids(dietary_tags)
    tags = get_tags_by_ids(tag_ids)
    if len(tags) != len(tag_ids):
        raise HTTPException(status_code=400, detail="Unknown dietary tag selected")

    entry = DishEntry(
        contributor=contributor.strip(),
        dish_name=dish_name.strip(),
        dish_type=dish_type,
        allergens=_parse_allergens(allergens),
        dietary_flags=[tag.name for tag in tags],
        tag_ids=[tag.id for tag in tags],
        notes=notes.strip() if notes else None,
    )
    add_dish(entry)
    return RedirectResponse(url=request.url_for("home"), status_code=status.HTTP_303_SEE_OTHER)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    # Serve the uploaded favicon from the static directory for browser requests.
    return FileResponse(STATIC_DIR / "favicon.ico", media_type="image/x-icon")


@app.get("/table/rows", response_class=HTMLResponse)
def table_rows_partial(request: Request, search: str = "") -> HTMLResponse:
    dishes = load_dishes()
    filtered = _filter_dishes(dishes, search)
    return templates.TemplateResponse(
        "partials/table_rows.html", {"request": request, "table_dishes": filtered}
    )


@app.get("/cards/grid", response_class=HTMLResponse)
def card_grid_partial(request: Request, search: str = "") -> HTMLResponse:
    dishes = load_dishes()
    filtered = _filter_dishes(dishes, search)
    return templates.TemplateResponse(
        "partials/card_grid.html", {"request": request, "card_dishes": filtered}
    )


@app.get(ADMIN_PATH, response_class=HTMLResponse)
def admin_page(request: Request) -> HTMLResponse:
    config = get_config()
    if not _is_ip_allowed(request, config):
        raise HTTPException(status_code=403, detail="Admin access restricted")

    tag_success = request.query_params.get("tag_success")
    tag_error = request.query_params.get("tag_error")
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "config": config,
            "dishes": load_dishes(),
            "admin_path": ADMIN_PATH,
            "tag_groups": load_tag_groups(),
            "tag_categories": get_tag_categories(),
            "tag_success": tag_success,
            "tag_error": tag_error,
        },
    )


@app.post(ADMIN_PATH)
def update_admin_settings(
    request: Request,
    dish_types_input: str = Form(...),
    admin_networks_input: str = Form(...),
) -> RedirectResponse:
    config = get_config()
    if not _is_ip_allowed(request, config):
        raise HTTPException(status_code=403, detail="Admin access restricted")

    dish_types = [line.strip() for line in dish_types_input.splitlines() if line.strip()]
    networks = [line.strip() for line in admin_networks_input.splitlines() if line.strip()]

    if not dish_types:
        raise HTTPException(status_code=400, detail="At least one dish type is required")
    if not networks:
        raise HTTPException(status_code=400, detail="At least one network is required")

    new_config = AppConfig(dish_types=dish_types, admin_networks=networks)
    save_config(new_config)
    app.state.config = new_config

    return RedirectResponse(url=request.url_for("admin_page"), status_code=status.HTTP_303_SEE_OTHER)


@app.post(f"{ADMIN_PATH}/tags")
def add_tag_action(
    request: Request,
    tag_name: str = Form(..., min_length=1, max_length=120),
    tag_category: str = Form(...),
) -> RedirectResponse:
    config = get_config()
    if not _is_ip_allowed(request, config):
        raise HTTPException(status_code=403, detail="Admin access restricted")

    try:
        create_tag(tag_name, tag_category)
    except ValueError as exc:
        return _redirect_to_admin(request, error=str(exc))
    return _redirect_to_admin(request, success="Tag added")


@app.post(f"{ADMIN_PATH}/tags/{{tag_id}}/delete")
def delete_tag_action(request: Request, tag_id: int) -> RedirectResponse:
    config = get_config()
    if not _is_ip_allowed(request, config):
        raise HTTPException(status_code=403, detail="Admin access restricted")

    delete_tag(tag_id)
    return _redirect_to_admin(request, success="Tag removed")


def _get_dish_or_404(dish_id: int) -> DishEntry:
    dish = get_dish(dish_id)
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")
    return dish


def _redirect_to_admin(request: Request, success: Optional[str] = None, error: Optional[str] = None) -> RedirectResponse:
    target = request.url_for("admin_page")
    params = {}
    if success:
        params["tag_success"] = success
    if error:
        params["tag_error"] = error
    if params:
        target = f"{target}?{urlencode(params)}"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


@app.get(f"{ADMIN_PATH}/dishes/{{dish_id}}", response_class=HTMLResponse)
def edit_dish_form(request: Request, dish_id: int) -> HTMLResponse:
    config = get_config()
    if not _is_ip_allowed(request, config):
        raise HTTPException(status_code=403, detail="Admin access restricted")

    dish = _get_dish_or_404(dish_id)
    return templates.TemplateResponse(
        "admin_edit_dish.html",
        {
            "request": request,
            "dish": dish,
            "dish_types": config.dish_types,
            "admin_path": ADMIN_PATH,
            "tag_groups": load_tag_groups(),
        },
    )


@app.post(f"{ADMIN_PATH}/dishes/{{dish_id}}")
def edit_dish_submit(
    request: Request,
    dish_id: int,
    contributor: str = Form(..., min_length=1, max_length=80),
    dish_name: str = Form(..., min_length=1, max_length=120),
    dish_type: str = Form(...),
    allergens: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    dietary_tags: List[int] = Form(default=[]),
) -> RedirectResponse:
    config = get_config()
    if not _is_ip_allowed(request, config):
        raise HTTPException(status_code=403, detail="Admin access restricted")

    dish = _get_dish_or_404(dish_id)
    if dish_type not in config.dish_types:
        raise HTTPException(status_code=400, detail="Unknown dish type")

    tag_ids = _normalize_tag_ids(dietary_tags)
    tags = get_tags_by_ids(tag_ids)
    if len(tags) != len(tag_ids):
        raise HTTPException(status_code=400, detail="Unknown dietary tag selected")

    updated = dish.model_copy(
        update={
            "contributor": contributor.strip(),
            "dish_name": dish_name.strip(),
            "dish_type": dish_type,
            "allergens": _parse_allergens(allergens),
            "dietary_flags": [tag.name for tag in tags],
            "tag_ids": [tag.id for tag in tags],
            "notes": notes.strip() if notes else None,
        }
    )
    update_dish(dish_id, updated)
    return RedirectResponse(url=request.url_for("admin_page"), status_code=status.HTTP_303_SEE_OTHER)


@app.post(f"{ADMIN_PATH}/dishes/{{dish_id}}/delete")
def delete_dish_action(request: Request, dish_id: int) -> RedirectResponse:
    config = get_config()
    if not _is_ip_allowed(request, config):
        raise HTTPException(status_code=403, detail="Admin access restricted")

    _get_dish_or_404(dish_id)
    delete_dish(dish_id)
    return RedirectResponse(url=request.url_for("admin_page"), status_code=status.HTTP_303_SEE_OTHER)
