# -------------------------------------------------------
# n.infraops — Atera RMM Driver
# -------------------------------------------------------
"""
Implementação concreta para execução de playbooks via
Atera API v3 (Scripts & Automation).

Referência: https://app.atera.com/apidocs
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.remediators.base import (
    BaseRMMDriver,
    ExecutionStatus,
    PlaybookResult,
)

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0)
_ATERA_API_BASE = "https://app.atera.com/api/v3"


class AteraRMMDriver(BaseRMMDriver):
    """Driver para Atera API v3.

    Usa API Key no header X-API-KEY para:
      1. Verificar status do agente.
      2. Executar scripts remotos.
      3. Consultar informações do device.
    """

    def __init__(self, api_key: str, api_url: str = _ATERA_API_BASE) -> None:
        super().__init__(api_key=api_key, api_url=api_url)

    def _headers(self) -> dict[str, str]:
        return {
            "X-API-KEY": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def execute_playbook(
        self,
        device_id: str,
        playbook_name: str,
        params: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> PlaybookResult:
        """Executa script remoto no agente via Atera API."""
        start = time.monotonic()

        if dry_run:
            logger.info(
                "[DRY_RUN] Atera | device=%s playbook=%s",
                device_id,
                playbook_name,
            )
            return PlaybookResult(
                status=ExecutionStatus.DRY_RUN,
                output=f"Simulação: {playbook_name} em {device_id}",
                duration_ms=0,
            )

        try:
            # Atera usa RunCommandScript para execução remota
            script_payload = {
                "AgentID": int(device_id),
                "ScriptName": playbook_name,
                "Arguments": params.get("arguments", "") if params else "",
            }

            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.post(
                    f"{self.api_url}/agents/{device_id}/runscript",
                    json=script_payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                result = response.json()

            elapsed = int((time.monotonic() - start) * 1000)

            logger.info(
                "Atera script executado | device=%s script=%s",
                device_id,
                playbook_name,
            )

            return PlaybookResult(
                status=ExecutionStatus.SUCCESS,
                output=result.get("Output", "Script enfileirado"),
                duration_ms=elapsed,
                raw_response=result,
            )

        except httpx.HTTPError as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.error("Atera falhou | device=%s: %s", device_id, exc)
            return PlaybookResult(
                status=ExecutionStatus.FAILED,
                error=str(exc),
                duration_ms=elapsed,
            )

    def check_device_online(self, device_id: str) -> bool:
        """Verifica se o agente Atera está online."""
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.get(
                    f"{self.api_url}/agents/{device_id}",
                    headers=self._headers(),
                )
                response.raise_for_status()
                data = response.json()
            return data.get("Online", False)
        except httpx.HTTPError:
            return False

    def get_device_info(self, device_id: str) -> dict[str, Any]:
        """Retorna informações do agente no Atera."""
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.get(
                    f"{self.api_url}/agents/{device_id}",
                    headers=self._headers(),
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            logger.error("Atera get_device_info falhou: %s", exc)
            return {"error": str(exc)}
