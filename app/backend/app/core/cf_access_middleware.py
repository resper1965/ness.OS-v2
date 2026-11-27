"""
Middleware Cloudflare Access — valida Cf-Access-Jwt-Assertion e
injeta o usuário autenticado na request.state.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings
from app.core.cf_access import validate_cf_access_token

logger = logging.getLogger("nessops.middleware.cf_access")

# Rotas públicas — não exigem autenticação
PUBLIC_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/auth/",
    "/api/v1/push/config",
    "/ready",
    "/health",
)


class CloudflareAccessMiddleware(BaseHTTPMiddleware):
    """Valida o JWT do Cloudflare Access em toda requisição não-pública."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()

        if not settings.cf_access_enabled:
            return await call_next(request)

        # Rotas públicas
        path = request.url.path
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        token = request.headers.get("Cf-Access-Jwt-Assertion")
        if not token:
            logger.debug("Cf-Access-Jwt-Assertion ausente em %s", path)
            return JSONResponse(
                status_code=401,
                content={"detail": "Autenticação via Cloudflare Access necessária."},
            )

        try:
            claims = await validate_cf_access_token(token)
        except ValueError as e:
            logger.warning("CF Access token inválido: %s", e)
            return JSONResponse(
                status_code=401,
                content={"detail": str(e)},
            )

        email = claims.get("email", "")
        # Injeta no state para uso por dependências (ex: get_current_user)
        request.state.cf_email = email
        request.state.cf_claims = claims

        logger.debug("CF Access autenticado: email=%s path=%s", email, path)
        return await call_next(request)
