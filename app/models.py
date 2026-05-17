"""Data models for DishList."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


def _current_utc() -> datetime:
    return datetime.now(timezone.utc)


class DishEntry(BaseModel):
    id: Optional[int] = None
    event_id: Optional[int] = None
    contributor: str = Field(..., min_length=1, max_length=80)
    dish_name: str = Field(..., min_length=1, max_length=120)
    dish_type: str
    allergens: List[str] = Field(default_factory=list)
    dietary_flags: List[str] = Field(default_factory=list)
    tag_ids: List[int] = Field(default_factory=list)
    tags: List["Tag"] = Field(default_factory=list)
    notes: Optional[str] = None
    is_host_item: bool = False
    created_at: datetime = Field(default_factory=_current_utc)


class Tag(BaseModel):
    id: int
    name: str
    category: str
    position: int
    keywords: List[str] = Field(default_factory=list)
    is_hidden: bool = False


class Event(BaseModel):
    id: Optional[int] = None
    slug: str
    management_token: str
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = None
    event_date: Optional[date] = None
    host_name: str = Field(default="The House", min_length=1, max_length=80)
    dish_types: List[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=_current_utc)
