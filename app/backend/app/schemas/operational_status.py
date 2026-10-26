"""The source timestamp refers to a valid collection, never a failed attempt."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class OperationalStatus(BaseModel):
    status: Literal["ok", "degraded", "down", "planned", "unavailable"]
    source: str
    observed_at: datetime
    last_success_at: datetime | None = None
    freshness_seconds: int | None = None
    stale: bool
    error_code: str | None = None
    data: dict[str, Any] | None = None
