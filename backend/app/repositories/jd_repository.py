"""Job description repository."""
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_description import JobDescription


class JobDescriptionRepository:
    @staticmethod
    async def create(
        session: AsyncSession,
        user_id: UUID,
        title: str,
        raw_text: str,
        embedding: list[float] | None = None,
    ) -> JobDescription:
        jd = JobDescription(user_id=user_id, title=title, raw_text=raw_text)
        if embedding is not None:
            jd.embedding = embedding
        session.add(jd)
        await session.flush()
        await session.refresh(jd)
        return jd

    @staticmethod
    async def get_by_id(session: AsyncSession, jd_id: UUID) -> JobDescription | None:
        result = await session.execute(select(JobDescription).where(JobDescription.id == jd_id))
        return result.scalars().first()

    @staticmethod
    async def update_embedding(session: AsyncSession, jd_id: UUID, embedding: list[float]) -> None:
        jd = await JobDescriptionRepository.get_by_id(session, jd_id)
        if jd:
            jd.embedding = embedding
            await session.flush()

    @staticmethod
    async def list_for_user(
        session: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[JobDescription], int]:
        count_q = select(func.count()).select_from(JobDescription).where(JobDescription.user_id == user_id)
        total = (await session.execute(count_q)).scalar() or 0
        offset = (page - 1) * page_size
        q = (
            select(JobDescription)
            .where(JobDescription.user_id == user_id)
            .order_by(JobDescription.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await session.execute(q)
        items = list(result.scalars().all())
        return items, total
