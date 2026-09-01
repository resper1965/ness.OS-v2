# -------------------------------------------------------
# n.infraops — RMM Factory (resolve driver por ativo)
# -------------------------------------------------------
"""
Factory Pattern que instancia o driver de RMM correto
baseado no cadastro do ativo no banco de dados.

Fluxo:
  1. Recebe zabbix_host_id.
  2. Consulta n_infraops_assets → descobre rmm_provider.
  3. Instancia DattoRMMDriver, AteraRMMDriver ou NetworkDriver.
  4. Retorna driver pronto para execute_playbook().

Multi-tenant: credenciais de API são resolvidas por customer_id,
permitindo que cada cliente tenha suas próprias chaves de RMM.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.remediators.atera import AteraRMMDriver
from app.remediators.base import BaseRMMDriver
from app.remediators.datto import DattoRMMDriver
from app.remediators.network import NetworkDriver

logger = logging.getLogger(__name__)
settings = get_settings()


class RMMFactory:
    """Factory que resolve o driver de RMM correto por ativo.

    Uso:
        driver = RMMFactory.create_driver(asset)
        result = driver.execute_playbook(device_id, "restart_service")
    """

    # Registry de credenciais por customer_id (multi-tenant)
    # Em produção: Vault, SOPS, ou tabela de secrets no banco
    _credential_store: dict[str, dict[str, str]] = {}

    @classmethod
    def register_credentials(
        cls,
        customer_id: str,
        provider: str,
        credentials: dict[str, str],
    ) -> None:
        """Registra credenciais de RMM para um customer.

        Args:
            customer_id: ID do cliente/contrato.
            provider: 'datto' ou 'atera'.
            credentials: Dict com api_key, api_secret, api_url, etc.
        """
        key = f"{customer_id}:{provider}"
        cls._credential_store[key] = credentials
        logger.info(
            "Credenciais registradas | customer=%s provider=%s", customer_id, provider
        )

    @classmethod
    def create_driver(cls, asset: dict[str, Any]) -> BaseRMMDriver:
        """Instancia o driver correto baseado no cadastro do ativo.

        Args:
            asset: Dict com dados do ativo (de n_infraops_assets).
                   Campos obrigatórios: rmm_provider, rmm_device_id.
                   Opcionais: customer_id, hostname, ssh_username, ssh_port.

        Returns:
            Instância concreta de BaseRMMDriver.

        Raises:
            ValueError: Se rmm_provider for desconhecido ou
                        credenciais estiverem faltando.
        """
        provider: str = asset.get("rmm_provider", "none")
        customer_id: str = asset.get("customer_id", "default")

        logger.debug(
            "Resolvendo driver | host=%s provider=%s customer=%s",
            asset.get("hostname"),
            provider,
            customer_id,
        )

        if provider == "datto":
            return cls._create_datto(asset, customer_id)
        elif provider == "atera":
            return cls._create_atera(asset, customer_id)
        elif provider == "none":
            return cls._create_network(asset)
        else:
            raise ValueError(
                f"RMM provider desconhecido: '{provider}' "
                f"para ativo '{asset.get('hostname')}'"
            )

    @classmethod
    def _create_datto(cls, asset: dict[str, Any], customer_id: str) -> DattoRMMDriver:
        """Cria driver Datto com credenciais do customer."""
        creds = cls._get_credentials(customer_id, "datto")
        return DattoRMMDriver(
            api_key=creds.get("api_key", ""),
            api_secret=creds.get("api_secret", ""),
            api_url=creds.get("api_url", "https://pinotage-api.centrastage.net"),
        )

    @classmethod
    def _create_atera(cls, asset: dict[str, Any], customer_id: str) -> AteraRMMDriver:
        """Cria driver Atera com credenciais do customer."""
        creds = cls._get_credentials(customer_id, "atera")
        return AteraRMMDriver(
            api_key=creds.get("api_key", ""),
            api_url=creds.get("api_url", "https://app.atera.com/api/v3"),
        )

    @classmethod
    def _create_network(cls, asset: dict[str, Any]) -> NetworkDriver:
        """Cria driver SSH para network devices."""
        hostname = asset.get("hostname") or asset.get("ip_address")
        username = asset.get("ssh_username")

        if not hostname or not username:
            raise ValueError(
                f"Network device '{asset.get('hostname')}' requer "
                f"hostname/IP e ssh_username no cadastro"
            )

        # Detectar tipo de device pelo os_family
        device_type = _resolve_netmiko_type(asset.get("os_family", ""))

        return NetworkDriver(
            hostname=str(hostname),
            username=username,
            ssh_port=asset.get("ssh_port", 22),
            device_type=device_type,
        )

    @classmethod
    async def _async_get_db_credentials(
        cls, customer_id: str, provider: str
    ) -> dict[str, str]:
        """Busca credenciais no banco de dados utilizando SQLAlchemy Async."""
        from sqlalchemy import select
        from app.database import SessionLocal
        from app.models import CustomerCredentials

        try:
            async with SessionLocal() as session:
                # Primeiro tenta com o customer_id específico
                stmt = select(CustomerCredentials).where(
                    CustomerCredentials.customer_id == customer_id,
                    CustomerCredentials.provider == provider,
                )
                result = await session.execute(stmt)
                db_creds = result.scalar_one_or_none()

                # Se não encontrar, tenta o default
                if not db_creds:
                    stmt = select(CustomerCredentials).where(
                        CustomerCredentials.customer_id == "default",
                        CustomerCredentials.provider == provider,
                    )
                    result = await session.execute(stmt)
                    db_creds = result.scalar_one_or_none()

                if db_creds:
                    return {
                        "api_key": db_creds.api_key,
                        "api_secret": db_creds.api_secret or "",
                        "api_url": db_creds.api_url or "",
                    }
        except Exception as e:
            logger.warning("Falha ao buscar credenciais no banco de dados: %s", e)
        return {}

    @classmethod
    def _get_credentials(cls, customer_id: str, provider: str) -> dict[str, str]:
        """Busca credenciais do registry ou banco. Fallback para 'default'."""
        import asyncio

        # Tenta buscar no banco de dados (async)
        try:
            creds = asyncio.run(cls._async_get_db_credentials(customer_id, provider))
        except Exception as e:
            logger.warning("Erro ao executar busca assíncrona de credenciais: %s", e)
            creds = {}

        # Fallback para o registry em memória (útil para testes/mocks)
        if not creds:
            key = f"{customer_id}:{provider}"
            creds = cls._credential_store.get(key)

        if not creds:
            # Fallback para credenciais globais em memória
            default_key = f"default:{provider}"
            creds = cls._credential_store.get(default_key, {})

        if not creds:
            raise ValueError(
                f"Credenciais não encontradas: customer={customer_id} "
                f"provider={provider}. Registre via RMMFactory.register_credentials()"
            )

        return creds


def _resolve_netmiko_type(os_family: str) -> str:
    """Mapeia os_family do ativo para device_type do Netmiko."""
    os_lower = os_family.lower()
    mapping = {
        "cisco ios": "cisco_ios",
        "cisco nxos": "cisco_nxos",
        "cisco asa": "cisco_asa",
        "junos": "juniper_junos",
        "juniper": "juniper_junos",
        "mikrotik": "mikrotik_routeros",
        "routeros": "mikrotik_routeros",
        "fortinet": "fortinet",
        "fortigate": "fortinet",
        "paloalto": "paloalto_panos",
        "aruba": "aruba_os",
        "hp procurve": "hp_procurve",
        "dell": "dell_os10",
    }
    for key, value in mapping.items():
        if key in os_lower:
            return value
    return "cisco_ios"  # Default conservador
