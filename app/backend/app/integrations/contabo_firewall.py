"""
n.infraops — Contabo API Integration
Firewall + Instance Management
Auth: OAuth2 Bearer Token (4 credentials required)

CRITICAL API NOTES (from official docs):
- x-request-id UUID v4 is MANDATORY on every request
- Firewall rules: PUT /rules does FULL REPLACEMENT (send complete ruleset)
- Firewall only supports 'accept' action (deny-by-omission strategy)
- Field names: ipRange (not sourceIp), port (not destinationPort)
- Instance assignment: instanceId in request BODY (not URL)
"""
import httpx
import uuid
import logging
from typing import Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

CONTABO_AUTH_URL = "https://auth.contabo.com/auth/realms/contabo/protocol/openid-connect/token"
CONTABO_API_URL  = "https://api.contabo.com/v1"


class ContaboTokenManager:
    """Gerencia o ciclo de vida do token OAuth2 da Contabo."""

    def __init__(self, client_id: str, client_secret: str, username: str, password: str):
        self.client_id     = client_id
        self.client_secret = client_secret
        self.username      = username
        self.password      = password
        self._token: str | None = None
        self._expires_at: datetime = datetime.min

    async def get_token(self) -> str:
        if self._token and datetime.utcnow() < self._expires_at:
            return self._token
        return await self._refresh_token()

    async def _refresh_token(self) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                CONTABO_AUTH_URL,
                data={
                    "client_id":     self.client_id,
                    "client_secret": self.client_secret,
                    "username":      self.username,
                    "password":      self.password,
                    "grant_type":    "password",
                },
            )
            response.raise_for_status()
            data = response.json()
            self._token = data["access_token"]
            self._expires_at = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600) - 60)
            logger.info("Contabo OAuth2 token refreshed.")
            return self._token


