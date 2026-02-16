"""Job description schemas."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class JobDescriptionCreate(BaseModel):
    title: str
    raw_text: str


class JobDescriptionResponse(BaseModel):
    id: UUID
    title: str
    raw_text: str
    created_at: datetime

    class Config:
        from_attributes = True


class JobDescriptionListItem(BaseModel):
    id: UUID
    title: str
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedJDs(BaseModel):
    items: list[JobDescriptionListItem]
    total: int
    page: int
    page_size: int
    pages: int
