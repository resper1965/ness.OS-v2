"""Collect a source and retain its last valid value across API workers."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from app.schemas.operational_status import OperationalStatus


async def observe_source(
    source: str,
    collector: Callable[[], Awaitable[dict[str, Any]]],
    cache: Any,
    *,
    configured: bool = True,
    now: datetime | None = None,
    timeout_seconds: float = 8,
) -> OperationalStatus:
    observed_at = now or datetime.now(timezone.utc)
    if not configured:
        return OperationalStatus(
            status="unavailable",
            source=source,
            observed_at=observed_at,
            stale=True,
            error_code="not_configured",
        )

    key = f"ninf:source:last-success:{source}"
    try:
        data = await asyncio.wait_for(collector(), timeout=timeout_seconds)
    except Exception as exc:
        error_code = type(exc).__name__
    else:
        try:
            await cache.set(
                key,
                json.dumps({"data": data, "last_success_at": observed_at.isoformat()}),
            )
        except Exception:
            return OperationalStatus(
                status="degraded",
                source=source,
                observed_at=observed_at,
                last_success_at=observed_at,
                freshness_seconds=0,
                stale=False,
                error_code="cache_unavailable",
                data=data,
            )
        return OperationalStatus(
            status="ok",
            source=source,
            observed_at=observed_at,
            last_success_at=observed_at,
            freshness_seconds=0,
            stale=False,
            data=data,
        )

    try:
        saved = json.loads(await cache.get(key) or "null")
        last_success = datetime.fromisoformat(saved["last_success_at"])
        previous_data = saved["data"]
        if not isinstance(previous_data, dict) or last_success.tzinfo is None:
            raise ValueError("invalid cached source value")
    except Exception:
        return OperationalStatus(
            status="down",
            source=source,
            observed_at=observed_at,
            stale=True,
            error_code=error_code,
        )
    return OperationalStatus(
        status="degraded",
        source=source,
        observed_at=observed_at,
        last_success_at=last_success,
        freshness_seconds=max(0, int((observed_at - last_success).total_seconds())),
        stale=True,
        error_code=error_code,
        data=previous_data,
    )
