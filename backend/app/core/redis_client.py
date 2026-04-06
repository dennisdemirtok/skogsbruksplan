import json
import logging
from typing import Optional

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[redis.Redis] = None


async def get_redis() -> Optional[redis.Redis]:
    """Get or create the async Redis connection. Returns None if unavailable."""
    global _redis
    if _redis is not None:
        return _redis
    try:
        _redis = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        # Test the connection
        await _redis.ping()
        logger.info("Redis connection established")
        return _redis
    except Exception as e:
        logger.warning(f"Redis unavailable, caching disabled: {e}")
        _redis = None
        return None


async def cache_get(key: str) -> Optional[str]:
    """Get a value from Redis cache. Returns None if Redis is unavailable or key doesn't exist."""
    try:
        client = await get_redis()
        if client is None:
            return None
        value = await client.get(key)
        return value
    except Exception as e:
        logger.warning(f"Redis cache_get error for key '{key}': {e}")
        return None


async def cache_set(key: str, value: str, ttl: int = 3600) -> bool:
    """Set a value in Redis cache with TTL (default 1 hour). Returns False if Redis is unavailable."""
    try:
        client = await get_redis()
        if client is None:
            return False
        await client.set(key, value, ex=ttl)
        return True
    except Exception as e:
        logger.warning(f"Redis cache_set error for key '{key}': {e}")
        return False


async def close_redis() -> None:
    """Close the Redis connection on shutdown."""
    global _redis
    if _redis is not None:
        try:
            await _redis.close()
        except Exception:
            pass
        _redis = None
