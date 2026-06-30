# -------------------------------------------------------
# NessOps — Dependencies (FastAPI Dependency Injection)
# -------------------------------------------------------
from __future__ import annotations

from typing import AsyncGenerator

from redis.asyncio import Redis

from app.config import get_settings


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Conexão Redis reutilizável via FastAPI Depends."""
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()
