"""Unit tests for ranking service (empty embedding returns empty list)."""
import pytest
from unittest.mock import AsyncMock

from app.services.ranking.service import RankingService

pytestmark = pytest.mark.asyncio


async def test_rank_resumes_empty_embedding_returns_empty():
    session = AsyncMock()
    result = await RankingService.rank_resumes(session, [])
    assert result == []
    session.execute.assert_not_called()
