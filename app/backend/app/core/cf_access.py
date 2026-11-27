"""
Validação do JWT do Cloudflare Access (Cf-Access-Jwt-Assertion).

Quando o Hub está atrás do Cloudflare Access, toda requisição autenticada
carrega um header `Cf-Access-Jwt-Assertion` assinado pela Cloudflare.
Este módulo valida a assinatura (RS256) contra os JWKS públicos do
Cloudflare Access e extrai o e-mail do token.

Configuração necessária:
  NINF_CF_ACCESS_AUD — audience tag da aplicação Access (ex: "abc123...")
  NINF_CF_ACCESS_ENABLED — bool (default false)

Referência: https://developers.cloudflare.com/cloudflare-one/identity/authorization-cookie/validating-json/
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError

from app.config import get_settings

logger = logging.getLogger("nessops.cf_access")

# Cache do JWKS (5 min TTL)
_jwks_cache: tuple[list[dict[str, Any]], float] | None = None
_JWKS_URL = "https://{team_domain}/cdn-cgi/access/certs"


async def _fetch_jwks(client: httpx.AsyncClient, team_domain: str) -> list[dict[str, Any]]:
    """Busca os JWKS do Cloudflare Access."""
    global _jwks_cache

    now = time.time()
    if _jwks_cache and (now - _jwks_cache[1]) < 300:
        return _jwks_cache[0]

    url = _JWKS_URL.format(team_domain=team_domain)
    logger.debug("Fetching CF Access JWKS: %s", url)
    res = await client.get(url)
    res.raise_for_status()
    data = res.json()
    keys = data.get("keys", [])
    _jwks_cache = (keys, now)
    return keys


async def validate_cf_access_token(token: str) -> dict[str, Any]:
    """
    Valida o JWT do Cloudflare Access.

    Retorna as claims se válido.
    Levanta ValueError se inválido/expirado.
    """
    settings = get_settings()
    aud = settings.cf_access_aud
    team_domain = settings.cf_access_team_domain

    if not aud:
        raise ValueError("NINF_CF_ACCESS_AUD não configurado")

    # Decodifica o header sem validar, para pegar o kid
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise ValueError("Token JWT malformado")

    kid = unverified_header.get("kid")
    if not kid:
        raise ValueError("Token JWT sem kid")

    async with httpx.AsyncClient(timeout=10) as client:
        jwks = await _fetch_jwks(client, team_domain)

    # Encontra a chave correspondente
    matching_jwk = None
    for jwk in jwks:
        if jwk.get("kid") == kid:
            matching_jwk = jwk
            break

    if not matching_jwk:
        logger.warning("CF Access JWK kid=%s não encontrado nos JWKS", kid)
        raise ValueError("Chave de assinatura não encontrada")

    # python-jose aceita a JWK diretamente como chave
    try:
        claims = jwt.decode(
            token,
            key=matching_jwk,
            algorithms=["RS256"],
            audience=aud,
            issuer=f"https://{team_domain}",
            options={"require": ["exp", "iss", "aud", "email"]},
        )
    except ExpiredSignatureError:
        raise ValueError("Token Cloudflare Access expirado")
    except JWTClaimsError as e:
        raise ValueError(f"Token Cloudflare Access com claims inválidas: {e}")
    except JWTError as e:
        raise ValueError(f"Token Cloudflare Access inválido: {e}")

    logger.debug("CF Access token validado: email=%s", claims.get("email"))
    return claims
