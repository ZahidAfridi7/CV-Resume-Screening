"""Upload and batch schemas."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BatchCreateResponse(BaseModel):
    batch_id: UUID
    status: str = "pending"
    file_count: int


class ResumeSummary(BaseModel):
    id: UUID
    filename: str
    status: str
    similarity_score: float | None = None
    rank_position: int | None = None

    class Config:
        from_attributes = True


class BatchResponse(BaseModel):
    id: UUID
    batch_name: str | None
    status: str
    created_at: datetime
    resume_count: int = 0
    resumes: list[ResumeSummary] = Field(default_factory=list)

    class Config:
        from_attributes = True


class BatchListItem(BaseModel):
    id: UUID
    batch_name: str | None
    status: str
    created_at: datetime
    resume_count: int

    class Config:
        from_attributes = True


class PaginatedBatches(BaseModel):
    items: list[BatchListItem]
    total: int
    page: int
    page_size: int
    pages: int
