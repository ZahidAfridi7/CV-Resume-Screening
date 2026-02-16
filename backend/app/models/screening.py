"""Screening run and result models."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ScreeningRun(Base):
    __tablename__ = "screening_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jd_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False)
    batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("upload_batches.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    results: Mapped[list["ScreeningResult"]] = relationship(
        "ScreeningResult", back_populates="run", cascade="all, delete-orphan", order_by="ScreeningResult.rank_position"
    )


class ScreeningResult(Base):
    __tablename__ = "screening_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("screening_runs.id", ondelete="CASCADE"), nullable=False)
    resume_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    similarity_score: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)  # 0.00000 - 1.00000
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)

    run: Mapped["ScreeningRun"] = relationship("ScreeningRun", back_populates="results")
