# -------------------------------------------------------
# n.infraops — JWT Helpers (FASE 4.1)
# -------------------------------------------------------
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt

from app.config import get_settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8


# Fallback secret gerado UMA VEZ no startup (nao sobrevive restart).
# Em producao, defina NINF_JWT_SECRET no .env ou docker-compose.
_FALLBACK_SECRET: str = secrets.token_hex(32)


def _secret() -> str:
    """Retorna o JWT secret configurado ou o fallback gerado no startup."""
    settings = get_settings()
    return settings.jwt_secret if settings.jwt_secret else _FALLBACK_SECRET


def create_access_token(
    user_id: int,
    role: str,
    expire_hours: int | None = None,
    token_version: int = 0,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Cria um JWT de acesso.

    Args:
        user_id:      PK do usuário (campo ``sub``).
        role:         Role do usuário ('noc', 'admin', 'cliente').
        expire_hours: Horas até expirar (padrão: ACCESS_TOKEN_EXPIRE_HOURS).
        extra_claims: Claims adicionais opcionais.

    Returns:
        Token JWT assinado como string.
    """
    settings = get_settings()
    hours = expire_hours if expire_hours is not None else settings.jwt_expire_hours
    expire = datetime.now(tz=timezone.utc) + timedelta(hours=hours)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "token_version": token_version,
        "exp": expire,
        "iat": datetime.now(tz=timezone.utc),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    """
    Valida e decodifica um JWT.

    Args:
        token: Token JWT como string.

    Returns:
        Payload decodificado.

    Raises:
        JWTError: Se o token for inválido, expirado ou mal formado.
    """
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
