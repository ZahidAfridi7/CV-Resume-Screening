"""Aggregate v1 API router."""
from fastapi import APIRouter

from app.api.v1 import analytics, auth, job_descriptions, screening, uploads

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
api_router.include_router(job_descriptions.router, prefix="/job-descriptions", tags=["job-descriptions"])
api_router.include_router(screening.router, prefix="/screening", tags=["screening"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
