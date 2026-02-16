"""
Celery task: extract text from CV file, normalize, embed, store. Updates batch status when all done.
Uses sync SQLAlchemy for Celery worker.
"""
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine

from app.config import get_settings
from app.models.upload import Resume, UploadBatch
from app.services.extraction import ExtractionService
from app.services.embedding import EmbeddingService
from app.core.text_normalizer import normalize_text

# Celery app instance (used as decorator target)
from celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()

# Sync engine for Celery worker (pool tuned for multiple workers)
_sync_url = settings.database_url_sync or settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
_engine = create_engine(
    _sync_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
)
_Session = sessionmaker(_engine, expire_on_commit=False, autocommit=False, autoflush=False)


def _get_session() -> Session:
    return _Session()


@celery_app.task(bind=True, name="app.tasks.process_resume")
def process_resume_task(self, resume_id: str, file_path: str) -> None:
    """Process a single resume: extract text, embed, update DB. On failure mark resume failed. Idempotent: skips if already processed."""
    rid = UUID(resume_id)
    session = _get_session()
    try:
        resume = session.execute(select(Resume).where(Resume.id == rid)).scalars().first()
        if not resume:
            logger.warning("Resume not found: %s", resume_id)
            return
        if resume.status == "processed":
            logger.info("Resume %s already processed, skipping (idempotent)", resume_id)
            return
        try:
            raw_text = ExtractionService.extract_from_path(file_path)
            normalized = normalize_text(raw_text)
            if not normalized:
                ResumeRepository_sync.update_failed(session, rid, "Empty or unreadable text")
                session.commit()
                _maybe_complete_batch(session, resume.batch_id)
                return
            embedding_svc = EmbeddingService()
            embedding = embedding_svc.embed_text(normalized)
            ResumeRepository_sync.update_processed(session, rid, normalized[:50000], embedding)
            session.commit()
        except Exception as e:
            logger.exception("Process failed for resume %s: %s", resume_id, e)
            ResumeRepository_sync.update_failed(session, rid, str(e))
            session.commit()
        finally:
            _maybe_complete_batch(session, resume.batch_id)
    finally:
        session.close()


def _maybe_complete_batch(session: Session, batch_id: UUID) -> None:
    """If all resumes in batch are processed or failed, set batch status to completed or failed."""
    from sqlalchemy import func
    pending = session.execute(select(func.count()).select_from(Resume).where(Resume.batch_id == batch_id, Resume.status == "pending")).scalar() or 0
    if pending == 0:
        batch = session.execute(select(UploadBatch).where(UploadBatch.id == batch_id)).scalars().first()
        if batch:
            failed = session.execute(select(func.count()).select_from(Resume).where(Resume.batch_id == batch_id, Resume.status == "failed")).scalar() or 0
            batch.status = "failed" if failed else "completed"
            session.flush()
    session.commit()


class ResumeRepository_sync:
    @staticmethod
    def update_processed(session: Session, resume_id: UUID, extracted_text: str, embedding: list[float]) -> None:
        resume = session.execute(select(Resume).where(Resume.id == resume_id)).scalars().first()
        if resume:
            resume.extracted_text = extracted_text
            resume.embedding = embedding
            resume.status = "processed"
            resume.error_message = None

    @staticmethod
    def update_failed(session: Session, resume_id: UUID, error_message: str) -> None:
        resume = session.execute(select(Resume).where(Resume.id == resume_id)).scalars().first()
        if resume:
            resume.status = "failed"
            resume.error_message = error_message
