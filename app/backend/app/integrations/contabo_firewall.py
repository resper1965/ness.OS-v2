"""
n.infraops — Contabo API Integration
Firewall + Instance Management
Auth: OAuth2 Bearer Token (4 credentials required)

CRITICAL API NOTES:
- x-request-id UUID v4 é OBRIGATÓRIO em cada request
- Firewall rules: usa PUT /firewalls/{id} com campo 'rules.inbound'
- `destPorts` é uma string JSON contendo portas/faixas
- NÃO existe endpoint PUT /rules
- status='inactive' = firewall associado mas NÃO aplicado (ativar via painel)
- Instances já vêm pré-associadas no objeto do firewall
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CONTABO_AUTH_URL = (
    "https://auth.contabo.com/auth/realms/contabo/protocol/openid-connect/token"
)
CONTABO_API_URL = "https://api.contabo.com/v1"


class ContaboTokenManager:
    """Gerencia o ciclo de vida do token OAuth2 da Contabo."""

    def __init__(
        self, client_id: str, client_secret: str, username: str, password: str
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
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
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "username": self.username,
                    "password": self.password,
                    "grant_type": "password",
                },
            )
            response.raise_for_status()
            data = response.json()
            self._token = data["access_token"]
            self._expires_at = datetime.utcnow() + timedelta(
                seconds=data.get("expires_in", 3600) - 60
            )
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
            "Content-Type": "application/json",
            "x-request-id": str(uuid.uuid4()),  # OBRIGATÓRIO
        }

    async def list_firewalls(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{CONTABO_API_URL}/firewalls", headers=await self._headers()
            )
            r.raise_for_status()
            return r.json().get("data", [])

    async def get_firewall(self, firewall_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{CONTABO_API_URL}/firewalls/{firewall_id}",
                headers=await self._headers(),
            )
            r.raise_for_status()
            data = r.json().get("data", [{}])
            return data[0] if data else {}

    async def set_firewall_rules(
        self, firewall_id: str, rules: list[dict], approved_by: str
    ) -> dict[str, Any]:
        """
        [HITL] Substitui TODAS as regras do firewall.
        O payload substitui integralmente `rules.inbound`.
        """
        if not approved_by.strip():
            raise ValueError("approved_by é obrigatório para alterar firewall")
        logger.warning(
            f"[HITL] Replacing ALL firewall rules. fw={firewall_id} rules={len(rules)} by={approved_by}"
        )
        async with httpx.AsyncClient() as client:
            r = await client.put(
                f"{CONTABO_API_URL}/firewalls/{firewall_id}",
                headers=await self._headers(),
                json={"rules": {"inbound": rules}},
            )
            r.raise_for_status()
            return r.json()

    async def ensure_standard_rules(
        self, firewall_id: str, approved_by: str
    ) -> dict[str, Any]:
        """[HITL] Garante as regras padrão: SSH(22), HTTP(80), HTTPS(443)."""
        standard = [
            {
                "displayName": "SSH",
                "protocol": "tcp",
                "destPorts": '["22"]',
                "srcCidr": {"ipv4": ["AnyIPv4"], "ipv6": []},
                "action": "accept",
                "status": "active",
            },
            {
                "displayName": "HTTP",
                "protocol": "tcp",
                "destPorts": '["80"]',
                "srcCidr": {"ipv4": ["AnyIPv4"], "ipv6": []},
                "action": "accept",
                "status": "active",
            },
            {
                "displayName": "HTTPS",
                "protocol": "tcp",
                "destPorts": '["443"]',
                "srcCidr": {"ipv4": ["AnyIPv4"], "ipv6": []},
                "action": "accept",
                "status": "active",
            },
        ]
        return await self.set_firewall_rules(firewall_id, standard, approved_by)

    async def block_ip(
        self, firewall_id: str, ip_cidr: str, approved_by: str
    ) -> dict[str, Any]:
        """Recusa bloqueio direto: a API aceita regras de permissão, não `drop`."""
        raise NotImplementedError(
            "Bloqueio de IP não é suportado por este cliente; use uma política allowlist revisada."
        )

    async def open_port_temporarily(
        self, firewall_id: str, port: int, source_ip: str, approved_by: str
    ) -> dict[str, Any]:
        """
        Abre uma porta para um IP específico (ex: janela de manutenção).
        HITL: approved_by deve conter o ID do usuário que autorizou a ação.
        """
        logger.info(
            f"[HITL] Opening port {port} for {source_ip}. Approved by: {approved_by}"
        )
        current = await self.get_firewall(firewall_id)
        existing_rules = current.get("rules", {}).get("inbound", [])

        allow_rule = {
            "protocol": "tcp",
            "action": "accept",
            "destPorts": json.dumps([str(port)]),
            "srcCidr": {"ipv4": [source_ip], "ipv6": []},
            "status": "active",
            "displayName": f"Temporary TCP {port}",
        }
        updated_rules = existing_rules + [allow_rule]
        return await self.set_firewall_rules(firewall_id, updated_rules, approved_by)

    async def assign_firewall_to_instance(
        self, firewall_id: str, instance_id: str, approved_by: str
    ) -> dict[str, Any]:
        """Associa um perfil de firewall a uma instância de VPS."""
        logger.info(
            f"[HITL] Assigning firewall {firewall_id} to instance {instance_id}. Approved by: {approved_by}"
        )
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
            "x-request-id": str(uuid.uuid4()),
        }

    async def list_instances(self) -> list[dict[str, Any]]:
        """Lista todas as instâncias de VPS/VDS da conta."""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{CONTABO_API_URL}/compute/instances", headers=await self._headers()
            )
            r.raise_for_status()
            return r.json().get("data", [])

    async def get_instance(self, instance_id: str) -> dict[str, Any]:
        """Retorna detalhes de uma instância específica."""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{CONTABO_API_URL}/compute/instances/{instance_id}",
                headers=await self._headers(),
            )
            r.raise_for_status()
            return r.json().get("data", [{}])[0]

    async def restart_instance(
        self, instance_id: str, approved_by: str
    ) -> dict[str, Any]:
        """
        Reinicia uma instância de VPS.
        HITL: approved_by deve conter o ID do usuário que autorizou a ação.
        """
        logger.warning(
            f"[HITL] Restarting instance {instance_id}. Approved by: {approved_by}"
        )
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{CONTABO_API_URL}/compute/instances/{instance_id}/actions/restart",
                headers=await self._headers(),
            )
            r.raise_for_status()
            return r.json()

    async def stop_instance(self, instance_id: str, approved_by: str) -> dict[str, Any]:
        """Desliga uma instância. HITL obrigatório."""
        logger.warning(
            f"[HITL] Stopping instance {instance_id}. Approved by: {approved_by}"
        )
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{CONTABO_API_URL}/compute/instances/{instance_id}/actions/stop",
                headers=await self._headers(),
            )
            r.raise_for_status()
            return r.json()

    async def create_snapshot(
        self, instance_id: str, name: str, description: str = ""
    ) -> dict[str, Any]:
        """Cria um snapshot de uma instância (útil antes de remediações automáticas)."""
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{CONTABO_API_URL}/compute/instances/{instance_id}/snapshots",
                headers=await self._headers(),
                json={"name": name, "description": description},
            )
            r.raise_for_status()
            return r.json()
