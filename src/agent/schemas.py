from __future__ import annotations
from datetime import date as date_
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class Category(str, Enum):
    ACADEMIC = "academic"
    EVENT = "event"
    ADMIN = "admin"
    SECURITY = "security"
    OTHER = "other"


class Audience(str, Enum):
    STUDENTS = "students"
    STAFF = "staff"
    ALL = "all"


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Item(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    category: Category
    audience: Audience
    urgency: Urgency
    date: date_
    summary: str = Field(..., min_length=10, max_length=500)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("title", "summary")
    @classmethod
    def no_injection_markers(cls, v: str) -> str:
        banned = ("ignore previous", "ignore rules", "system:", "you are now")
        low = v.lower()
        if any(b in low for b in banned):
            raise ValueError("possible prompt injection detected in field")
        return v.strip()


class ItemBatch(BaseModel):
    items: list[Item]
