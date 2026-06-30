# -------------------------------------------------------
# NessOps — Lock Distribuído via Redis
# -------------------------------------------------------
"""
Previne race conditions quando centenas de webhooks chegam
simultaneamente em cenários de falha massiva.

Usa SET NX EX (atomic) para garantir que apenas 1 worker
processa a criação inicial do incidente para cada fingerprint.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from redis.asyncio import Redis


@asynccontextmanager
async def distributed_lock(
    redis: Redis,
    fingerprint: str,
    ttl_seconds: int = 10,
) -> AsyncGenerator[bool, None]:
    """Context manager para lock distribuído baseado em fingerprint.

    Args:
        redis: Conexão async do Redis.
        fingerprint: SHA-256 do alerta (garante unicidade por host+trigger).
        ttl_seconds: TTL do lock (auto-release se worker morrer).

    Yields:
        True se o lock foi adquirido, False caso contrário.
    """
    lock_key = f"ninf:lock:{fingerprint}"
    acquired = await redis.set(lock_key, "1", nx=True, ex=ttl_seconds)

    try:
        yield bool(acquired)
    finally:
        # Libera o lock apenas se nós o adquirimos
        if acquired:
            await redis.delete(lock_key)


async def try_acquire_lock(
    redis: Redis,
    fingerprint: str,
    ttl_seconds: int = 10,
) -> bool:
    """Tenta adquirir lock sem context manager (fire-and-forget).

    Usado no endpoint webhook onde não precisamos do finally
    (o worker Celery libera após processamento).
    """
    lock_key = f"nessops:lock:{fingerprint}"
    result = await redis.set(lock_key, "1", nx=True, ex=ttl_seconds)
    return bool(result)
