from fastapi import APIRouter, HTTPException, Depends
from app.integrations.atera import AteraClient
from typing import List, Dict, Any
import os

router = APIRouter()

def get_atera_client():
    api_key = os.getenv("ATERA_API_KEY")
    if not api_key:
        # Fallback for testing/dev
        api_key = "dummy" 
    return AteraClient(api_key=api_key)

@router.get("/summary")
async def get_assets_summary(atera: AteraClient = Depends(get_atera_client)):
    """Consolidated summary of assets across all platforms."""
    agents = await atera.get_agents()
    
    # Mapping and counting
    total_agents = len(agents)
    online = sum(1 for a in agents if a.get("Online", False))
    
    return {
        "atera": {
            "total": total_agents,
            "online": online,
            "offline": total_agents - online
        },
        "datto": {
            "total": 0, # Pending Datto integration
            "alerts": 0
        }
    }

@router.get("/list")
async def list_all_assets(atera: AteraClient = Depends(get_atera_client)):
    """Detailed list of managed assets."""
    agents = await atera.get_agents()
    # Normalize data for frontend
    normalized = []
    for a in agents:
        normalized.append({
            "id": a.get("AgentID"),
            "name": a.get("MachineName"),
            "customer": a.get("CustomerName"),
            "os": a.get("OS"),
            "ip": a.get("IpAddresses"),
            "status": "online" if a.get("Online") else "offline",
            "source": "atera"
        })
    return normalized
