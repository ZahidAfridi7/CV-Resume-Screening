"""Job descriptions: create, list, get one."""
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_async_session
from app.models.user import User
from app.repositories.jd_repository import JobDescriptionRepository
from app.schemas.common import PaginationParams, get_pagination
from app.schemas.job_descriptions import (
    JobDescriptionCreate,
    JobDescriptionListItem,
    JobDescriptionResponse,
    PaginatedJDs,
)
from app.core.embedding_errors import EmbeddingUnavailableError
from app.services.embedding import EmbeddingService

router = APIRouter()


@router.post("", response_model=JobDescriptionResponse)
async def create_jd(
    body: JobDescriptionCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> JobDescriptionResponse:
    embedding = None
    try:
        embedding_svc = EmbeddingService()
        embedding = await embedding_svc.embed_text_async(body.raw_text)
    except EmbeddingUnavailableError:
        pass
    jd = await JobDescriptionRepository.create(
        session, current_user.id, body.title, body.raw_text, embedding=embedding
    )
    await session.commit()
    return JobDescriptionResponse(id=jd.id, title=jd.title, raw_text=jd.raw_text, created_at=jd.created_at)


@router.post("/from-form", response_model=JobDescriptionResponse)
async def create_jd_from_form(
    title: str = Form(..., description="Job title"),
    raw_text: str = Form(..., description="Full job description text (multi-line supported)"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> JobDescriptionResponse:
    """Create a JD from form data. Use this in Swagger UI when pasting multi-line job descriptions."""
    embedding = None
    try:
        embedding_svc = EmbeddingService()
        embedding = await embedding_svc.embed_text_async(raw_text)
    except EmbeddingUnavailableError:
        pass
    jd = await JobDescriptionRepository.create(
        session, current_user.id, title, raw_text, embedding=embedding
    )
    await session.commit()
    return JobDescriptionResponse(id=jd.id, title=jd.title, raw_text=jd.raw_text, created_at=jd.created_at)


@router.get("", response_model=PaginatedJDs)
async def list_jds(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    pagination: PaginationParams = Depends(get_pagination),
) -> PaginatedJDs:
    items, total = await JobDescriptionRepository.list_for_user(
        session, current_user.id, page=pagination.page, page_size=pagination.page_size
    )
    list_items = [JobDescriptionListItem(id=j.id, title=j.title, created_at=j.created_at) for j in items]
    pages = (total + pagination.page_size - 1) // pagination.page_size if total else 0
    return PaginatedJDs(items=list_items, total=total, page=pagination.page, page_size=pagination.page_size, pages=pages)


@router.get("/{jd_id}", response_model=JobDescriptionResponse)
async def get_jd(
    jd_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> JobDescriptionResponse:
    jd = await JobDescriptionRepository.get_by_id(session, jd_id)
    if not jd or jd.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job description not found")
    return JobDescriptionResponse(id=jd.id, title=jd.title, raw_text=jd.raw_text, created_at=jd.created_at)
