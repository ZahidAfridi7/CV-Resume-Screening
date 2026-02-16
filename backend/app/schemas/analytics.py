"""Analytics dashboard schemas."""
from pydantic import BaseModel


class DashboardResponse(BaseModel):
    total_resumes: int
    total_batches: int
    total_jds: int
    total_runs: int
    resumes_by_status: dict[str, int]
    uploads_by_date: list[dict[str, str | int]]
    runs_by_date: list[dict[str, str | int]]
    jds_by_date: list[dict[str, str | int]]
