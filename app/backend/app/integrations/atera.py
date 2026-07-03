import httpx
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class AteraClient:
    def __init__(self, api_key: str, base_url: str = "https://app.atera.com/api/v3"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "X-API-KEY": self.api_key,
            "Accept": "application/json"
        }

    async def get_agents(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/agents", headers=self.headers)
                response.raise_for_status()
                return response.json().get("items", [])
            except Exception as e:
                logger.error(f"Atera API Error (Agents): {e}")
                return []

    async def get_customers(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/customers", headers=self.headers)
                response.raise_for_status()
                return response.json().get("items", [])
            except Exception as e:
                logger.error(f"Atera API Error (Customers): {e}")
                return []
