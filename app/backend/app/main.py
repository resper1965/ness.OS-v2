# -------------------------------------------------------
# NessOps — FastAPI Application Entry Point
# -------------------------------------------------------
from __future__ import annotations

import logging

from fastapi import FastAPI

from app.api.webhooks import router as webhooks_router
from app.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title=settings.app_name,
    description="Plataforma AIOps — Correlação e remediação inteligente de alertas Zabbix",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- Routers ---
app.include_router(webhooks_router)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "running"}
