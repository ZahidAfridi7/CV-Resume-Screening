"""Screening request/response schemas."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RankRequest(BaseModel):
    jd_id: UUID
    batch_id: UUID | None = None
    limit: int = 50
    min_score: float | None = None


class RankedResumeItem(BaseModel):
    resume_id: UUID
    filename: str
    similarity_score: float
    rank_position: int
    batch_id: UUID


class RankResponse(BaseModel):
    run_id: UUID
    jd_id: UUID
    total_count: int
    results: list[RankedResumeItem]


class ScreeningRunListItem(BaseModel):
    id: UUID
    jd_id: UUID
    batch_id: UUID | None
    created_at: datetime
    result_count: int = 0

    class Config:
        from_attributes = True


class PaginatedRuns(BaseModel):
    items: list[ScreeningRunListItem]
    total: int
    page: int
    page_size: int
    pages: int


class ScreeningResultItem(BaseModel):
    resume_id: UUID
    filename: str
    similarity_score: float
    rank_position: int

    class Config:
        from_attributes = True


class RunDetailResponse(BaseModel):
    id: UUID
    jd_id: UUID
    batch_id: UUID | None
    created_at: datetime
    results: list[ScreeningResultItem] = Field(default_factory=list)
    total: int = 0

    class Config:
        from_attributes = True
