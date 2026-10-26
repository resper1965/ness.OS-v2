# -------------------------------------------------------
# n.infraops — Cliente API Zabbix (JSON-RPC)
# -------------------------------------------------------
import logging
import time
from typing import Any
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ZabbixClient:
    """Cliente JSON-RPC assíncrono para a API do Zabbix 7.0 LTS."""

    def __init__(self, url: str | None = None, token: str | None = None):
        self.url = url or settings.zabbix_url
        self.token = token or settings.zabbix_api_token
        self.timeout = httpx.Timeout(10.0, read=30.0)

    async def _call(self, method: str, params: dict[str, Any] | list[str]) -> Any:
        """Executa uma chamada JSON-RPC para a API do Zabbix."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }

        # Zabbix 7.0 suporta autenticação via Bearer token no payload ou header
        if self.token:
            payload["auth"] = self.token

        headers = {"Content-Type": "application/json-rpc"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.url, json=payload, headers=headers)
                response.raise_for_status()
                res_data = response.json()
                if "error" in res_data:
                    logger.error(
                        "Erro na API Zabbix [%s]: %s", method, res_data["error"]
                    )
                    raise ValueError(
                        f"Zabbix API Error: {res_data['error'].get('data', '') or res_data['error'].get('message', '')}"
                    )
                return res_data.get("result")
            except Exception as e:
                logger.error("Falha ao comunicar com API Zabbix [%s]: %s", method, e)
                raise

    async def get_active_problems(self, severity_min: int = 4) -> list[dict[str, Any]]:
        """Recupera problemas ativos no Zabbix filtrados por severidade mínima.

        Zabbix severities:
          0 - Not classified, 1 - Info, 2 - Warning, 3 - Average, 4 - High, 5 - Disaster
        """
        params = {
            "output": ["eventid", "name", "severity", "clock", "r_clock", "userid"],
            "selectAcknowledges": "extend",
            "selectTags": "extend",
            "recent": True,
            "sortfield": ["eventid"],
            "sortorder": "DESC",
        }
        if severity_min > 0:
            params["severities"] = [i for i in range(severity_min, 6)]

        return await self._call("problem.get", params)

    async def get_history(
        self, item_ids: list[str], limit: int = 100, history_type: int = 0
    ) -> list[dict[str, Any]]:
        """Recupera histórico bruto de valores de um item.

        history_type: 0 (float), 1 (char), 2 (log), 3 (int), 4 (text)
        """
        params = {
            "output": "extend",
            "itemids": item_ids,
            "history": history_type,
            "sortfield": "clock",
            "sortorder": "DESC",
            "limit": limit,
        }
        return await self._call("history.get", params)

    async def get_trends(
        self, item_ids: list[str], limit: int = 1000
    ) -> list[dict[str, Any]]:
        """Recupera dados agregados (trends) para capacity planning."""
        params = {
            "output": "extend",
            "itemids": item_ids,
            "sortfield": "clock",
            "sortorder": "DESC",
            "limit": limit,
        }
        return await self._call("trend.get", params)

    async def acknowledge_problem(
        self, event_id: str, message: str, action: int = 6
    ) -> Any:
        """Acknowledge e opcionalmente fecha um problema.

        action bitmask:
          1 - close problem
          2 - acknowledge event
          4 - add message
          8 - change severity
        Default action=6 (acknowledge + add message)
        """
        params = {"eventids": event_id, "action": action, "message": message}
        return await self._call("event.acknowledge", params)

    async def execute_script(self, script_id: str, host_id: str) -> dict[str, Any]:
        """Executa um script do Zabbix (comando remoto no Agent/Server)."""
        params = {"scriptid": script_id, "hostid": host_id}
        return await self._call("script.execute", params)

    async def create_maintenance(
        self, host_ids: list[str], duration_seconds: int = 3600, name: str | None = None
    ) -> str:
        """Cria uma janela de manutenção silenciosa no Zabbix."""
        now = int(time.time())
        m_name = name or f"n.infraops Auto Maintenance {now}"

        params = {
            "name": m_name,
            "active_since": now,
            "active_till": now + duration_seconds,
            "hostids": host_ids,
            "timeperiods": [
                {
                    "timeperiod_type": 0,  # One-time period
                    "start_date": now,
                    "period": duration_seconds,
                }
            ],
        }
        res = await self._call("maintenance.create", params)
        # Retorna o ID da manutenção criada
        return res.get("maintenanceids", [""])[0]

    async def delete_maintenance(self, maintenance_id: str) -> None:
        """Remove uma janela de manutenção silenciosa."""
        await self._call("maintenance.delete", [maintenance_id])
