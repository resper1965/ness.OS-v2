# -------------------------------------------------------
# n.infraops — Datto RMM Driver
# -------------------------------------------------------
"""
Implementação concreta para execução de playbooks via
Datto RMM API (componente 'Quick Jobs' ou 'ComStore').

Referência: https://rmm-api-docs.datto.com/
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


class DattoRMMDriver(BaseRMMDriver):
    """Driver para Datto RMM API.

    Usa a API REST do Datto para:
      1. Verificar status do device.
      2. Executar Quick Jobs (scripts PowerShell/Bash).
      3. Monitorar resultado da execução.
    """

    def __init__(self, api_key: str, api_secret: str, api_url: str) -> None:
        super().__init__(api_key=api_key, api_url=api_url)
        self.api_secret = api_secret
        self._token: str | None = None
        self._token_expiry: float = 0

    def _get_auth_headers(self) -> dict[str, str]:
        """Obtém token OAuth2 com cache."""
        if self._token and time.time() < self._token_expiry:
            return {"Authorization": f"Bearer {self._token}"}

        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(
                f"{self.api_url}/auth/oauth/token",
                data={"grant_type": "password"},
                auth=(self.api_key, self.api_secret),
            )
            response.raise_for_status()
            data = response.json()

        self._token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600) - 60
        return {"Authorization": f"Bearer {self._token}"}

    def execute_playbook(
        self,
        device_id: str,
        playbook_name: str,
        params: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> PlaybookResult:
        """Executa Quick Job no device via Datto API."""
        start = time.monotonic()

        if dry_run:
            logger.info(
                "[DRY_RUN] Datto | device=%s playbook=%s",
                device_id,
                playbook_name,
            )
            return PlaybookResult(
                status=ExecutionStatus.DRY_RUN,
                output=f"Simulação: {playbook_name} em {device_id}",
                duration_ms=0,
            )

        try:
            headers = self._get_auth_headers()

            # Criar Quick Job
            job_payload = {
                "jobName": f"n.infraops: {playbook_name}",
                "deviceId": device_id,
                "componentName": playbook_name,
                "variables": params or {},
            }

            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.post(
                    f"{self.api_url}/api/v2/device/{device_id}/quickjob",
                    json=job_payload,
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()

            elapsed = int((time.monotonic() - start) * 1000)

            logger.info(
                "Datto job criado | device=%s job_id=%s",
                device_id,
                result.get("jobUid"),
            )

            return PlaybookResult(
                status=ExecutionStatus.SUCCESS,
                output=f"Job {result.get('jobUid')} criado com sucesso",
                duration_ms=elapsed,
                raw_response=result,
            )

        except httpx.HTTPError as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.error("Datto falhou | device=%s: %s", device_id, exc)
            return PlaybookResult(
                status=ExecutionStatus.FAILED,
                error=str(exc),
                duration_ms=elapsed,
            )

    def check_device_online(self, device_id: str) -> bool:
        """Verifica status do device no Datto."""
        try:
            headers = self._get_auth_headers()
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.get(
                    f"{self.api_url}/api/v2/device/{device_id}",
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
            return data.get("online", False)
        except httpx.HTTPError:
            return False

    def get_device_info(self, device_id: str) -> dict[str, Any]:
        """Retorna informações do device no Datto."""
        try:
            headers = self._get_auth_headers()
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.get(
                    f"{self.api_url}/api/v2/device/{device_id}",
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            logger.error("Datto get_device_info falhou: %s", exc)
            return {"error": str(exc)}
