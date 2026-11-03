import asyncio
import json
import logging
import math
import time
from typing import Any, TypedDict

import httpx

from app.config import get_settings
from app.core.ai_context import AIRequestV1, _observed_at, log_ai_call
from app.integrations.llm import achat_completion

logger = logging.getLogger(__name__)
settings = get_settings()

_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0)
_DEADLINE = (
    45.0  # prazo total da chamada ao modelo; o atendimento não espera além disso
)


class TriageResult(TypedDict):
    classification: str  # FP, LOW, MED, HIGH, CRIT
    confidence: float
    summary: str
    action_taken: str


_SOC_SYSTEM_PROMPT = """\
Você é um analista de segurança (SOC) sênior da ness. operando sob o ness.OS (módulo n.secops).
Sua tarefa é analisar alertas de segurança gerados pelo Wazuh (sysmon, integridade de arquivos, auditoria) enriquecidos com dados adicionais (VirusTotal, AbuseIPDB, MITRE) e gerar uma decisão de triagem automatizada.

Classifique a severidade operacional real do alerta em uma das cinco categorias:
- "FP" (False Positive): Alertas gerados por ferramentas autorizadas, ruídos de rede conhecidos ou falso positivo comprovado.
- "LOW": Evento real de baixo risco (ex: alteração de configuração esperada sem impacto, varredura de porta externa bloqueada).
- "MED": Evento suspeito de médio risco (ex: múltiplas tentativas falhas de login de origem interna, software não homologado instalado).
- "HIGH": Alerta de alto risco (ex: alteração de arquivo crítico do sistema, comportamento anômalo de processo, malware detectado localmente).
- "CRIT": Incidente crítico com exploração ativa (ex: ransomware detectado, exfiltração de dados confirmada, RCE abusado com sucesso).

Você deve responder rigorosamente no formato JSON com os seguintes campos:
- "classification": "FP" | "LOW" | "MED" | "HIGH" | "CRIT"
- "confidence": um valor float entre 0.0 e 1.0 representando sua confiança na decisão.
- "summary": uma descrição executiva e técnica resumida em Português (PT-BR) contendo o que aconteceu e o diagnóstico.
- "action_taken": a ação recomendada a ser tomada (ex: "Auto-close", "Create ticket", "Alerter analista on-call").
"""


_WAZUH_FIELDS = (
    "rule",
    "full_log",
    "data",
    "syscheck",
    "location",
    "decoder",
    "threat_intel_enrichment",
)


_CLASSES = ("FP", "LOW", "MED", "HIGH", "CRIT")


class SignalRejected(ValueError):
    """Campo do resultado do modelo fora do contrato; carrega o campo e o valor recebido."""

    def __init__(self, field: str, value: Any):
        super().__init__(f"invalid {field}")
        self.field, self.value = field, value


