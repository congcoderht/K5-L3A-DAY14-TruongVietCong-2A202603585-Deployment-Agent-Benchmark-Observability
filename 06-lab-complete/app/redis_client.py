"""
Kết nối Redis dùng chung cho rate limiter và cost guard.
"""
import redis

from app.config import settings

# Chỉ khởi tạo client nếu REDIS_URL được cấu hình; không ping lúc import
# để container vẫn khởi động được khi Redis chưa sẵn sàng.
r = (
    redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1.0,
        socket_timeout=1.0,
    )
    if settings.redis_url
    else None
)


def redis_healthy() -> bool:
    """Kiểm tra kết nối Redis cho endpoint /ready."""
    if r is None:
        return False
    try:
        return bool(r.ping())
    except Exception:
        return False
