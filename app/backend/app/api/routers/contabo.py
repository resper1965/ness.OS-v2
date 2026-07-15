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
        raise HTTPException(status_code=500, detail="Contabo CLI integration failed or missing credentials.")

# --- Compute Advanced ---
@router.post("/compute/{instance_id}/reinstall")
def reinstall_instance(instance_id: int, image_id: str, client: ContaboAPIClient = Depends(get_contabo_client)):
    """Reinstall a VPS with a specific OS image."""
    try:
        client.post(f"/compute/instances/{instance_id}/reinstall", json_data={"imageId": image_id})
        return {"status": "success", "message": "Reinstallation started."}
    except Exception as e:
        logger.error(f"Reinstall failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/compute/{instance_id}/vnc")
def get_vnc(instance_id: int, client: ContaboAPIClient = Depends(get_contabo_client)):
    """Get VNC console connection details."""
    try:
        return client.get(f"/compute/instances/{instance_id}/vnc")
    except Exception as e:
        logger.error(f"VNC fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Snapshots ---
@router.post("/compute/{instance_id}/snapshots")
def create_snapshot(instance_id: int, name: str, description: str = "", client: ContaboAPIClient = Depends(get_contabo_client)):
    """Create a new snapshot."""
    try:
        return client.post(f"/compute/instances/{instance_id}/snapshots", json_data={"name": name, "description": description})
    except Exception as e:
        logger.error(f"Snapshot creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/compute/{instance_id}/snapshots/{snapshot_id}")
def delete_snapshot(instance_id: int, snapshot_id: str, client: ContaboAPIClient = Depends(get_contabo_client)):
    """Delete a specific snapshot."""
    try:
        client.delete(f"/compute/instances/{instance_id}/snapshots/{snapshot_id}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Snapshot deletion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/compute/{instance_id}/snapshots/{snapshot_id}/rollback")
def rollback_snapshot(instance_id: int, snapshot_id: str, client: ContaboAPIClient = Depends(get_contabo_client)):
    """Rollback instance to a specific snapshot."""
    try:
        client.post(f"/compute/instances/{instance_id}/snapshots/{snapshot_id}/rollback")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Secrets ---
@router.get("/secrets")
def list_secrets(client: ContaboAPIClient = Depends(get_contabo_client)):
    """List all SSH keys and secrets."""
    try:
        return client.get("/secrets").get("data", [])
    except Exception as e:
        logger.error(f"Secrets fetch failed: {e}")
        return []

@router.post("/secrets")
def create_secret(name: str, value: str, secret_type: str = "ssh", client: ContaboAPIClient = Depends(get_contabo_client)):
    """Create a new secret (SSH key)."""
    try:
        return client.post("/secrets", json_data={"name": name, "value": value, "type": secret_type})
    except Exception as e:
        logger.error(f"Secret creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

@router.post("/compute/{instance_id}/actions/{action}")
def compute_action(instance_id: int, action: str, client: ContaboAPIClient = Depends(get_contabo_client)):
    """Start, stop or shutdown a specific VPS instance."""
    if action not in ["start", "stop", "shutdown", "restart"]:
        raise HTTPException(status_code=400, detail="Invalid action. Use start, stop, shutdown or restart.")
    try:
        client.post(f"/compute/instances/{instance_id}/actions/{action}")
        return {"status": "success", "message": f"Action {action} on instance {instance_id} initiated."}
    except Exception as e:
        logger.error(f"Failed action {action} on instance {instance_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/compute/{instance_id}/snapshots")
def list_snapshots(instance_id: int, client: ContaboAPIClient = Depends(get_contabo_client)):
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
                "stopped": len(instances) - running
            },
            "storage": {
                "total_tb": total_storage,
                "buckets": len(storages)
            }
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
            fut_secrets = executor.submit(client.get, "/secrets")
            fut_img = executor.submit(client.get, "/compute/images")
            
            instances = fut_inst.result().get("data", [])
            storages = fut_stor.result().get("data", [])
            firewalls = fut_fire.result().get("data", [])
            networks = fut_net.result().get("data", [])
            audits = fut_audits.result().get("data", [])
            secrets = fut_secrets.result().get("data", [])
            images = fut_img.result().get("data", [])
        
        running = sum(1 for i in instances if i.get("status") == "running")
        total_storage = sum(float(s.get("totalSpaceTb", 0)) for s in storages)
        
        summary = {
            "instances": {
                "total": len(instances),
                "running": running,
                "stopped": len(instances) - running
            },
            "storage": {
                "total_tb": total_storage,
                "buckets": len(storages)
            }
        }
        
        return {
            "summary": summary,
            "instances": instances,
            "storage": storages,
            "firewalls": firewalls,
            "networks": networks,
            "audits": audits,
            "secrets": secrets,
            "images": images
        }
    except Exception as e:
        logger.error(f"Failed to fetch dashboard full: {e}")
        raise HTTPException(status_code=500, detail=str(e))

