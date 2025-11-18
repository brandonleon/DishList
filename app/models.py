"""Data models for DishList."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


def _current_utc() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class DishEntry(BaseModel):
    id: Optional[int] = None
    contributor: str = Field(..., min_length=1, max_length=80)
    dish_name: str = Field(..., min_length=1, max_length=120)
    dish_type: str
    allergens: List[str] = Field(default_factory=list)
    dietary_flags: List[str] = Field(default_factory=list)
    tag_ids: List[int] = Field(default_factory=list)
    tags: List["Tag"] = Field(default_factory=list)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=_current_utc)


class Tag(BaseModel):
    id: int
    name: str
    category: str
    position: int
