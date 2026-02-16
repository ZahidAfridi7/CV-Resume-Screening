"""Async Redis client for token blacklist (revocation). Uses same REDIS_URL as Celery with key prefix."""
import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
BLACKLIST_PREFIX = "jti_blacklist:"
# TTL for blacklisted JTI (match access token max lifetime so blacklist entry outlives the token)
DEFAULT_BLACKLIST_TTL_SECONDS = 60 * 60 * 24 * 2  # 2 days


def _get_client():
    try:
        from redis.asyncio import Redis
        return Redis.from_url(get_settings().redis_url, decode_responses=True)
    except Exception as e:
        logger.warning("Redis not available for token blacklist: %s", e)
        return None


async def is_token_revoked(jti: str) -> bool:
    """Return True if the token JTI is in the blacklist."""
    client = _get_client()
    if not client:
        return False
    try:
        key = f"{BLACKLIST_PREFIX}{jti}"
        return await client.exists(key) > 0
    except Exception as e:
        logger.warning("Redis blacklist check failed: %s", e)
        return False
    finally:
        if client:
            await client.aclose()


async def revoke_token(jti: str, ttl_seconds: int = DEFAULT_BLACKLIST_TTL_SECONDS) -> None:
    """Add the token JTI to the blacklist with the given TTL."""
    client = _get_client()
    if not client:
        return
    try:
        key = f"{BLACKLIST_PREFIX}{jti}"
        await client.set(key, "1", ex=ttl_seconds)
    except Exception as e:
        logger.warning("Redis blacklist set failed: %s", e)
    finally:
        if client:
            await client.aclose()
