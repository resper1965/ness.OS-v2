# -------------------------------------------------------
# n.infraops — Auth Router (FASE 4.1 / 4.4)
# -------------------------------------------------------
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timezone

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import get_current_user, is_noc_role
from app.core.jwt import create_access_token
from app.core.oidc import exchange_oidc_code, verify_oidc_token
from app.core.session import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    require_trusted_origin,
    set_session_cookie,
)
from app.database import get_db
from app.models.users import User, UserRole

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
_logout_bearer = HTTPBearer(auto_error=False)


# ── Schemas ──────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: str  # str simples evita dep. email-validator
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str | None


class MeResponse(BaseModel):
    id: int
    email: str
    full_name: str | None
    role: str


class SeedResponse(BaseModel):
    detail: str


# ── Helpers ───────────────────────────────────────────────────────────────────


def _hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


_AUTHENTIK_GROUP_ROLE_PRIORITY = (
    ({"platform_admin", "ness-os-platform-admin"}, UserRole.platform_admin),
    ({"admin"}, UserRole.admin),
    ({"viewer"}, UserRole.viewer),
    ({"operator"}, UserRole.operator),
    ({"noc"}, UserRole.noc),
    ({"soc"}, UserRole.soc),
    ({"helpdesk"}, UserRole.helpdesk),
    ({"gestao"}, UserRole.gestao),
    ({"usuarios"}, UserRole.cliente),
)


def map_authentik_role(claims: dict) -> UserRole:
    """Mapeia grupos/role sem depender de um único nome legado de grupo."""
    groups = claims.get("groups", [])
    if isinstance(groups, str):
        groups = [groups]
    normalized_groups = {str(group).strip().lower() for group in groups}

    for aliases, role in _AUTHENTIK_GROUP_ROLE_PRIORITY:
        if normalized_groups.intersection(aliases):
            return role

    if not normalized_groups:
        raw_role = str(claims.get("role", "cliente")).lower()
        try:
            return UserRole(raw_role)
        except ValueError:
            pass
    return UserRole.cliente


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/login",
    response_model=MeResponse | TokenResponse,
    summary="Login com e-mail e senha",
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MeResponse | TokenResponse:
    """
    Inicia uma sessão segura para o Hub. Clientes não-browser sem cabeçalho
    ``Origin`` mantêm a resposta Bearer para compatibilidade com automações.

    - **401** se e-mail não encontrado ou senha incorreta
    - **403** se conta inativa
    """
    browser_request = request.headers.get("origin") is not None
    if browser_request:
        require_trusted_origin(request)
    result = await db.execute(select(User).where(User.email == body.email))
    user: User | None = result.scalar_one_or_none()

    if not user or not _verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta inativa. Entre em contato com o administrador.",
        )

    # Atualiza last_login
    user.last_login = datetime.now(tz=timezone.utc)
    await db.commit()

    token = create_access_token(
        user_id=user.id,
        role=user.role.value,
        extra_claims={
            "tenant_id": user.tenant_id,
            "session_epoch": getattr(user, "session_epoch", 0),
        },
    )
    if not browser_request:
        return TokenResponse(
            access_token=token,
            role=user.role.value,
            full_name=user.full_name,
        )

    set_session_cookie(response, token)
    logger.info("Login bem-sucedido: user_id=%s email=%s", user.id, user.email)

    return MeResponse(
        id=user.id,
        email=user.email,
        role=user.role.value,
        full_name=user.full_name,
    )


