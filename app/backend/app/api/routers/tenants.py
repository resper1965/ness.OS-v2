import logging
from typing import Any, Dict, List

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
            # We fetch unique customer_ids from Asset or CustomerCredentials
            # For now, let's use the CustomerCredentials table as the source of truth for tenants
            stmt = select(CustomerCredentials)
            result = await session.execute(stmt)
            credentials = result.scalars().all()

            # If no credentials, check Assets for legacy customer_ids
            if not credentials:
                stmt_assets = select(Asset.customer_id, Asset.customer_name).distinct()
                result_assets = await session.execute(stmt_assets)
                rows = result_assets.all()
                return [
                    {"id": r.customer_id, "name": r.customer_name or r.customer_id}
                    for r in rows
                    if r.customer_id
                ]

            return [
                {
                    "id": cred.customer_id,
                    "name": cred.customer_id,  # Can be enhanced with a real Tenant table later
                    "provider": cred.provider,
                }
                for cred in credentials
            ]
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
