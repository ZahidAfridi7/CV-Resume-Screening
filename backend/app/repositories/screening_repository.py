"""Screening run and result repositories."""
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.screening import ScreeningResult, ScreeningRun


class ScreeningRepository:
    @staticmethod
    async def create_run(
        session: AsyncSession,
        jd_id: UUID,
        batch_id: UUID | None = None,
    ) -> ScreeningRun:
        run = ScreeningRun(jd_id=jd_id, batch_id=batch_id)
        session.add(run)
        await session.flush()
        await session.refresh(run)
        return run

    @staticmethod
    async def add_results(
        session: AsyncSession,
        run_id: UUID,
        results: list[tuple[UUID, float, int]],
    ) -> None:
        for resume_id, similarity_score, rank_position in results:
            sr = ScreeningResult(
                run_id=run_id,
                resume_id=resume_id,
                similarity_score=similarity_score,
                rank_position=rank_position,
            )
            session.add(sr)
        await session.flush()

    @staticmethod
    async def get_run_by_id(session: AsyncSession, run_id: UUID) -> ScreeningRun | None:
        result = await session.execute(select(ScreeningRun).where(ScreeningRun.id == run_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_runs_for_user(
        session: AsyncSession,
        user_id: UUID,
        jd_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ScreeningRun], int]:
        from app.models.job_description import JobDescription

        count_q = (
            select(func.count(ScreeningRun.id))
            .select_from(ScreeningRun)
            .join(JobDescription, JobDescription.id == ScreeningRun.jd_id)
            .where(JobDescription.user_id == user_id)
        )
        if jd_id is not None:
            count_q = count_q.where(ScreeningRun.jd_id == jd_id)
        total = (await session.execute(count_q)).scalar() or 0

        offset = (page - 1) * page_size
        base = (
            select(ScreeningRun)
            .join(JobDescription, JobDescription.id == ScreeningRun.jd_id)
            .where(JobDescription.user_id == user_id)
        )
        if jd_id is not None:
            base = base.where(ScreeningRun.jd_id == jd_id)
        q = base.order_by(ScreeningRun.created_at.desc()).offset(offset).limit(page_size)
        result = await session.execute(q)
        runs = list(result.unique().scalars().all())
        return runs, total

    @staticmethod
    async def list_runs_for_user_with_result_counts(
        session: AsyncSession,
        user_id: UUID,
        jd_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[tuple[UUID, UUID, UUID | None, object, int]], int]:
        """List runs with result_count in one query (avoids N+1). Returns list of (id, jd_id, batch_id, created_at, result_count), total."""
        from app.models.job_description import JobDescription

        count_q = (
            select(func.count(ScreeningRun.id))
            .select_from(ScreeningRun)
            .join(JobDescription, JobDescription.id == ScreeningRun.jd_id)
            .where(JobDescription.user_id == user_id)
        )
        if jd_id is not None:
            count_q = count_q.where(ScreeningRun.jd_id == jd_id)
        total = (await session.execute(count_q)).scalar() or 0

        offset = (page - 1) * page_size
        q = (
            select(
                ScreeningRun.id,
                ScreeningRun.jd_id,
                ScreeningRun.batch_id,
                ScreeningRun.created_at,
                func.count(ScreeningResult.id).label("result_count"),
            )
            .join(JobDescription, JobDescription.id == ScreeningRun.jd_id)
            .outerjoin(ScreeningResult, ScreeningResult.run_id == ScreeningRun.id)
            .where(JobDescription.user_id == user_id)
        )
        if jd_id is not None:
            q = q.where(ScreeningRun.jd_id == jd_id)
        q = (
            q.group_by(ScreeningRun.id, ScreeningRun.jd_id, ScreeningRun.batch_id, ScreeningRun.created_at)
            .order_by(ScreeningRun.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await session.execute(q)
        rows = result.all()
        return [(r.id, r.jd_id, r.batch_id, r.created_at, r.result_count) for r in rows], total
