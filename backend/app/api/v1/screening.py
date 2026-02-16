"""Screening: rank CVs by JD, list runs, get run detail."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limit import get_user_or_ip_key, limiter
from app.db.session import get_async_session
from app.models.user import User
from app.repositories.jd_repository import JobDescriptionRepository
from app.repositories.screening_repository import ScreeningRepository
from app.schemas.common import PaginationParams, get_pagination
from app.schemas.screening import (
    RankRequest,
    RankResponse,
    RankedResumeItem,
    PaginatedRuns,
    RunDetailResponse,
    ScreeningRunListItem,
    ScreeningResultItem,
)
from app.core.embedding_errors import EmbeddingUnavailableError
from app.services.embedding import EmbeddingService
from app.services.ranking.service import RankingService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/rank", response_model=RankResponse)
@limiter.limit("30/minute", key_func=get_user_or_ip_key)
async def rank_cvs(
    request: Request,
    body: RankRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> RankResponse:
    logger.info(
        "Rank request: jd_id=%s batch_id=%s limit=%s min_score=%s",
        body.jd_id, body.batch_id, body.limit, body.min_score,
    )
    jd = await JobDescriptionRepository.get_by_id(session, body.jd_id)
    if not jd or jd.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job description not found")
    if jd.embedding is None:
        logger.info("Computing JD embedding for jd_id=%s (raw_text len=%d)", body.jd_id, len(jd.raw_text or ""))
        try:
            emb_svc = EmbeddingService()
            jd.embedding = await emb_svc.embed_text_async(jd.raw_text)
            await JobDescriptionRepository.update_embedding(session, jd.id, jd.embedding)
            await session.commit()
        except EmbeddingUnavailableError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Embedding service temporarily unavailable. Try again later.",
            )
    else:
        logger.info("Using cached JD embedding for jd_id=%s (dim=%d)", body.jd_id, len(jd.embedding))
    ranked = await RankingService.rank_resumes(
        session, list(jd.embedding), batch_id=body.batch_id, limit=body.limit, min_score=body.min_score
    )
    if not ranked:
        logger.warning("Ranking returned 0 CVs for jd_id=%s (check diagnostic counts above)", body.jd_id)
    else:
        logger.info("Ranking returned %d CVs for jd_id=%s", len(ranked), body.jd_id)
    for rank_pos, (r_id, fn, score, _, bid) in enumerate(ranked, start=1):
        logger.info("  [%d] resume_id=%s filename=%s score=%.4f batch_id=%s", rank_pos, r_id, fn, score, bid)
    run = await ScreeningRepository.create_run(session, body.jd_id, body.batch_id)
    results_for_db = [(resume_id, score, rank_pos) for resume_id, _, score, rank_pos, _ in ranked]
    await ScreeningRepository.add_results(session, run.id, results_for_db)
    await session.commit()
    results = [
        RankedResumeItem(resume_id=r_id, filename=fn, similarity_score=score, rank_position=pos, batch_id=bid)
        for r_id, fn, score, pos, bid in ranked
    ]
    return RankResponse(run_id=run.id, jd_id=body.jd_id, total_count=len(results), results=results)


@router.get("/runs", response_model=PaginatedRuns)
async def list_runs(
    jd_id: UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    pagination: PaginationParams = Depends(get_pagination),
) -> PaginatedRuns:
    rows, total = await ScreeningRepository.list_runs_for_user_with_result_counts(
        session, current_user.id, jd_id=jd_id, page=pagination.page, page_size=pagination.page_size
    )
    items = [
        ScreeningRunListItem(id=r[0], jd_id=r[1], batch_id=r[2], created_at=r[3], result_count=r[4])
        for r in rows
    ]
    pages = (total + pagination.page_size - 1) // pagination.page_size if total else 0
    return PaginatedRuns(items=items, total=total, page=pagination.page, page_size=pagination.page_size, pages=pages)


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    pagination: PaginationParams = Depends(get_pagination),
) -> RunDetailResponse:
    run = await ScreeningRepository.get_run_by_id(session, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    jd = await JobDescriptionRepository.get_by_id(session, run.jd_id)
    if not jd or jd.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    from sqlalchemy import func, select
    from app.models.screening import ScreeningResult
    from app.models.upload import Resume
    q = select(ScreeningResult, Resume).join(Resume, Resume.id == ScreeningResult.resume_id).where(ScreeningResult.run_id == run_id).order_by(ScreeningResult.rank_position)
    offset = (pagination.page - 1) * pagination.page_size
    q = q.offset(offset).limit(pagination.page_size)
    result = await session.execute(q)
    rows = result.all()
    total_q = await session.execute(select(func.count()).select_from(ScreeningResult).where(ScreeningResult.run_id == run_id))
    total = total_q.scalar() or 0
    results = [ScreeningResultItem(resume_id=sr.resume_id, filename=r.filename, similarity_score=float(sr.similarity_score), rank_position=sr.rank_position) for sr, r in rows]
    return RunDetailResponse(id=run.id, jd_id=run.jd_id, batch_id=run.batch_id, created_at=run.created_at, results=results, total=total)

