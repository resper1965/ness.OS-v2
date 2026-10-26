from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from cli.contabo.api_client import ContaboAPIClient
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def get_contabo_client() -> ContaboAPIClient:
    try:
        return ContaboAPIClient()
    except Exception as e:
        logger.error(f"Failed to initialize Contabo client: {e}")
        raise HTTPException(
            status_code=500,
            detail="Contabo CLI integration failed or missing credentials.",
        )


@router.get("/compute", response_model=List[Dict[str, Any]])
def list_instances(client: ContaboAPIClient = Depends(get_contabo_client)):
    """List all VPS instances from Contabo."""
    try:
        response = client.get("/compute/instances")
        return response.get("data", [])
    except Exception as e:
        logger.error(f"Failed to fetch Contabo instances: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compute/{instance_id}/restart")
def restart_instance(
    instance_id: int, client: ContaboAPIClient = Depends(get_contabo_client)
):
    """Restart a specific VPS instance."""
    try:
        # Contabo restart action URL
        client.post(f"/compute/instances/{instance_id}/actions/restart")
        return {
            "status": "success",
            "message": f"Instance {instance_id} restart initiated.",
        }
    except Exception as e:
        logger.error(f"Failed to restart instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/storage", response_model=List[Dict[str, Any]])
def list_storage(client: ContaboAPIClient = Depends(get_contabo_client)):
    """List all Object Storages from Contabo."""
    try:
        response = client.get("/object-storages")
        return response.get("data", [])
    except Exception as e:
        logger.error(f"Failed to fetch Contabo object storage: {e}")
        raise HTTPException(status_code=500, detail=str(e))
