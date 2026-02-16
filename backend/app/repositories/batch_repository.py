"""Upload batch and resume repositories."""
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.upload import Resume, UploadBatch


class BatchRepository:
    @staticmethod
    async def create(session: AsyncSession, user_id: UUID, batch_name: str | None = None) -> UploadBatch:
        batch = UploadBatch(user_id=user_id, batch_name=batch_name, status="pending")
        session.add(batch)
        await session.flush()
        await session.refresh(batch)
        return batch

    @staticmethod
    async def get_by_id(session: AsyncSession, batch_id: UUID) -> UploadBatch | None:
        result = await session.execute(select(UploadBatch).where(UploadBatch.id == batch_id))
        return result.scalars().first()

    @staticmethod
    async def list_for_user(
        session: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[UploadBatch], int]:
        count_q = select(func.count()).select_from(UploadBatch).where(UploadBatch.user_id == user_id)
        total = (await session.execute(count_q)).scalar() or 0
        offset = (page - 1) * page_size
        q = (
            select(UploadBatch)
            .where(UploadBatch.user_id == user_id)
            .order_by(UploadBatch.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await session.execute(q)
        batches = list(result.scalars().all())
        return batches, total

    @staticmethod
    async def list_for_user_with_resume_counts(session: AsyncSession, user_id: UUID, page: int = 1, page_size: int = 20):
        """List batches with resume_count in one query (avoids N+1). Returns (rows, total); each row is (id, batch_name, status, created_at, resume_count)."""
        count_q = select(func.count()).select_from(UploadBatch).where(UploadBatch.user_id == user_id)
        total = (await session.execute(count_q)).scalar() or 0
        offset = (page - 1) * page_size
        q = (
            select(UploadBatch.id, UploadBatch.batch_name, UploadBatch.status, UploadBatch.created_at, func.count(Resume.id).label("resume_count"))
            .outerjoin(Resume, Resume.batch_id == UploadBatch.id)
            .where(UploadBatch.user_id == user_id)
            .group_by(UploadBatch.id, UploadBatch.batch_name, UploadBatch.status, UploadBatch.created_at)
            .order_by(UploadBatch.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await session.execute(q)
        rows = result.all()
        return [(r.id, r.batch_name, r.status, r.created_at, r.resume_count) for r in rows], total

    @staticmethod
    async def update_status(session: AsyncSession, batch_id: UUID, status: str) -> None:
        batch = await BatchRepository.get_by_id(session, batch_id)
        if batch:
            batch.status = status
            await session.flush()


class ResumeRepository:
    @staticmethod
    async def create(
        session: AsyncSession,
        batch_id: UUID,
        filename: str,
        file_path: str | None = None,
        file_size: int | None = None,
    ) -> Resume:
        resume = Resume(
            batch_id=batch_id,
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            status="pending",
        )
        session.add(resume)
        await session.flush()
        await session.refresh(resume)
        return resume

    @staticmethod
    async def get_by_id(session: AsyncSession, resume_id: UUID) -> Resume | None:
        result = await session.execute(select(Resume).where(Resume.id == resume_id))
        return result.scalars().first()

    @staticmethod
    async def update_processed(
        session: AsyncSession,
        resume_id: UUID,
        extracted_text: str,
        embedding: list[float],
    ) -> None:
        resume = await ResumeRepository.get_by_id(session, resume_id)
        if resume:
            resume.extracted_text = extracted_text
            resume.embedding = embedding
            resume.status = "processed"
            resume.error_message = None
            await session.flush()

    @staticmethod
    async def update_failed(session: AsyncSession, resume_id: UUID, error_message: str) -> None:
        resume = await ResumeRepository.get_by_id(session, resume_id)
        if resume:
            resume.status = "failed"
            resume.error_message = error_message
            await session.flush()