@router.get(
    "/me", response_model=MeResponse, summary="Retorna dados do usuário autenticado"
)
async def me(
    current_user: User = Depends(get_current_user),
) -> MeResponse:
    """
    Retorna os dados do usuário autenticado via cookie ou Bearer token.

    - **401** se token ausente, inválido ou expirado
    """
    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Encerra a sessão",
)
async def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(_logout_bearer),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Revoga as sessões locais do usuário e remove o cookie do navegador."""
    require_trusted_origin(request)
    if credentials is not None or request.cookies.get(SESSION_COOKIE_NAME):
        try:
            user = await get_current_user(request, credentials, db)
        except HTTPException:
            pass  # Token já inválido; ainda limpamos o cookie local.
        else:
            user.session_epoch = getattr(user, "session_epoch", 0) + 1
            await db.commit()
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post(
    "/seed",
    response_model=SeedResponse,
    summary="Cria usuário admin padrão (somente DEBUG=true)",
)
async def seed_admin(
    db: AsyncSession = Depends(get_db),
) -> SeedResponse:
    """
    Cria o usuário administrador padrão (`admin@ness.com.br`).

    Disponível **apenas** quando `NINF_DEBUG=true`. Idempotente: retorna 200 se já existir.

    - **403** se `DEBUG` estiver desativado
    """
    settings = get_settings()
    if not settings.debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Endpoint disponível apenas em modo DEBUG",
        )

    SEED_EMAIL = "admin@ness.com.br"
    SEED_PASSWORD = os.getenv("NINF_SEED_ADMIN_PASSWORD")
    SEED_FULL_NAME = "Administrador n.infraops"

    if not SEED_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NINF_SEED_ADMIN_PASSWORD não configurada",
        )

    result = await db.execute(select(User).where(User.email == SEED_EMAIL))
    existing: User | None = result.scalar_one_or_none()

    if existing:
        logger.info("Seed: usuário admin já existe (id=%s)", existing.id)
        return SeedResponse(detail="Usuário admin já existe")

    admin = User(
        email=SEED_EMAIL,
        hashed_password=_hash_password(SEED_PASSWORD),
        full_name=SEED_FULL_NAME,
        role=UserRole.admin,
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    logger.info("Seed: usuário admin criado (id=%s)", admin.id)

    return SeedResponse(detail=f"Usuário admin criado com id={admin.id}")


# --- Authentik OIDC BFF Callback (Task 3) ---


class OidcCallbackRequest(BaseModel):
    code: str
    redirect_uri: str
    code_verifier: str | None = None


@router.post(
    "/oidc/callback",
    response_model=MeResponse,
    summary="Callback OIDC para troca de tokens com Authentik (BFF)",
)
async def oidc_callback(
    body: OidcCallbackRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    require_trusted_origin(request)
    settings = get_settings()
    if not settings.oidc_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Autenticação OIDC desabilitada no servidor.",
        )

    # 1. Trocar código OIDC no Authentik
    try:
        token_payload = await exchange_oidc_code(
            body.code, body.redirect_uri, body.code_verifier
        )
    except Exception as e:
        logger.error(f"Erro na troca do código OIDC: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Falha ao autenticar com o Authentik SSO (troca de código falhou).",
        )

    id_token = token_payload.get("id_token")

    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentik não retornou um token de identidade válido.",
        )

    # 2. Validar token
    try:
        claims = await verify_oidc_token(id_token)
    except Exception as e:
        logger.error(f"Token OIDC inválido: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token OIDC fornecido pelo Authentik é inválido ou expirou.",
        )

    email = claims.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token OIDC do Authentik não possui a claim obrigatória 'email'.",
        )

    user_role = map_authentik_role(claims)

    raw_tenant = claims.get("tenant_id")
    if raw_tenant is not None and not isinstance(raw_tenant, str):
        raise HTTPException(
            status_code=403, detail="Cliente informado pelo SSO é inválido"
        )
    tenant_id = (raw_tenant or "").strip().lower()
    if len(tenant_id) > 128 or (not is_noc_role(user_role) and not tenant_id):
        raise HTTPException(
            status_code=403,
            detail="Usuário sem cliente associado no SSO. Solicite o vínculo ao administrador.",
        )
    full_name = claims.get("name") or claims.get("given_name")

    # 3. Just-In-Time Provisioning
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        logger.info(f"OIDC JIT: Criando novo usuário local para o e-mail: {email}")
        random_pwd = secrets.token_urlsafe(32)
        user = User(
            email=email,
            hashed_password=_hash_password(random_pwd),
            full_name=full_name,
            role=user_role,
            tenant_id=tenant_id,
            is_active=True,
        )
        db.add(user)
    else:
        if not user.is_active:
            raise HTTPException(
                status_code=403,
                detail="Conta inativa. Entre em contato com o administrador.",
            )
        logger.info(f"OIDC JIT: Atualizando usuário local existente: {email}")
        user.role = user_role
        user.tenant_id = tenant_id
        if full_name:
            user.full_name = full_name

    await db.commit()
    await db.refresh(user)

    # 4. Emitir JWT de sessão local compatível com o n.infraops
    local_token = create_access_token(
        user_id=user.id,
        role=user.role.value,
        extra_claims={
            "tenant_id": user.tenant_id,
            "session_epoch": getattr(user, "session_epoch", 0),
        },
    )
    set_session_cookie(response, local_token)

    return MeResponse(
        id=user.id,
        email=user.email,
        role=user.role.value,
        full_name=user.full_name,
    )
