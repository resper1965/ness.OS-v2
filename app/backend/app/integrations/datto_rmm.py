"""
n.infraops — Datto RMM API v2 Integration
Auth: OAuth2 Client Credentials (token expira em 4h)
Rate Limit: 600 req/min por API key
Pagination: page + pageSize (max 250 por pagina)

IMPORTANTE: Identificar a plataforma pelo subdominio do portal:
  Ex: se acessar merlot.centrastage.net → DATTO_PLATFORM=merlot
Plataformas: pinotage, merlot, concord, vidal, zinfandel, syrah
"""

import base64
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class DattoRMMClient:
    def __init__(self, platform: str, api_key: str, api_secret: str):
        """
        Args:
            platform: subdomínio da plataforma (ex: 'merlot', 'pinotage')
            api_key:  chave pública gerada em Setup → Users → Generate API Keys
            api_secret: chave privada (exibida apenas uma vez na geração)
        """
        self.platform = platform
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = f"https://{platform}-api.centrastage.net/api"
        self.token_url = f"https://{platform}-api.centrastage.net/auth/oauth/token"
        self._token: str | None = None
        self._expires_at: datetime = datetime.min

    async def _get_token(self) -> str:
        if self._token and datetime.utcnow() < self._expires_at:
            return self._token
        credentials = base64.b64encode(
            f"{self.api_key}:{self.api_secret}".encode()
        ).decode()
        async with httpx.AsyncClient() as client:
            r = await client.post(
                self.token_url,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )
            r.raise_for_status()
            data = r.json()
            self._token = data["access_token"]
            # Token expira em ~4h (14399s), renovamos com 5min de margem
            self._expires_at = datetime.utcnow() + timedelta(
                seconds=data.get("expires_in", 14399) - 300
            )
            logger.info(f"Datto RMM token refreshed. Platform: {self.platform}")
            return self._token

    async def _headers(self) -> dict:
        token = await self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def _paginate(self, endpoint: str, data_key: str) -> list[dict[str, Any]]:
        """Busca todas as páginas (pageDetails.nextPageUrl)."""
        results = []
        url = f"{self.base_url}{endpoint}"
        params: dict = {"pageSize": 250}

        while url:
            async with httpx.AsyncClient() as client:
                r = await client.get(url, headers=await self._headers(), params=params)
                r.raise_for_status()
                body = r.json()
            results.extend(body.get(data_key, []))
            url = body.get("pageDetails", {}).get("nextPageUrl")
            params = {}  # URL seguinte já tem params embutidos
        return results

    # -------------------------------------------------------
    # SITES (Clientes / Tenants)
    # -------------------------------------------------------
    async def list_sites(self) -> list[dict[str, Any]]:
        """Lista todos os sites (clientes) da conta Datto RMM."""
        return await self._paginate("/v2/account/sites", "sites")

    async def get_site(self, site_uid: str) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}/v2/site/{site_uid}", headers=await self._headers()
            )
            r.raise_for_status()
            return r.json()

    # -------------------------------------------------------
    # DEVICES (Endpoints)
    # -------------------------------------------------------
    async def list_all_devices(self) -> list[dict[str, Any]]:
        """Lista TODOS os dispositivos de todos os sites."""
        return await self._paginate("/v2/account/devices", "devices")

    async def list_devices_by_site(self, site_uid: str) -> list[dict[str, Any]]:
        """Lista dispositivos de um site específico."""
        return await self._paginate(f"/v2/site/{site_uid}/devices", "devices")

    async def get_device(self, device_uid: str) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}/v2/device/{device_uid}", headers=await self._headers()
            )
            r.raise_for_status()
            return r.json()

    # -------------------------------------------------------
    # ALERTS
    # -------------------------------------------------------
    async def list_open_alerts(self) -> list[dict[str, Any]]:
        """Lista todos os alertas abertos de toda a conta."""
        return await self._paginate("/v2/account/alerts/open", "alerts")

    async def list_open_alerts_by_site(self, site_uid: str) -> list[dict[str, Any]]:
        """Lista alertas abertos de um site específico."""
        return await self._paginate(f"/v2/site/{site_uid}/alerts/open", "alerts")

    async def resolve_alert(self, alert_uid: str, approved_by: str) -> dict[str, Any]:
        """[HITL] Resolve um alerta do Datto RMM."""
        logger.info(f"[HITL] Resolving Datto alert={alert_uid} by={approved_by}")
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.base_url}/v2/alert/{alert_uid}/resolve",
                headers=await self._headers(),
                json={},
            )
            r.raise_for_status()
            return {
                "status": "resolved",
                "alert_uid": alert_uid,
                "approved_by": approved_by,
            }

    # -------------------------------------------------------
    # SUMMARY para o Dashboard n.infraops
    # -------------------------------------------------------
    async def get_dashboard_summary(self) -> dict[str, Any]:
        """Retorna resumo consolidado para o painel."""
        try:
            sites = await self.list_sites()
            devices = await self.list_all_devices()
            alerts = await self.list_open_alerts()
            online = sum(1 for d in devices if d.get("online") is True)
            return {
                "source": "datto_rmm",
                "platform": self.platform,
                "total_sites": len(sites),
                "total_devices": len(devices),
                "devices_online": online,
                "devices_offline": len(devices) - online,
                "open_alerts": len(alerts),
            }
        except Exception as e:
            logger.error(f"Datto RMM summary error: {e}")
            return {"source": "datto_rmm", "error": str(e)}
