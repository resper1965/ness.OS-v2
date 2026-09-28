# -------------------------------------------------------
# n.infraops — Utilitário OpenID Connect (Authentik OIDC)
# -------------------------------------------------------
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from jose import JWTError, jwt

from app.config import get_settings

logger = logging.getLogger("nessops.core.oidc")

# Cache de chaves públicas JWKS em memória
_JWKS_CACHE: dict[str, Any] = {}
_JWKS_CACHE_TIME: float = 0.0
JWKS_TTL_SECONDS = 3600  # 1 hora de cache


async def get_jwks() -> dict[str, Any]:
    """Obtém o JSON Web Key Set (JWKS) do Authentik SSO com cache em memória."""
    global _JWKS_CACHE, _JWKS_CACHE_TIME
    now = time.time()

    if _JWKS_CACHE and (now - _JWKS_CACHE_TIME < JWKS_TTL_SECONDS):
        return _JWKS_CACHE

    settings = get_settings()
    logger.info(f"Buscando JWKS do Authentik no endpoint: {settings.oidc_jwks_url}")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(settings.oidc_jwks_url)
            res.raise_for_status()
            jwks = res.json()
            _JWKS_CACHE = jwks
            _JWKS_CACHE_TIME = now
            logger.info("Chaves JWKS do Authentik atualizadas no cache com sucesso.")
            return jwks
    except Exception as exc:
        logger.error("Authentik JWKS load failed: %s", type(exc).__name__)
        if _JWKS_CACHE:
            logger.warning("Retornando JWKS expirado do cache devido a falha de rede.")
            return _JWKS_CACHE
        raise


async def verify_oidc_token(token: str) -> dict[str, Any]:
    """
    Valida a assinatura RS256 e as claims do token JWT OIDC contra o JWKS do Authentik.
    """
    settings = get_settings()
    jwks = await get_jwks()

    # jose.jwt.decode analisa as chaves do JWKS correspondendo pelo 'kid' do token
    try:
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.oidc_client_id,
            issuer=settings.oidc_issuer,
        )
        return payload
    except JWTError as exc:
        logger.error(
            "Authentik identity token validation failed: %s", type(exc).__name__
        )
        raise


async def exchange_oidc_code(
    code: str, redirect_uri: str, code_verifier: str | None = None
) -> dict[str, Any]:
    """
    Realiza o POST para trocar o código de autorização por tokens no Authentik
    usando o client_secret (BFF seguro).
    """
    settings = get_settings()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": settings.oidc_client_id,
        "client_secret": settings.oidc_client_secret,
    }
    if code_verifier:
        data["code_verifier"] = code_verifier

    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.post(settings.oidc_token_url, data=data)
        if not res.is_success:
            logger.error(
                "Authentik token exchange failed with HTTP %s", res.status_code
            )
            res.raise_for_status()
        return res.json()
