"""Data models for DishList."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DishEntry(BaseModel):
    contributor: str = Field(..., min_length=1, max_length=80)
    dish_name: str = Field(..., min_length=1, max_length=120)
    dish_type: str
    allergens: List[str] = Field(default_factory=list)
    dietary_flags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
