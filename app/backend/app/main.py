# -------------------------------------------------------
# ness.OS — Plataforma Unificada de Operacoes Gerenciadas
# Modulos: n.infraops | n.secops | core
# -------------------------------------------------------
from __future__ import annotations

# Imports da aplicação ocorrem após o ajuste de `sys.path` para preservar a
# execução direta usada pelos scripts legados de operação.
# ruff: noqa: E402
import asyncio
import logging
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sqlalchemy import text

project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.api.v1.alerts import router as v1_alerts_router
from app.api.webhooks import router as webhooks_router

try:
    from app.api.routers.contabo import router as contabo_router

    _has_contabo = True
except ImportError:
    contabo_router = None  # type: ignore
    _has_contabo = False
from app.api.routers.assets import router as assets_router
from app.api.routers.atera import router as atera_router
from app.api.routers.auth import router as auth_router
from app.api.routers.core import router as core_router
from app.api.routers.dashboard import router as dashboard_router
from app.api.routers.incidents import router as incidents_router
from app.api.routers.pipeline import router as pipeline_router
from app.api.routers.push import router as push_router
from app.api.routers.secops import router as secops_router
from app.api.routers.tenants import router as tenants_router
from app.config import get_settings
from app.database import SessionLocal

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="ness.OS",
    description=(
        "ness.OS — Sistema Operacional da ness. | "
        "Modulos: n.infraops (NOC/Infra) · n.secops (SOC/Seguranca) · core (Gestao)"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://hub.ness.com.br",
        "https://api.ness.com.br",
        "http://localhost",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ness.OS Core ---
app.include_router(core_router)  # prefix: /api/core

# --- n.infraops ---
app.include_router(webhooks_router)
app.include_router(v1_alerts_router)
app.include_router(v1_alerts_router, prefix="/api")
if _has_contabo and contabo_router is not None:
    app.include_router(contabo_router, prefix="/api/contabo", tags=["contabo"])
app.include_router(dashboard_router, tags=["infraops-dashboard"])
app.include_router(pipeline_router, tags=["infraops-pipeline"])
app.include_router(incidents_router, tags=["infraops-incidents"])
app.include_router(tenants_router, prefix="/api/tenants", tags=["infraops-tenants"])
app.include_router(assets_router, prefix="/api/assets", tags=["infraops-assets"])
app.include_router(atera_router)  # prefix: /api/rmm/atera

# --- n.secops ---
app.include_router(secops_router)  # prefix: /api/secops

# --- Auth (compartilhado) ---
app.include_router(auth_router)  # prefix: /api/auth
app.include_router(push_router)  # prefix: /api/v1/push


@app.get("/", tags=["root"])
async def root() -> dict:
    return {
        "platform": "ness.OS",
        "service": "n.infraops",
        "version": "1.0.0",
        "status": "running",
        "modules": ["n.infraops", "n.secops", "core"],
    }


@app.get("/ready", tags=["system"])
async def ready() -> dict[str, str]:
    """Container readiness: API, PostgreSQL and both Redis connections."""

    async def probe() -> None:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        for url in (settings.redis_url, settings.celery_broker_url):
            client = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
            try:
                if await client.ping() is not True:
                    raise ConnectionError("Redis did not confirm readiness")
            finally:
                await client.aclose()

    try:
        await asyncio.wait_for(probe(), timeout=4)
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "API readiness failed: %s", type(exc).__name__
        )
        raise HTTPException(status_code=503, detail="unavailable") from None
    return {"status": "ready"}
