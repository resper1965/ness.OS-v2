"""
n.infraops — Atera RMM API v3 Integration
Base URL: https://app.atera.com/api/v3
Auth: Static API Key via X-API-KEY header (permanente, sem refresh)
Rate Limit: 700 req/min (~11.6/s). Retry automático em 429.
Pagination: page + itemsInPage (max 50 por página)
"""

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ATERA_BASE_URL = "https://app.atera.com/api/v3"
_REQUEST_DELAY = 0.15  # ~6 req/s — bem abaixo do limite de 700/min
_RETRY_DELAY = 2.0  # segundos de espera em 429
_MAX_RETRIES = 3


class AteraClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self) -> dict:
        return {
            "X-API-KEY": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _get(self, url: str, params: dict | None = None) -> dict[str, Any]:
        """GET com retry automático em 429 e delay entre requests."""
        for attempt in range(_MAX_RETRIES):
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(url, headers=self._headers(), params=params or {})
                if r.status_code == 429:
                    retry_after = float(r.headers.get("Retry-After", _RETRY_DELAY))
                    logger.warning(
                        f"Atera 429 rate limit — waiting {retry_after}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(retry_after)
                    continue
                r.raise_for_status()
                await asyncio.sleep(_REQUEST_DELAY)  # throttle pós-request
                return r.json()
        raise Exception("Atera API rate limit exceeded after max retries")

    async def _get_page_one(self, endpoint: str, page_size: int = 1) -> dict[str, Any]:
        """Busca apenas a primeira página — usado para obter totais eficientemente."""
        return await self._get(
            f"{ATERA_BASE_URL}{endpoint}",
            params={"page": 1, "itemsInPage": page_size},
        )

    async def _paginate(
        self,
        endpoint: str,
        data_key: str,
        params: dict | None = None,
        max_pages: int = 100,
    ) -> list[dict[str, Any]]:
        """Busca todas as páginas com throttling. Respeita max_pages."""
        results = []
        page = 1
        while page <= max_pages:
            p = {"page": page, "itemsInPage": 50, **(params or {})}
            body = await self._get(f"{ATERA_BASE_URL}{endpoint}", params=p)
            items = body.get(data_key, body.get("items", []))
            results.extend(items)
            if not body.get("nextLink") or not items:
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
        return await self._get(f"{ATERA_BASE_URL}/customers/{customer_id}")

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
        return await self._get(f"{ATERA_BASE_URL}/agents/{agent_id}")

    # -------------------------------------------------------
    # ALERTS
    # -------------------------------------------------------
    async def list_alerts(self) -> list[dict[str, Any]]:
        """Lista todos os alertas ativos do Atera."""
        return await self._paginate("/alerts", "items")

    async def dismiss_alert(self, alert_id: int, approved_by: str) -> dict[str, Any]:
        """[HITL] Remove/fecha um alerta do Atera."""
        logger.info(f"[HITL] Dismissing Atera alert={alert_id} by={approved_by}")
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.delete(
                f"{ATERA_BASE_URL}/alerts/{alert_id}", headers=self._headers()
            )
            r.raise_for_status()
        return {"status": "dismissed", "alert_id": alert_id, "approved_by": approved_by}

    # -------------------------------------------------------
    # TICKETS
    # -------------------------------------------------------
    async def list_tickets(self) -> list[dict[str, Any]]:
        """Lista todos os tickets do Atera."""
        return await self._paginate("/tickets", "items")

    async def create_ticket(
        self, title: str, customer_id: int, description: str = "", priority: str = "Low"
    ) -> dict[str, Any]:
        """Cria um ticket no Atera (ex: disparado por alerta do Zabbix)."""
        payload = {
            "TicketTitle": title,
            "TicketPriority": priority,
            "TicketType": "Incident",
            "CustomerID": customer_id,
            "TicketNotes": description,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{ATERA_BASE_URL}/tickets", headers=self._headers(), json=payload
            )
            r.raise_for_status()
        return r.json()

    # -------------------------------------------------------
    # SUMMARY EFICIENTE para o Dashboard n.infraops
    # Usa apenas a 1ª página de cada recurso para obter totais
    # sem paginar 1.637+ agentes completos.
    # -------------------------------------------------------
    async def get_dashboard_summary(self) -> dict[str, Any]:
        """
        Resumo consolidado para o painel.
        Faz apenas 3 requests (1 por recurso, página 1 com 1 item)
        e usa o campo 'totalItemCount' da resposta para o total real.
        """
        t0 = time.monotonic()
        try:
            # Buscar apenas 1 item por recurso — a API retorna totalItemCount no corpo
            customers_r, agents_r, alerts_r = await asyncio.gather(
                self._get_page_one("/customers", page_size=1),
                self._get_page_one("/agents", page_size=1),
                self._get_page_one("/alerts", page_size=1),
            )

            total_customers = customers_r.get(
                "totalItemCount", len(customers_r.get("items", []))
            )
            total_agents = agents_r.get(
                "totalItemCount", len(agents_r.get("items", []))
            )
            total_alerts = alerts_r.get(
                "totalItemCount", len(alerts_r.get("items", []))
            )

            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return {
                "source": "atera",
                "customers_total": total_customers,
                "agents_total": total_agents,
                "alerts_total": total_alerts,
                "response_time_ms": elapsed_ms,
            }
        except Exception as e:
            logger.error(f"Atera summary error: {e}")
            return {"source": "atera", "error": str(e), "degraded": True}
