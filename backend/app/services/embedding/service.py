"""
Generate embeddings via OpenAI API (embeddings only, no LLM).
Uses text-embedding-3-small; normalizes text before embedding.
Sync client for Celery; async client for FastAPI routes (non-blocking).
"""
import asyncio
import logging

from openai import AsyncOpenAI, OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.core.circuit_breaker import get_embedding_circuit
from app.core.embedding_errors import EmbeddingUnavailableError
from app.core.text_normalizer import normalize_text

logger = logging.getLogger(__name__)
settings = get_settings()

# Retry on transient/rate-limit errors for sync callers (Celery)
_retry_policy = retry(
    retry=retry_if_exception_type((Exception,)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    reraise=True,
)


class EmbeddingService:
    """Generate embeddings for text using OpenAI. Use embed_text in sync context (Celery), embed_text_async in async (FastAPI)."""

    def __init__(self) -> None:
        self._client: OpenAI | None = None
        self._async_client: AsyncOpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is not set")
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    @property
    def async_client(self) -> AsyncOpenAI:
        if self._async_client is None:
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is not set")
            self._async_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._async_client

    def _call_embed(self, normalized: str) -> list[float]:
        """Single sync API call (used by embed_text and by retry wrapper)."""
        response = self.client.embeddings.create(
            model=settings.openai_embedding_model,
            input=normalized,
            dimensions=settings.openai_embedding_dimensions,
            timeout=30.0,
        )
        return response.data[0].embedding

    @_retry_policy
    def embed_text(self, text: str | None) -> list[float]:
        """
        Sync: normalize text and return embedding vector. Use in Celery tasks.
        Returns zero vector if text is empty (caller may skip storing).
        """
        normalized = normalize_text(text, max_chars=8000)
        if not normalized:
            return [0.0] * settings.openai_embedding_dimensions
        return self._call_embed(normalized)

    async def embed_text_async(self, text: str | None) -> list[float]:
        """
        Async: normalize text and return embedding vector. Use in FastAPI routes to avoid blocking.
        Returns zero vector if text is empty. Retries with asyncio.sleep (non-blocking).
        Raises EmbeddingUnavailableError when circuit breaker is open.
        """
        normalized = normalize_text(text, max_chars=8000)
        if not normalized:
            return [0.0] * settings.openai_embedding_dimensions
        circuit = get_embedding_circuit()
        if circuit.is_open():
            raise EmbeddingUnavailableError("Embedding service temporarily unavailable (circuit open)")
        last_error = None
        for attempt in range(5):
            try:
                response = await self.async_client.embeddings.create(
                    model=settings.openai_embedding_model,
                    input=normalized,
                    dimensions=settings.openai_embedding_dimensions,
                    timeout=30.0,
                )
                circuit.record_success()
                return response.data[0].embedding
            except Exception as e:
                last_error = e
                circuit.record_failure()
                if attempt < 4:
                    wait = min(2 ** (attempt + 1), 60)
                    logger.warning(
                        "Embedding attempt %s failed: %s; retrying in %ss",
                        attempt + 1, e, wait,
                    )
                    await asyncio.sleep(wait)
        raise last_error
