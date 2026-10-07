from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import select, desc
from app.database import SessionLocal
from app.models.models import CustomerCredentials, Asset
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)
from typing import List, Dict, Any
import logging
from app.core.security import SecurityScanner

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/health", tags=["system"])
async def system_health():
    """Check connectivity with all integrated components."""
    from app.integrations.zabbix import ZabbixClient
    from cli.contabo.api_client import ContaboAPIClient
    
    health = {
        "zabbix": "down",
        "contabo": "down",
        "database": "down",
        "status": "warning"
    }
    
    try:
        z = ZabbixClient()
        await z._call("apiinfo.version", {})
        health["zabbix"] = "up"
    except: pass

    try:
        c = ContaboAPIClient()
        c.get("/compute/instances")
        health["contabo"] = "up"
    except: pass

    try:
        async with SessionLocal() as session:
            await session.execute(select(1))
            health["database"] = "up"
    except: pass

    if all(v == "up" for k, v in health.items() if k != "status"):
        health["status"] = "healthy"
        
    return health

@router.get("/security-audit", tags=["system"])
async def security_audit():
    """Run a local security and update audit."""
    scanner = SecurityScanner()
    return scanner.run_all()

@router.get("/list", response_model=List[Dict[str, Any]])
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
                return [{"id": r.customer_id, "name": r.customer_name or r.customer_id} for r in rows if r.customer_id]

            return [
                {
                    "id": cred.customer_id,
                    "name": cred.customer_id, # Can be enhanced with a real Tenant table later
                    "provider": cred.provider
                } 
                for cred in credentials
            ]
        except Exception as e:
            logger.error(f"Failed to list tenants: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/{tenant_id}/summary")
async def get_tenant_summary(tenant_id: str):
    """Get a quick health summary for a specific tenant."""
    async with SessionLocal() as session:
        try:
            # Assets count
            asset_stmt = select(Asset).where(Asset.customer_id == tenant_id)
            asset_result = await session.execute(asset_stmt)
            assets = asset_result.scalars().all()
            
            return {
                "tenant_id": tenant_id,
                "assets_count": len(assets),
                "status": "active"
            }
        except Exception as e:
            logger.error(f"Failed to get tenant summary: {e}")
            raise HTTPException(status_code=500, detail=str(e))