def _validated(data: Any) -> TriageResult:
    """Reject anything the schema should have guaranteed; caller falls back."""
    if not isinstance(data, dict):
        raise SignalRejected("result", data)
    conf = data.get("confidence")
    if data.get("classification") not in _CLASSES:
        raise SignalRejected("classification", data.get("classification"))
    if isinstance(conf, bool) or not isinstance(conf, int | float):
        raise SignalRejected("confidence", conf)
    if not math.isfinite(conf) or not 0.0 <= conf <= 1.0:  # json.loads accepts NaN
        raise SignalRejected("confidence", conf)
    for key in ("summary", "action_taken"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise SignalRejected(key, data.get(key))
    # Só os quatro campos; action_taken cabe na coluna (String(255)).
    return {
        "classification": data["classification"],
        "confidence": float(conf),
        "summary": data["summary"],
        "action_taken": data["action_taken"].strip()[:255],
    }


def wazuh_ai_request(alert: dict[str, Any], tenant: str) -> AIRequestV1:
    """Allowlist Wazuh fields; manager/cluster and unknown keys never leave."""
    raw_agent, raw_rule = alert.get("agent"), alert.get("rule")
    agent: dict[str, Any] = raw_agent if isinstance(raw_agent, dict) else {}
    rule: dict[str, Any] = raw_rule if isinstance(raw_rule, dict) else {}
    evidence = {k: alert[k] for k in _WAZUH_FIELDS if k in alert}
    evidence["agent"] = {k: agent[k] for k in ("id", "name") if k in agent}
    return AIRequestV1(
        tenant=tenant,
        source_event_id=str(alert.get("id") or f"{agent.get('id')}:{rule.get('id')}"),
        severity=str(rule.get("level", "unknown")),
        observed_at=_observed_at(alert.get("timestamp")),
        evidence=evidence,
    )


def _manual_fallback(alert: dict[str, Any], reason: str) -> TriageResult:
    """Modelo indisponível ou resposta rejeitada: o atendimento segue, para triagem manual."""
    return {
        "classification": "HIGH",
        "confidence": 0.5,
        "summary": f"Erro na triagem automática: {reason}. Alerta original: {alert.get('description', 'Sem descrição')}",
        "action_taken": "Criar ticket de triagem manual",
    }


async def triage_wazuh_alert(
    alert_payload: dict[str, Any], tenant: str
) -> TriageResult:
    """Triagem de um alerta Wazuh via LLM. `tenant` vem do vínculo administrativo,
    nunca do payload. Nunca levanta: falha do modelo devolve fallback manual."""
    if not settings.llm_api_key:
        logger.warning(
            "LLM API key não configurada para triagem SOC. Usando fallback padrão."
        )
        return {
            "classification": "HIGH",
            "confidence": 0.5,
            "summary": f"Alerta Wazuh: {alert_payload.get('description', 'Sem descrição')}. Triagem automática indisponível devido a chave de API ausente.",
            "action_taken": "Criar ticket de triagem manual",
        }

    ai_request = wazuh_ai_request(alert_payload, tenant)
    user = f"Alerta Wazuh a ser analisado:\n{json.dumps(ai_request.model_dump(mode='json'), indent=2, ensure_ascii=False)}"
    schema = {
        "type": "OBJECT",
        "properties": {
            "classification": {
                "type": "STRING",
                "enum": ["FP", "LOW", "MED", "HIGH", "CRIT"],
            },
            "confidence": {"type": "NUMBER"},
            "summary": {"type": "STRING"},
            "action_taken": {"type": "STRING"},
        },
        "required": ["classification", "confidence", "summary", "action_taken"],
    }

    started = time.perf_counter()
    usage: dict[str, Any] = {}
    outcome = "error"
    try:
        text_response, usage = await asyncio.wait_for(
            achat_completion(
                _SOC_SYSTEM_PROMPT,
                user,
                json_schema=schema,
                temperature=0.2,
                max_tokens=2048,
                timeout=_TIMEOUT,
            ),
            timeout=_DEADLINE,
        )
        triage_data = _validated(json.loads(text_response))
        outcome = "ok"
        logger.info(
            "Triage SOC concluída via LLM | classificação=%s confiança=%s",
            triage_data.get("classification"),
            triage_data.get("confidence"),
        )
        return triage_data
    except SignalRejected as exc:
        logger.error(
            "Sinal %s: resultado do modelo rejeitado | campo=%s valor=%s",
            ai_request.source_event_id,
            exc.field,
            # texto livre do modelo pode ecoar dado do alerta: só tipo e tamanho
            (
                repr(exc.value)[:80]
                if exc.field in ("classification", "confidence")
                else f"<{type(exc.value).__name__} len={len(str(exc.value))}>"
            ),
        )
        return _manual_fallback(alert_payload, "SignalRejected")
    except Exception as exc:
        logger.error(
            "Sinal %s: falha na triagem via LLM: %s",
            ai_request.source_event_id,
            type(exc).__name__,
        )
        return _manual_fallback(alert_payload, type(exc).__name__)
    finally:
        log_ai_call("soc_triage", outcome, started, usage)
