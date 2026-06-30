# -------------------------------------------------------
# n.infraops — BaseRMMDriver (contrato abstrato)
# -------------------------------------------------------
"""
Interface que todo driver de RMM deve implementar.

O motor de execução de playbooks usa o Factory Pattern:
  1. Consulta o ativo no banco → descobre rmm_provider.
  2. RMMFactory instancia o driver correto.
  3. O driver executa o playbook via API do RMM ou SSH.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DRY_RUN = "dry_run"


@dataclass(frozen=True, slots=True)
class PlaybookResult:
    """Resultado padronizado da execução de um playbook."""

    status: ExecutionStatus
    output: str = ""
    error: str = ""
    duration_ms: int = 0
    raw_response: dict[str, Any] = field(default_factory=dict)


class BaseRMMDriver(ABC):
    """Contrato abstrato para drivers de RMM.

    Cada implementação concreta encapsula a comunicação com
    um provedor de RMM específico (Datto, Atera) ou execução
    direta via SSH (para network devices sem agente).
    """

    def __init__(self, api_key: str, api_url: str = "") -> None:
        self.api_key = api_key
        self.api_url = api_url

    @abstractmethod
    def execute_playbook(
        self,
        device_id: str,
        playbook_name: str,
        params: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> PlaybookResult:
        """Executa um playbook no dispositivo remoto.

        Args:
            device_id: ID do dispositivo no RMM ou hostname/IP para SSH.
            playbook_name: Nome do playbook a executar.
            params: Parâmetros adicionais (variáveis do playbook).
            dry_run: Se True, simula sem executar.

        Returns:
            PlaybookResult com status, output e metadados.
        """
        ...

    @abstractmethod
    def check_device_online(self, device_id: str) -> bool:
        """Verifica se o dispositivo está online/acessível."""
        ...

    @abstractmethod
    def get_device_info(self, device_id: str) -> dict[str, Any]:
        """Retorna informações do dispositivo no RMM."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(api_url={self.api_url!r})"
