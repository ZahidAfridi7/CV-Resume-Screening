"""Upload batch: create batch (multipart), list batches, get batch detail."""
import asyncio
import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.core.rate_limit import get_user_or_ip_key, limiter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.db.session import get_async_session
from app.models.user import User
from app.repositories.batch_repository import BatchRepository, ResumeRepository
from app.schemas.common import PaginationParams, get_pagination
from app.schemas.uploads import (
    BatchCreateResponse,
    BatchListItem,
    BatchResponse,
    PaginatedBatches,
    ResumeSummary,
)
from app.tasks.process_resume import process_resume_task

router = APIRouter()
settings = get_settings()


def _ensure_upload_dirs() -> None:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.temp_dir).mkdir(parents=True, exist_ok=True)


def _validate_file(file: UploadFile) -> None:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(settings.allowed_extensions)}",
        )
    if file.size and file.size > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max {settings.max_file_size_mb} MB",
        )


@router.post("/batch")
@limiter.limit("10/minute", key_func=get_user_or_ip_key)
async def create_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    batch_name: str | None = Form(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> BatchCreateResponse:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")
    if len(files) > settings.max_files_per_batch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files. Maximum {settings.max_files_per_batch} per batch",
        )
    _ensure_upload_dirs()
    for f in files:
        _validate_file(f)
        if f.size is not None and f.size > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Max {settings.max_file_size_mb} MB",
            )

    batch = await BatchRepository.create(session, current_user.id, batch_name)
    saved_paths: list[tuple[str, int, str]] = []  # (rel_path, size, original_filename)
    for f in files:
        original_name = (f.filename or "document").strip() or "document"
        ext = Path(original_name).suffix.lower() or Path(f.filename or "file").suffix.lower() or ".pdf"
        safe_name = f"{uuid.uuid4().hex}{ext}"
        rel_path = os.path.join(settings.upload_dir, safe_name)
        full_path = Path(rel_path)
        try:
            content = await f.read()
            if len(content) > settings.max_file_size_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File too large",
                )
            size = len(content)
            async with aiofiles.open(full_path, "wb") as out:
                await out.write(content)
            saved_paths.append((rel_path, size, original_name))
        except HTTPException:
            raise
        except Exception:
            for path, _, _ in saved_paths:
                Path(path).unlink(missing_ok=True)
            raise

    resumes_created: list[tuple[str, str]] = []  # (resume_id_str, rel_path)
    for rel_path, size, original_filename in saved_paths:
        resume = await ResumeRepository.create(session, batch.id, original_filename, file_path=rel_path, file_size=size)
        resumes_created.append((str(resume.id), rel_path))

    batch.status = "processing"
    await session.commit()  # Persist before task runs (task needs resume in DB)

    for resume_id_str, rel_path in resumes_created:
        if settings.process_resumes_inline:
            # Process inline (for dev when Celery/Redis not running). Blocks until extraction + embedding done.
            await asyncio.to_thread(process_resume_task, resume_id_str, rel_path)
        else:
            process_resume_task.delay(resume_id_str, rel_path)

    if settings.process_resumes_inline:
        await session.refresh(batch)  # Get batch status set by inline task
    return BatchCreateResponse(batch_id=batch.id, status=batch.status, file_count=len(files))


@router.get("/batches", response_model=PaginatedBatches)
async def list_batches(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    pagination: PaginationParams = Depends(get_pagination),
) -> PaginatedBatches:
    rows, total = await BatchRepository.list_for_user_with_resume_counts(
        session, current_user.id, page=pagination.page, page_size=pagination.page_size
    )
    items = [
        BatchListItem(id=r[0], batch_name=r[1], status=r[2], created_at=r[3], resume_count=r[4])
        for r in rows
    ]
    pages = (total + pagination.page_size - 1) // pagination.page_size if total else 0
    return PaginatedBatches(items=items, total=total, page=pagination.page, page_size=pagination.page_size, pages=pages)


@router.get("/batches/{batch_id}", response_model=BatchResponse)
async def get_batch(
    batch_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> BatchResponse:
    batch = await BatchRepository.get_by_id(session, batch_id)
    if not batch or batch.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    from sqlalchemy import select
    from app.models.upload import Resume
    res = await session.execute(select(Resume).where(Resume.batch_id == batch_id))
    resumes = list(res.scalars().all())
    resume_summaries = [
        ResumeSummary(id=r.id, filename=r.filename, status=r.status)
        for r in resumes
    ]
    return BatchResponse(
        id=batch.id,
        batch_name=batch.batch_name,
        status=batch.status,
        created_at=batch.created_at,
        resume_count=len(resumes),
        resumes=resume_summaries,
    )
