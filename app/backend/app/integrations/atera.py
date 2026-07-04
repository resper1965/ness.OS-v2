"""
n.infraops — Atera RMM API v3 Integration
Base URL: https://app.atera.com/api/v3
Auth: Static API Key via X-API-KEY header (permanente, sem refresh)
Rate Limit: 700 req/min
Pagination: page + itemsInPage (max 50 por pagina)
"""
import httpx
import logging
from typing import Any

logger = logging.getLogger(__name__)

ATERA_BASE_URL = "https://app.atera.com/api/v3"


class AteraClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self) -> dict:
        return {
            "X-API-KEY": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _paginate(self, endpoint: str, data_key: str, params: dict | None = None) -> list[dict[str, Any]]:
        """Busca todas as páginas de um endpoint paginado."""
        results = []
        page = 1
        while True:
            p = {"page": page, "itemsInPage": 50, **(params or {})}
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{ATERA_BASE_URL}{endpoint}", headers=self._headers(), params=p)
                r.raise_for_status()
                body = r.json()
            items = body.get(data_key, body.get("items", []))
            results.extend(items)
            if not body.get("nextLink"):
                break
            page += 1
        return results

    # -------------------------------------------------------
    # CUSTOMERS
    # -------------------------------------------------------
    async def list_customers(self) -> list[dict[str, Any]]:
        """Lista todos os clientes/tenants do Atera."""
        return await self._paginate("/customers", "items")

    async def get_customer(self, customer_id: int) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{ATERA_BASE_URL}/customers/{customer_id}", headers=self._headers())
            r.raise_for_status()
            return r.json()

    # -------------------------------------------------------
    # AGENTS (Workstations & Servers com agente instalado)
    # -------------------------------------------------------
    async def list_agents(self) -> list[dict[str, Any]]:
        """Lista todos os agentes (endpoints monitorados) do Atera."""
        return await self._paginate("/agents", "items")

    async def list_agents_by_customer(self, customer_id: int) -> list[dict[str, Any]]:
        """Lista agentes de um cliente específico."""
        return await self._paginate(f"/agents/customer/{customer_id}", "items")

    async def get_agent(self, agent_id: int) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{ATERA_BASE_URL}/agents/{agent_id}", headers=self._headers())
            r.raise_for_status()
            return r.json()

    # -------------------------------------------------------
    # ALERTS
    # -------------------------------------------------------
    async def list_alerts(self) -> list[dict[str, Any]]:
        """Lista todos os alertas ativos do Atera."""
        return await self._paginate("/alerts", "items")

    async def dismiss_alert(self, alert_id: int, approved_by: str) -> dict[str, Any]:
        """[HITL] Remove/fecha um alerta do Atera."""
        logger.info(f"[HITL] Dismissing Atera alert={alert_id} by={approved_by}")
        async with httpx.AsyncClient() as client:
            r = await client.delete(f"{ATERA_BASE_URL}/alerts/{alert_id}", headers=self._headers())
            r.raise_for_status()
            return {"status": "dismissed", "alert_id": alert_id, "approved_by": approved_by}

    # -------------------------------------------------------
    # TICKETS
    # -------------------------------------------------------
    async def list_tickets(self) -> list[dict[str, Any]]:
        """Lista todos os tickets do Atera."""
        return await self._paginate("/tickets", "items")

    async def create_ticket(self, title: str, customer_id: int, description: str = "", priority: str = "Low") -> dict[str, Any]:
        """Cria um ticket no Atera (ex: disparado por alerta do Zabbix/Keep)."""
        payload = {
            "TicketTitle": title,
            "TicketPriority": priority,
            "TicketType": "Incident",
            "CustomerID": customer_id,
            "TicketNotes": description,
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{ATERA_BASE_URL}/tickets", headers=self._headers(), json=payload)
            r.raise_for_status()
            return r.json()

    # -------------------------------------------------------
    # SUMMARY para o Dashboard n.infraops
    # -------------------------------------------------------
    async def get_dashboard_summary(self) -> dict[str, Any]:
        """Retorna um resumo consolidado para o painel."""
        try:
            customers = await self.list_customers()
            agents = await self.list_agents()
            alerts = await self.list_alerts()
            online = sum(1 for a in agents if a.get("OnlineStatus") == "Online")
            return {
                "source": "atera",
                "total_customers": len(customers),
                "total_agents": len(agents),
                "agents_online": online,
                "agents_offline": len(agents) - online,
                "active_alerts": len(alerts),
            }
        except Exception as e:
            logger.error(f"Atera summary error: {e}")
            return {"source": "atera", "error": str(e)}
