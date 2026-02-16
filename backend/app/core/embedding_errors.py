"""Exceptions for embedding service (e.g. circuit open, unavailable)."""


class EmbeddingUnavailableError(Exception):
    """Raised when embedding cannot be computed (e.g. circuit breaker open, service down)."""
