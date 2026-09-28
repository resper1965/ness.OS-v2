import logging
from typing import Any, Dict, Iterable, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.dependencies import (
    require_authenticated,
    require_noc,
    resolve_tenant_scope,
)
from app.core.security import SecurityScanner
from app.database import SessionLocal
from app.models.models import Asset, CustomerCredentials
from app.models.users import User

logger = logging.getLogger(__name__)
router = APIRouter()


def _tenant_failure(operation: str, error: Exception) -> HTTPException:
    logger.error("Tenant %s failed: %s", operation, type(error).__name__)
    return HTTPException(status_code=500, detail="Dados de tenants indisponíveis.")


def _tenant_list(rows: Iterable[tuple[str | None, str | None]]) -> list[dict[str, str]]:
    """Return one stable selector entry for each usable tenant identifier."""
    tenants: dict[str, str] = {}
    for tenant_id, tenant_name in rows:
        if not tenant_id:
            continue
        identifier = tenant_id.strip().lower()
        if identifier:
            tenants.setdefault(identifier, (tenant_name or tenant_id).strip())

    return [
        {"id": tenant_id, "name": tenants[tenant_id]}
        for tenant_id in sorted(tenants, key=lambda value: tenants[value].casefold())
    ]


@router.get("/health", tags=["system"], dependencies=[Depends(require_noc)])
async def system_health():
    """Check connectivity with all integrated components."""
    from cli.contabo.api_client import ContaboAPIClient

    from app.integrations.zabbix import ZabbixClient

    health = {
        "zabbix": "down",
        "contabo": "down",
        "database": "down",
        "status": "warning",
    }

    try:
        z = ZabbixClient()
        await z._call("apiinfo.version", {})
        health["zabbix"] = "up"
    except Exception:
        logger.warning("Zabbix health check failed", exc_info=True)

    try:
        c = ContaboAPIClient()
        c.get("/compute/instances")
        health["contabo"] = "up"
    except Exception:
        logger.warning("Contabo health check failed", exc_info=True)

    try:
        async with SessionLocal() as session:
            await session.execute(select(1))
            health["database"] = "up"
    except Exception:
        logger.warning("Database health check failed", exc_info=True)

    if all(v == "up" for k, v in health.items() if k != "status"):
        health["status"] = "healthy"

    return health


@router.get(
    "/security-audit",
    tags=["system"],
    dependencies=[Depends(require_noc)],
)
async def security_audit():
    """Run a local security and update audit."""
    scanner = SecurityScanner()
    return scanner.run_all()


@router.get(
    "/list",
    response_model=List[Dict[str, Any]],
    dependencies=[Depends(require_noc)],
)
async def list_tenants():
    """List all available tenants (customers)."""
    async with SessionLocal() as session:
        try:
            # CustomerCredentials is the primary source. A tenant can have multiple
            # provider credentials, but the selector must expose it only once.
            stmt = select(CustomerCredentials)
            result = await session.execute(stmt)
            credentials = result.scalars().all()

            # If no credentials, check Assets for legacy customer_ids
            if not credentials:
                stmt_assets = select(Asset.customer_id, Asset.customer_name).distinct()
                result_assets = await session.execute(stmt_assets)
                rows = result_assets.all()
                return _tenant_list((r.customer_id, r.customer_name) for r in rows)

            return _tenant_list(
                (credential.customer_id, credential.customer_id)
                for credential in credentials
            )
        except Exception as error:
            raise _tenant_failure("list", error)


@router.get("/{tenant_id}/summary")
async def get_tenant_summary(
    tenant_id: str,
    current_user: User = Depends(require_authenticated),
):
    """Get a quick health summary for a specific tenant."""
    tenant_scope = resolve_tenant_scope(current_user, tenant_id)
    async with SessionLocal() as session:
        try:
            # Assets count
            asset_stmt = select(Asset).where(Asset.customer_id == tenant_scope)
            asset_result = await session.execute(asset_stmt)
            assets = asset_result.scalars().all()

            return {
                "tenant_id": tenant_scope,
                "assets_count": len(assets),
                "status": "active",
            }
        except Exception as error:
            raise _tenant_failure("summary", error)
