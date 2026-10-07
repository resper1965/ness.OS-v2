# -------------------------------------------------------
# NessOps — FastAPI Application Entry Point
# -------------------------------------------------------
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.api.webhooks import router as webhooks_router
from app.api.routers.contabo import router as contabo_router
from app.api.routers.dashboard import router as dashboard_router
from app.api.routers.pipeline import router as pipeline_router
from app.api.routers.incidents import router as incidents_router
from app.api.routers.tenants import router as tenants_router
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev purposes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(webhooks_router)
app.include_router(contabo_router, prefix="/api/contabo", tags=["contabo"])
app.include_router(dashboard_router, tags=["dashboard"])
app.include_router(pipeline_router, tags=["dashboard"])
app.include_router(incidents_router, tags=["incidents"])
app.include_router(tenants_router, prefix="/api/tenants", tags=["tenants"])


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "running"}
