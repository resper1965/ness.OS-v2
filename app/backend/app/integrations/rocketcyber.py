"""
n.infraops — RocketCyber SOC API Integration
Base URLs:
  Customer API: https://api-us.rocketcyber.com
  Console API:  https://console-api.us.rocketcyber.com
Auth: Bearer <CONSOLE_API_KEY>  (obtida em app.rocketcyber.com → Setup → API)

Account IDs mapeados da collection:
  147586 → cliente principal
  166960 → cliente (incidente 9292088)
  167442 → cliente recente
  137707 → cliente com MTTP calculado
  124091 → cliente com apps
  201912 → cliente adicional

Capacidades:
  - Listar todos os sub-accounts (clientes MSP)
  - Listar agentes instalados por cliente
  - Listar eventos de segurança (telemetria bruta)
  - Listar incidentes abertos/fechados (ameaças detectadas)
  - Filtrar por accountId, status, data, severidade
"""
import httpx
import logging
from typing import Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

ROCKETCYBER_BASE = "https://api-us.rocketcyber.com"


class RocketCyberClient:
    def __init__(self, api_key: str):
        """
        Args:
            api_key: CONSOLE_API_KEY obtida em app.rocketcyber.com → Setup → API
        """
        self.api_key = api_key

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # -------------------------------------------------------
    # ACCOUNT (MSP raiz + sub-contas dos clientes)
    # -------------------------------------------------------
    async def get_account(self) -> dict[str, Any]:
        """Retorna dados da conta MSP raiz e todas as sub-contas."""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{ROCKETCYBER_BASE}/v3/account",
                headers=self._headers(),
                params={"details": "true"},
            )
            r.raise_for_status()
            return r.json()

    # -------------------------------------------------------
    # AGENTS (endpoints com agente RocketCyber instalado)
    # -------------------------------------------------------
    async def list_agents(self, account_id: int) -> list[dict[str, Any]]:
        """Lista agentes instalados para um account (cliente)."""
        results = []
        page = 1
        while True:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{ROCKETCYBER_BASE}/v2/account/{account_id}/agents",
                    headers=self._headers(),
                    params={"page": page, "pageSize": 100},
                )
                r.raise_for_status()
                data = r.json()
            items = data.get("data", data.get("agents", []))
            results.extend(items)
            if not data.get("nextPage") and not data.get("hasNextPage"):
                break
            page += 1
        return results

    # -------------------------------------------------------
    # EVENTS (telemetria de segurança bruta)
    # -------------------------------------------------------
    async def list_events(
        self,
        account_id: int,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Lista eventos de segurança brutos de um cliente.
        Args:
            account_id: ID do cliente
            start_date: '2026-07-01' (padrão: últimos 7 dias)
            end_date:   '2026-07-04'
        """
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.utcnow().strftime("%Y-%m-%d")

        results = []
        page = 1
        while True:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{ROCKETCYBER_BASE}/v2/account/{account_id}/events",
                    headers=self._headers(),
                    params={"startDate": start_date, "endDate": end_date, "page": page, "pageSize": 100},
                )
                r.raise_for_status()
                data = r.json()
            items = data.get("data", data.get("events", []))
            results.extend(items)
            if not data.get("nextPage"):
                break
            page += 1
        return results

    # -------------------------------------------------------
    # INCIDENTS (ameaças detectadas — principal para o dashboard)
    # -------------------------------------------------------
    async def list_open_incidents(
        self,
        account_id: int | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Lista incidentes de segurança ABERTOS.
        Se account_id=None, retorna todos os incidentes MSP.
        """
        params: dict = {
            "page": 1,
            "pageSize": min(limit, 100),
            "status": "open",
            "sort": "createdAt:desc",
        }
        if account_id:
            params["accountId"] = account_id

        results = []
        while True:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{ROCKETCYBER_BASE}/v3/incidents",
                    headers=self._headers(),
                    params=params,
                )
                r.raise_for_status()
                data = r.json()
            items = data.get("data", data.get("incidents", []))
            results.extend(items)
            total = data.get("totalCount", data.get("total", 0))
            if len(results) >= total or len(results) >= limit or not items:
                break
            params["page"] = params.get("page", 1) + 1
        return results[:limit]

    async def list_incidents_by_date(
        self,
        account_id: int,
        since: str,
        until: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Lista incidentes em um intervalo de datas.
        Args:
            since: '2026-07-01T00:00:00Z'
            until: '2026-07-04T23:59:59Z' (padrão: agora)
        """
        if not until:
            until = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        date_range = f"{since}|{until}"

        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{ROCKETCYBER_BASE}/v3/incidents",
                headers=self._headers(),
                params={
                    "accountId": account_id,
                    "createdAt": date_range,
                    "page": 1,
                    "pageSize": 100,
                    "sort": "createdAt:desc",
                },
            )
            r.raise_for_status()
            data = r.json()
        return data.get("data", data.get("incidents", []))

    async def get_incident(self, incident_id: int, account_id: int) -> dict[str, Any]:
        """Busca um incidente específico pelo ID."""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{ROCKETCYBER_BASE}/v3/incidents",
                headers=self._headers(),
                params={"id": incident_id, "accountId": account_id},
            )
            r.raise_for_status()
            data = r.json()
        items = data.get("data", [])
        return items[0] if items else {}

    # -------------------------------------------------------
    # APPS (módulos de segurança ativos por cliente)
    # -------------------------------------------------------
    async def list_apps(self, account_id: int) -> list[dict[str, Any]]:
        """Lista apps/módulos de segurança habilitados para um cliente."""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{ROCKETCYBER_BASE}/v2/account/{account_id}/apps",
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()

    # -------------------------------------------------------
    # MTTP (Mean Time to Patch) — cálculo via n8n no ambiente atual
    # -------------------------------------------------------
    async def get_mttp(self, account_id: int) -> dict[str, Any]:
        """
        Calcula MTTP (Mean Time to Patch) para um cliente.
        Nota: No ambiente atual isso é feito via webhook n8n.
        Endpoint: /webhook/secops_getMTTR?accountId={id}
        """
        # Placeholder — implementar quando n8n estiver integrado ao Keep
        return {"account_id": account_id, "mttp_days": None, "note": "pending_n8n_integration"}

    # -------------------------------------------------------
    # DASHBOARD SUMMARY para o hub n.infraops
    # -------------------------------------------------------
    async def get_dashboard_summary(self, account_ids: list[int] | None = None) -> dict[str, Any]:
        """
        Retorna resumo consolidado de incidentes para o painel.
        Se account_ids=None, busca todos os incidentes MSP.
        """
        try:
            all_incidents = await self.list_open_incidents(limit=200)
            critical = [i for i in all_incidents if i.get("severity", "").lower() in ("critical", "high")]
            by_account: dict[int, int] = {}
            for inc in all_incidents:
                acc = inc.get("accountId")
                if acc:
                    by_account[acc] = by_account.get(acc, 0) + 1
            return {
                "source": "rocketcyber",
                "open_incidents": len(all_incidents),
                "critical_incidents": len(critical),
                "accounts_with_incidents": len(by_account),
                "top_accounts": sorted(by_account.items(), key=lambda x: x[1], reverse=True)[:5],
            }
        except Exception as e:
            logger.error(f"RocketCyber summary error: {e}")
            return {"source": "rocketcyber", "error": str(e)}
