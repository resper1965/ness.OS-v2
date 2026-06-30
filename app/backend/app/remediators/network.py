# -------------------------------------------------------
# n.infraops — Network Device Driver (SSH via Netmiko)
# -------------------------------------------------------
"""
Driver para ativos de rede sem agente RMM (switches,
firewalls, APs). Usa SSH via Netmiko para execução
de comandos ou roteamento para n8n.

Cobre rmm_provider = 'none' com asset_type = 'network_device'.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.remediators.base import (
    BaseRMMDriver,
    ExecutionStatus,
    PlaybookResult,
)

logger = logging.getLogger(__name__)

# Mapeamento de playbooks → comandos de rede
_NETWORK_PLAYBOOKS: dict[str, list[str]] = {
    "interface_reset": [
        "show interface {interface} status",
        "configure terminal",
        "interface {interface}",
        "shutdown",
        "no shutdown",
        "end",
        "show interface {interface} status",
    ],
    "clear_arp_cache": [
        "clear arp-cache",
        "show arp",
    ],
    "bgp_neighbor_reset": [
        "clear ip bgp {neighbor} soft",
        "show ip bgp summary",
    ],
    "save_config": [
        "write memory",
    ],
    "diagnostic": [
        "show version",
        "show interfaces status",
        "show ip route summary",
        "show logging last 50",
        "show processes cpu history",
    ],
}


class NetworkDriver(BaseRMMDriver):
    """Driver para network devices (SSH/Netmiko).

    Para ativos com rmm_provider='none', a execução acontece via:
      1. SSH direto usando Netmiko (Cisco IOS, Junos, etc.).
      2. Ou roteamento para n8n (se preferível para o ativo).
    """

    def __init__(
        self,
        hostname: str,
        username: str,
        ssh_port: int = 22,
        device_type: str = "cisco_ios",
        **kwargs: Any,
    ) -> None:
        # NetworkDriver não usa api_key/api_url
        super().__init__(api_key="", api_url="")
        self.hostname = hostname
        self.username = username
        self.ssh_port = ssh_port
        self.device_type = device_type

    def execute_playbook(
        self,
        device_id: str,
        playbook_name: str,
        params: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> PlaybookResult:
        """Executa sequência de comandos via SSH/Netmiko."""
        start = time.monotonic()

        commands = _NETWORK_PLAYBOOKS.get(playbook_name)
        if not commands:
            return PlaybookResult(
                status=ExecutionStatus.FAILED,
                error=f"Playbook '{playbook_name}' não encontrado para network devices",
                duration_ms=0,
            )

        # Substituir variáveis nos comandos
        resolved_commands = []
        for cmd in commands:
            try:
                resolved_commands.append(cmd.format(**(params or {})))
            except KeyError as e:
                return PlaybookResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Parâmetro obrigatório ausente: {e}",
                    duration_ms=0,
                )

        if dry_run:
            logger.info(
                "[DRY_RUN] Network | host=%s playbook=%s commands=%d",
                self.hostname,
                playbook_name,
                len(resolved_commands),
            )
            return PlaybookResult(
                status=ExecutionStatus.DRY_RUN,
                output="\n".join(f"  → {c}" for c in resolved_commands),
                duration_ms=0,
            )

        try:
            # Import tardio — Netmiko é pesado e só precisa em network
            from netmiko import ConnectHandler  # type: ignore[import-untyped]

            device_config = {
                "device_type": self.device_type,
                "host": self.hostname,
                "username": self.username,
                "port": self.ssh_port,
                # Em produção: key_file ou lookup no vault
            }

            with ConnectHandler(**device_config) as conn:
                output_lines: list[str] = []
                for cmd in resolved_commands:
                    result = conn.send_command(cmd, read_timeout=30)
                    output_lines.append(f">>> {cmd}\n{result}")

            elapsed = int((time.monotonic() - start) * 1000)

            logger.info(
                "Network playbook executado | host=%s playbook=%s cmds=%d",
                self.hostname,
                playbook_name,
                len(resolved_commands),
            )

            return PlaybookResult(
                status=ExecutionStatus.SUCCESS,
                output="\n\n".join(output_lines),
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.error(
                "Network falhou | host=%s: %s", self.hostname, exc
            )
            return PlaybookResult(
                status=ExecutionStatus.FAILED,
                error=str(exc),
                duration_ms=elapsed,
            )

    def check_device_online(self, device_id: str) -> bool:
        """Tenta SSH rápido para verificar conectividade."""
        import socket

        try:
            sock = socket.create_connection(
                (self.hostname, self.ssh_port), timeout=5
            )
            sock.close()
            return True
        except (socket.timeout, OSError):
            return False

    def get_device_info(self, device_id: str) -> dict[str, Any]:
        """Retorna info básica do device via SSH."""
        return {
            "hostname": self.hostname,
            "device_type": self.device_type,
            "ssh_port": self.ssh_port,
            "driver": "network_ssh",
        }
