"""
n.infraops — Dependências RBAC
Uso: adicione como Depends() em qualquer endpoint que precise de autenticação/autorização.

Exemplos:
    @router.get("/admin-only")
    async def admin(user: User = Depends(require_admin)):
        ...

    @router.get("/noc-or-admin")
    async def noc(user: User = Depends(require_authenticated)):
        ...
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import verify_token
from app.database import get_db
from app.models.users import User, UserRole

_bearer = HTTPBearer(auto_error=False)

NOC_ROLES = frozenset(
    {
        UserRole.noc,
        UserRole.soc,
        UserRole.admin,
        UserRole.platform_admin,
    }
)


def is_noc_role(role: UserRole | str | None) -> bool:
    """Return whether a persisted role or JWT role value is an operator role."""
    try:
        return UserRole(role) in NOC_ROLES
    except (TypeError, ValueError):
        return False


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency base: valida Bearer JWT e retorna o User. Levanta 401 se inválido."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticacao ausente",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = verify_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario nao encontrado ou inativo",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_authenticated(user: User = Depends(get_current_user)) -> User:
    """Qualquer role autenticada (noc, admin, cliente)."""
    return user


def require_noc(user: User = Depends(get_current_user)) -> User:
    """Role noc, soc, admin ou platform_admin."""
    if not is_noc_role(user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a operadores NOC/SOC",
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Admin local ou platform_admin global."""
    if user.role not in (UserRole.admin, UserRole.platform_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores",
        )
    return user


def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    """Administração global da plataforma e do plano de controle."""
    if user.role != UserRole.platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores da plataforma",
        )
    return user


def require_role(*roles: UserRole):
    """Factory: exige um dos roles listados.

    Uso:
        @router.get("/")
        async def ep(user: User = Depends(require_role(UserRole.admin, UserRole.noc))):
    """

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso restrito a: {', '.join(r.value for r in roles)}",
            )
        return user

    return _check
