"""Shared authentication for machine-to-machine ingestion."""

from hmac import compare_digest

from fastapi import HTTPException


def verify_key(configured: str, supplied: str | None) -> None:
    if not configured:
        raise HTTPException(
            status_code=503, detail="Webhook authentication unavailable"
        )
    if not supplied or not compare_digest(supplied.encode(), configured.encode()):
        raise HTTPException(status_code=401, detail="Invalid API Key")
