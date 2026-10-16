"""Data models for DishList."""

from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel, Field


def _current_utc() -> datetime:
    return datetime.now(UTC)


class DishEntry(BaseModel):
    id: int | None = None
    event_id: int | None = None
    contributor: str = Field(..., min_length=1, max_length=80)
    dish_name: str = Field(..., min_length=1, max_length=120)
    dish_type: str
    tag_ids: list[int] = Field(default_factory=list)
    tags: list[Tag] = Field(default_factory=list)
    notes: str | None = None
    is_host_item: bool = False
    created_at: datetime = Field(default_factory=_current_utc)


class Tag(BaseModel):
    id: int
    name: str
    category: str
    position: int
    keywords: list[str] = Field(default_factory=list)
    is_hidden: bool = False


class Event(BaseModel):
    id: int
    slug: str
    management_token: str
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None
    event_date: date | None = None
    host_name: str = Field(default="The House", min_length=1, max_length=80)
    dish_types: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=_current_utc)
