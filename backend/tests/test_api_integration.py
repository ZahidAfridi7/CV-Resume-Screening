"""Integration tests for protected API routes (auth required)."""
import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_upload_batch_requires_auth(client: AsyncClient):
    """POST /api/v1/uploads/batch without token returns 401."""
    r = await client.post(
        "/api/v1/uploads/batch",
        data={"batch_name": "Test"},
        files=[("files", ("test.pdf", b"fake pdf content", "application/pdf"))],
    )
    assert r.status_code == 401


async def test_rank_requires_auth(client: AsyncClient):
    """POST /api/v1/screening/rank without token returns 401."""
    r = await client.post(
        "/api/v1/screening/rank",
        json={
            "jd_id": "00000000-0000-0000-0000-000000000001",
            "limit": 10,
        },
    )
    assert r.status_code == 401


async def test_analytics_dashboard_requires_auth(client: AsyncClient):
    """GET /api/v1/analytics/dashboard without token returns 401."""
    r = await client.get("/api/v1/analytics/dashboard")
    assert r.status_code == 401
