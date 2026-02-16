"""Unit tests for embedding service."""
import os
import pytest
from app.services.embedding.service import EmbeddingService
from app.config import get_settings


def test_embed_empty_returns_zero_vector():
    try:
        svc = EmbeddingService()
    except ValueError:
        pytest.skip("OPENAI_API_KEY not set")
    result = svc.embed_text("")
    dim = get_settings().openai_embedding_dimensions
    assert len(result) == dim
    assert all(x == 0.0 for x in result)


def test_embed_none_returns_zero_vector():
    try:
        svc = EmbeddingService()
    except ValueError:
        pytest.skip("OPENAI_API_KEY not set")
    result = svc.embed_text(None)
    dim = get_settings().openai_embedding_dimensions
    assert len(result) == dim
    assert all(x == 0.0 for x in result)
