# -------------------------------------------------------
# n.infraops — Cliente API Zabbix (JSON-RPC)
# -------------------------------------------------------
import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def is_zabbix_api_url(url: str) -> bool:
    """Accept only an explicit HTTP(S) Zabbix JSON-RPC endpoint."""
    parsed = urlparse(url)
    return bool(
        parsed.scheme in {"http", "https"}
        and parsed.hostname
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
        and parsed.path.rstrip("/").endswith("/api_jsonrpc.php")
    )


class ZabbixClient:
    """Cliente JSON-RPC assíncrono para a API do Zabbix 7.0 LTS."""

    def __init__(self, url: str | None = None, token: str | None = None):
        self.url = (settings.zabbix_url if url is None else url).rstrip("/")
        self.token = settings.zabbix_api_token if token is None else token
        self.timeout = httpx.Timeout(10.0, read=30.0)
        self.verify_ssl = settings.zabbix_verify_cert

    async def _call(self, method: str, params: dict[str, Any] | list[str]) -> Any:
        """Executa uma chamada JSON-RPC para a API do Zabbix."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }

        # Zabbix 7.0+: API tokens (criados na UI) devem usar Bearer header.
        # O campo "auth" no payload era para session tokens (user.login) — deprecado em 7.0.
        headers = {"Content-Type": "application/json-rpc"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient(
            timeout=self.timeout, verify=self.verify_ssl, follow_redirects=False
        ) as client:
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

    async def _readiness_call(
        self,
        client: httpx.AsyncClient,
        method: str,
        params: dict[str, Any],
        request_id: int,
        *,
        authenticated: bool,
    ) -> Any:
        headers = {"Content-Type": "application/json-rpc"}
        if authenticated:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            response = await client.post(
                self.url,
                json={
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                    "id": request_id,
                },
                headers=headers,
            )
        except httpx.HTTPError:
            raise RuntimeError("Probe falhou: API Zabbix inacessível") from None

        if response.is_redirect:
            raise RuntimeError("Probe falhou: redirecionamento recusado")

        content_type = response.headers.get("content-type", "").lower()
        if "text/html" in content_type:
            raise RuntimeError(
                "Probe falhou: frontend acessível, API JSON-RPC indisponível"
            )

        if authenticated and response.status_code in {401, 403}:
            raise RuntimeError("Probe falhou: token Zabbix não autorizado")
        if response.status_code != 200:
            raise RuntimeError("Probe falhou: status HTTP inesperado da API Zabbix")

        try:
            data = response.json()
        except ValueError:
            raise RuntimeError("Probe falhou: resposta JSON-RPC inválida") from None

        if not isinstance(data, dict):
            raise RuntimeError("Probe falhou: resposta JSON-RPC inválida")

        error = data.get("error")
        if isinstance(error, dict):
            error_text = " ".join(
                str(error.get(field, "")) for field in ("message", "data")
            ).lower()
            if authenticated and (
                "not authorized" in error_text
                or "not authorised" in error_text
                or "unauthorized" in error_text
            ):
                raise RuntimeError("Probe falhou: token Zabbix não autorizado")
            raise RuntimeError("Probe falhou: erro JSON-RPC do Zabbix")

        if (
            data.get("jsonrpc") != "2.0"
            or data.get("id") != request_id
            or "result" not in data
        ):
            raise RuntimeError("Probe falhou: resposta JSON-RPC inválida")
        return data["result"]

    async def readiness_probe(self) -> dict[str, Any]:
        """Verify the API route and token using read-only JSON-RPC methods."""
        if not is_zabbix_api_url(self.url):
            raise RuntimeError(
                "Probe recusado: NINF_ZABBIX_URL deve apontar para api_jsonrpc.php"
            )
        if not self.token or not self.token.strip():
            raise RuntimeError("Probe recusado: token Zabbix não configurado")

        async with httpx.AsyncClient(
            timeout=self.timeout,
            verify=self.verify_ssl,
            follow_redirects=False,
        ) as client:
            version = await self._readiness_call(
                client,
                "apiinfo.version",
                {},
                1,
                authenticated=False,
            )
            hosts = await self._readiness_call(
                client,
                "host.get",
                {"output": ["hostid"], "limit": 1},
                2,
                authenticated=True,
            )

        if not isinstance(version, str) or not version:
            raise RuntimeError("Probe falhou: versão Zabbix inválida")
        if not isinstance(hosts, list):
            raise RuntimeError("Probe falhou: resposta autenticada inválida")

        return {
            "status": "ready",
            "mode": "read-only",
            "transport": "json-rpc",
            "version": version,
            "authenticated": True,
            "visible_host_sample_count": len(hosts),
            "write_operations": 0,
        }

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

    async def acknowledge_trigger(self, trigger_id: str, message: str) -> bool:
        """Encontra o problema ativo para a trigger_id e o reconhece/fecha (action=7)."""
        problems = await self._call(
            "problem.get",
            {
                "output": ["eventid"],
                "objectids": [trigger_id],
                "recent": False,
            },
        )

        if not problems:
            logger.info(
                "Nenhum problema ativo encontrado no Zabbix para a trigger_id=%s",
                trigger_id,
            )
            return False

        event_id = problems[0]["eventid"]

        # Action 7 = Close problem (1) + Acknowledge event (2) + Add message (4)
        await self.acknowledge_problem(
            event_id=event_id,
            message=message,
            action=7,
        )
        return True

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
