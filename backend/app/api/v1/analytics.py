"""Analytics dashboard."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_async_session
from app.models.upload import Resume, UploadBatch
from app.models.user import User
from app.models.job_description import JobDescription
from app.models.screening import ScreeningRun
from app.schemas.analytics import DashboardResponse

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> DashboardResponse:
    # Counts scoped to current user
    batches_q = select(func.count()).select_from(UploadBatch).where(UploadBatch.user_id == current_user.id)
    total_batches = (await session.execute(batches_q)).scalar() or 0
    jds_q = select(func.count()).select_from(JobDescription).where(JobDescription.user_id == current_user.id)
    total_jds = (await session.execute(jds_q)).scalar() or 0
    runs_q = select(func.count()).select_from(ScreeningRun).join(JobDescription, JobDescription.id == ScreeningRun.jd_id).where(JobDescription.user_id == current_user.id)
    total_runs = (await session.execute(runs_q)).scalar() or 0
    resumes_q = select(func.count()).select_from(Resume).join(UploadBatch, UploadBatch.id == Resume.batch_id).where(UploadBatch.user_id == current_user.id)
    total_resumes = (await session.execute(resumes_q)).scalar() or 0
    by_status_q = select(Resume.status, func.count()).select_from(Resume).join(UploadBatch, UploadBatch.id == Resume.batch_id).where(UploadBatch.user_id == current_user.id).group_by(Resume.status)
    by_status_rows = (await session.execute(by_status_q)).all()
    resumes_by_status = {row[0]: row[1] for row in by_status_rows}
    date_from = (datetime.now(timezone.utc) - timedelta(days=30)).date()

    uploads_by_date_q = select(func.date(UploadBatch.created_at), func.count()).select_from(UploadBatch).where(UploadBatch.user_id == current_user.id).where(func.date(UploadBatch.created_at) >= date_from).group_by(func.date(UploadBatch.created_at)).order_by(func.date(UploadBatch.created_at))
    uploads_by_date_rows = (await session.execute(uploads_by_date_q)).all()
    uploads_by_date = [{"date": str(r[0]), "count": r[1]} for r in uploads_by_date_rows]

    runs_by_date_q = select(func.date(ScreeningRun.created_at), func.count()).select_from(ScreeningRun).join(JobDescription, JobDescription.id == ScreeningRun.jd_id).where(JobDescription.user_id == current_user.id).where(func.date(ScreeningRun.created_at) >= date_from).group_by(func.date(ScreeningRun.created_at)).order_by(func.date(ScreeningRun.created_at))
    runs_by_date_rows = (await session.execute(runs_by_date_q)).all()
    runs_by_date = [{"date": str(r[0]), "count": r[1]} for r in runs_by_date_rows]

    jds_by_date_q = select(func.date(JobDescription.created_at), func.count()).select_from(JobDescription).where(JobDescription.user_id == current_user.id).where(func.date(JobDescription.created_at) >= date_from).group_by(func.date(JobDescription.created_at)).order_by(func.date(JobDescription.created_at))
    jds_by_date_rows = (await session.execute(jds_by_date_q)).all()
    jds_by_date = [{"date": str(r[0]), "count": r[1]} for r in jds_by_date_rows]

    return DashboardResponse(
        total_resumes=total_resumes,
        total_batches=total_batches,
        total_jds=total_jds,
        total_runs=total_runs,
        resumes_by_status=resumes_by_status,
        uploads_by_date=uploads_by_date,
        runs_by_date=runs_by_date,
        jds_by_date=jds_by_date,
    )