class ContaboFirewallClient:
    """
    Cliente para o Firewall da Contabo.

    REGRA DE OURO: PUT /rules faz SUBSTITUIÇÃO TOTAL.
    Sempre enviar o conjunto COMPLETO de regras desejadas.
    A Contabo só suporta 'accept' — bloqueio é feito por omissão.
    """

    def __init__(self, token_manager: ContaboTokenManager):
        self.token_manager = token_manager

    async def _headers(self) -> dict:
        token = await self.token_manager.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "x-request-id":  str(uuid.uuid4()),  # OBRIGATÓRIO
        }

    async def list_firewalls(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{CONTABO_API_URL}/firewalls", headers=await self._headers())
            r.raise_for_status()
            return r.json().get("data", [])

    async def get_firewall(self, firewall_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{CONTABO_API_URL}/firewalls/{firewall_id}", headers=await self._headers())
            r.raise_for_status()
            data = r.json().get("data", [{}])
            return data[0] if data else {}

    async def set_firewall_rules(self, firewall_id: str, rules: list[dict], approved_by: str) -> dict[str, Any]:
        """
        [HITL] Substitui TODAS as regras do firewall.
        Formato de regra: {"name": "SSH", "protocol": "TCP", "port": "22", "action": "accept", "ipRange": "0.0.0.0/0"}
        """
        logger.warning(f"[HITL] Replacing ALL firewall rules. fw={firewall_id} rules={len(rules)} by={approved_by}")
        async with httpx.AsyncClient() as client:
            r = await client.put(
                f"{CONTABO_API_URL}/firewalls/{firewall_id}/rules",
                headers=await self._headers(),
                json={"inboundRules": rules},
            )
            r.raise_for_status()
            return r.json()

    async def ensure_standard_rules(self, firewall_id: str, approved_by: str) -> dict[str, Any]:
        """[HITL] Garante as regras padrão: SSH(22), HTTP(80), HTTPS(443)."""
        standard = [
            {"name": "SSH",   "protocol": "TCP", "port": "22",  "action": "accept", "ipRange": "0.0.0.0/0"},
            {"name": "HTTP",  "protocol": "TCP", "port": "80",  "action": "accept", "ipRange": "0.0.0.0/0"},
            {"name": "HTTPS", "protocol": "TCP", "port": "443", "action": "accept", "ipRange": "0.0.0.0/0"},
        ]
        return await self.set_firewall_rules(firewall_id, standard, approved_by)

    async def block_ip(self, firewall_id: str, ip_cidr: str, approved_by: str) -> dict[str, Any]:
        """
        block_rule = {
            "protocol": "tcp",
            "action": "drop",
            "sourceIp": ip_cidr,
            "destinationPort": "1-65535",
        }
        updated_rules = existing_rules + [block_rule]

        async with httpx.AsyncClient() as client:
            r = await client.put(
                f"{CONTABO_API_URL}/firewalls/{firewall_id}",
                headers=await self._headers(),
                json={"inboundRules": updated_rules},
            )
            r.raise_for_status()
            return r.json()

    async def open_port_temporarily(
        self, firewall_id: str, port: int, source_ip: str, approved_by: str
    ) -> dict[str, Any]:
        """
        Abre uma porta para um IP específico (ex: janela de manutenção).
        HITL: approved_by deve conter o ID do usuário que autorizou a ação.
        """
        logger.info(f"[HITL] Opening port {port} for {source_ip}. Approved by: {approved_by}")
        current = await self.get_firewall(firewall_id)
        existing_rules = current.get("inboundRules", [])

        allow_rule = {
            "protocol": "tcp",
            "action": "accept",
            "sourceIp": source_ip,
            "destinationPort": str(port),
        }
        updated_rules = existing_rules + [allow_rule]

        async with httpx.AsyncClient() as client:
            r = await client.put(
                f"{CONTABO_API_URL}/firewalls/{firewall_id}",
                headers=await self._headers(),
                json={"inboundRules": updated_rules},
            )
            r.raise_for_status()
            return r.json()

    async def assign_firewall_to_instance(self, firewall_id: str, instance_id: str, approved_by: str) -> dict[str, Any]:
        """Associa um perfil de firewall a uma instância de VPS."""
        logger.info(f"[HITL] Assigning firewall {firewall_id} to instance {instance_id}. Approved by: {approved_by}")
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{CONTABO_API_URL}/firewalls/{firewall_id}/instances/{instance_id}",
                headers=await self._headers(),
            )
            r.raise_for_status()
            return r.json()


class ContaboInstanceClient:
    """
    Cliente para Instâncias de Computação da Contabo.
    Capacidades: Listing, status check, start/stop/restart.
    """

    def __init__(self, token_manager: ContaboTokenManager):
        self.token_manager = token_manager

    async def _headers(self) -> dict:
        token = await self.token_manager.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def list_instances(self) -> list[dict[str, Any]]:
        """Lista todas as instâncias de VPS/VDS da conta."""
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{CONTABO_API_URL}/compute/instances", headers=await self._headers())
            r.raise_for_status()
            return r.json().get("data", [])

    async def get_instance(self, instance_id: str) -> dict[str, Any]:
        """Retorna detalhes de uma instância específica."""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{CONTABO_API_URL}/compute/instances/{instance_id}", headers=await self._headers()
            )
            r.raise_for_status()
            return r.json().get("data", [{}])[0]

    async def restart_instance(self, instance_id: str, approved_by: str) -> dict[str, Any]:
        """
        Reinicia uma instância de VPS.
        HITL: approved_by deve conter o ID do usuário que autorizou a ação.
        """
        logger.warning(f"[HITL] Restarting instance {instance_id}. Approved by: {approved_by}")
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{CONTABO_API_URL}/compute/instances/{instance_id}/actions/restart",
                headers=await self._headers(),
            )
            r.raise_for_status()
            return r.json()

    async def stop_instance(self, instance_id: str, approved_by: str) -> dict[str, Any]:
        """Desliga uma instância. HITL obrigatório."""
        logger.warning(f"[HITL] Stopping instance {instance_id}. Approved by: {approved_by}")
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{CONTABO_API_URL}/compute/instances/{instance_id}/actions/stop",
                headers=await self._headers(),
            )
            r.raise_for_status()
            return r.json()

    async def create_snapshot(self, instance_id: str, name: str, description: str = "") -> dict[str, Any]:
        """Cria um snapshot de uma instância (útil antes de remediações automáticas)."""
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{CONTABO_API_URL}/compute/instances/{instance_id}/snapshots",
                headers=await self._headers(),
                json={"name": name, "description": description},
            )
            r.raise_for_status()
            return r.json()
