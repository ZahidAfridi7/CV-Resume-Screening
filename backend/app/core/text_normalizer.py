"""
Normalize text before embedding: collapse whitespace, strip, limit length.
"""
import re


def normalize_text(text: str | None, max_chars: int = 8000) -> str:
    """
    Normalize text for embedding: remove excessive whitespace, strip, truncate.
    OpenAI embedding models have token limits; 8000 chars is a safe upper bound.
    """
    if not text or not isinstance(text, str):
        return ""
    # Collapse whitespace (spaces, newlines, tabs) to single space
    normalized = re.sub(r"\s+", " ", text)
    normalized = normalized.strip()
    if len(normalized) > max_chars:
        normalized = normalized[:max_chars]
    return normalized
