import json
import logging
import time
from typing import Any, Dict

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LokiClient:
    """Cliente de integração para persistência de inteligência operacional no Grafana Loki."""

    def __init__(self):
        self.url = settings.loki_url
        self.headers = {"Content-Type": "application/json"}

    async def send_json_log(
        self, tenant_id: str, log_data: Dict[str, Any], labels: Dict[str, str]
    ) -> bool:
        """Envia o log JSON estruturado da IA para o Loki com isolamento de tenant via X-Scope-OrgID.

        Args:
            tenant_id: Identificador único do cliente para o cabeçalho X-Scope-OrgID.
            log_data: Dicionário completo do JSON gerado pela IA.
            labels: Dicionário de etiquetas para indexação nativa (ex: framework, regulacao, criticidade).
        """
        if not self.url:
            logger.warning("Loki URL não configurada. Pulo no envio do log de AIOps.")
            return False

        # Configurar isolamento de tenant
        headers = self.headers.copy()
        headers["X-Scope-OrgID"] = tenant_id

        # Obter timestamp em nanosegundos (exigido pelo Loki)
        ns_timestamp = str(int(time.time() * 1e9))

        # Payload no formato Loki Push API v1
        payload = {
            "streams": [
                {"stream": labels, "values": [[ns_timestamp, json.dumps(log_data)]]}
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(self.url, headers=headers, json=payload)
                if res.status_code in (200, 204):
                    logger.info(
                        "Log AIOps enviado com sucesso ao Loki para tenant: %s",
                        tenant_id,
                    )
                    return True
                else:
                    logger.error(
                        "Falha ao enviar log ao Loki (HTTP %d) para tenant %s. Resposta: %s",
                        res.status_code,
                        tenant_id,
                        res.text,
                    )
                    return False
        except Exception as e:
            logger.error("Erro de conexão ao enviar log para o Loki: %s", e)
            return False
