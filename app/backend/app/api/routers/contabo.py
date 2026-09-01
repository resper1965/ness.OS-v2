from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from cli.contabo.api_client import ContaboAPIClient
from app.core.dependencies import require_platform_admin
import logging

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_platform_admin)])


def get_contabo_client() -> ContaboAPIClient:
    try:
        return ContaboAPIClient()
    except Exception as e:
        logger.error(f"Failed to initialize Contabo client: {e}")
        raise HTTPException(
            status_code=500,
            detail="Contabo CLI integration failed or missing credentials.",
        )


# --- Infrastructure ---
@router.get("/compute", response_model=List[Dict[str, Any]])
def list_instances(client: ContaboAPIClient = Depends(get_contabo_client)):
    """List all VPS instances from Contabo."""
    try:
        response = client.get("/compute/instances")
        return response.get("data", [])
    except Exception as e:
        logger.error(f"Failed to fetch Contabo instances: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compute/{instance_id}/snapshots")
def list_snapshots(
    instance_id: int, client: ContaboAPIClient = Depends(get_contabo_client)
):
    """List snapshots for a specific instance."""
    try:
        response = client.get(f"/compute/instances/{instance_id}/snapshots")
        return response.get("data", [])
    except Exception as e:
        logger.error(f"Failed to fetch snapshots for {instance_id}: {e}")
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


@router.get("/summary")
def get_cloud_summary(client: ContaboAPIClient = Depends(get_contabo_client)):
    """Aggregated summary of cloud resources for the dashboard header."""
    try:
        instances = client.get("/compute/instances").get("data", [])
        storages = client.get("/object-storages").get("data", [])

        running = sum(1 for i in instances if i.get("status") == "running")
        total_storage = sum(float(s.get("totalSpaceTb", 0)) for s in storages)

        return {
            "instances": {
                "total": len(instances),
                "running": running,
                "stopped": len(instances) - running,
            },
            "storage": {"total_tb": total_storage, "buckets": len(storages)},
        }
    except Exception as e:
        logger.error(f"Failed to generate cloud summary: {e}")
        return {"error": str(e)}


@router.get("/firewall", response_model=List[Dict[str, Any]])
def list_firewalls(client: ContaboAPIClient = Depends(get_contabo_client)):
    """List all Cloud Firewalls."""
    try:
        response = client.get("/firewalls")
        return response.get("data", [])
    except Exception as e:
        logger.error(f"Failed to fetch firewalls: {e}")
        return []


@router.get("/networks", response_model=List[Dict[str, Any]])
def list_networks(client: ContaboAPIClient = Depends(get_contabo_client)):
    """List all Private Networks (VPC)."""
    try:
        response = client.get("/private-networks")
        return response.get("data", [])
    except Exception as e:
        logger.error(f"Failed to fetch networks: {e}")
        return []


@router.get("/images", response_model=List[Dict[str, Any]])
def list_images(client: ContaboAPIClient = Depends(get_contabo_client)):
    """List all OS images (Standard and Custom)."""
    try:
        # Images are under compute in OpenAPI
        response = client.get("/compute/images")
        return response.get("data", [])
    except Exception as e:
        logger.error(f"Failed to fetch images: {e}")
        return []


@router.get("/audits", response_model=List[Dict[str, Any]])
def list_audits(client: ContaboAPIClient = Depends(get_contabo_client)):
    """List cloud activity audits for health tracking."""
    try:
        response = client.get("/compute/instances/audits")
        return response.get("data", [])
    except Exception as e:
        logger.error(f"Failed to fetch audits: {e}")
        return []


@router.get("/dashboard-full")
def get_dashboard_full(client: ContaboAPIClient = Depends(get_contabo_client)):
    """Unified endpoint to fetch all Contabo resources concurrently for the dashboard."""
    from concurrent.futures import ThreadPoolExecutor

    try:
        with ThreadPoolExecutor(max_workers=7) as executor:
            fut_inst = executor.submit(client.get, "/compute/instances")
            fut_stor = executor.submit(client.get, "/object-storages")
            fut_fire = executor.submit(client.get, "/firewalls")
            fut_net = executor.submit(client.get, "/private-networks")
            fut_audits = executor.submit(client.get, "/compute/instances/audits")
            fut_img = executor.submit(client.get, "/compute/images")

            instances = fut_inst.result().get("data", [])
            storages = fut_stor.result().get("data", [])
            firewalls = fut_fire.result().get("data", [])
            networks = fut_net.result().get("data", [])
            audits = fut_audits.result().get("data", [])
            images = fut_img.result().get("data", [])

        running = sum(1 for i in instances if i.get("status") == "running")
        total_storage = sum(float(s.get("totalSpaceTb", 0)) for s in storages)

        summary = {
            "instances": {
                "total": len(instances),
                "running": running,
                "stopped": len(instances) - running,
            },
            "storage": {"total_tb": total_storage, "buckets": len(storages)},
        }

        return {
            "summary": summary,
            "instances": instances,
            "storage": storages,
            "firewalls": firewalls,
            "networks": networks,
            "audits": audits,
            "images": images,
        }
    except Exception as e:
        logger.error(f"Failed to fetch dashboard full: {e}")
        raise HTTPException(status_code=500, detail=str(e))
