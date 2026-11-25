"""
Rate limiting dùng Redis Sorted Set (tiêu chí 7).
"""
import hashlib
import logging
import time
import uuid

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r

logger = logging.getLogger("app.rate_limiter")

WINDOW_SECONDS = 60


def _rate_key(api_key: str) -> str:
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
    return f"ratelimit:{digest}"


def check_rate_limit(key: str) -> None:
    """Kiểm tra sliding window rate limit trong Redis; vượt ngưỡng trả HTTP 429."""
    if r is None:
        return

    redis_key = _rate_key(key)
    now = time.time()
    cutoff = now - WINDOW_SECONDS
    limit = settings.rate_limit_per_minute

    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, 0, cutoff)
        pipe.zcard(redis_key)
        _, current_count = pipe.execute()

        if current_count >= limit:
            oldest = r.zrange(redis_key, 0, 0, withscores=True)
            retry_after = (
                max(1, int(oldest[0][1] + WINDOW_SECONDS - now) + 1)
                if oldest
                else WINDOW_SECONDS
            )
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )

        member = f"{now}:{uuid.uuid4().hex}"
        pipe = r.pipeline()
        pipe.zadd(redis_key, {member: now})
        pipe.expire(redis_key, WINDOW_SECONDS + 5)
        pipe.execute()
    except HTTPException:
        raise
    except RedisError as exc:
        logger.warning("Redis rate limiter error", extra={"event": "redis_error", "error": str(exc)})
