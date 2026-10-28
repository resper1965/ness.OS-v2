import json
import logging
import time
from typing import Any, Dict, List, Literal, Optional

import httpx
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.ai_context import incident_ai_request, log_ai_call
from app.core.sanitizer import sanitize_value
from app.integrations.llm import achat_completion

logger = logging.getLogger(__name__)
settings = get_settings()

_TIMEOUT = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=5.0)
Urgency = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
URGENCY_ORDER = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


class AIAnalysisResult(BaseModel):
    executive_action_plan: str = Field(
        ..., description="Plano de ação resumido e executivo para o cliente final"
    )
    technical_action_plan: str = Field(
        ...,
        description="Passo a passo técnico detalhado de mitigação para a equipe de NOC/SOC",
    )
    urgency: Urgency = Field(
        ..., description="Grau de urgência determinado: LOW, MEDIUM, HIGH, CRITICAL"
    )
    isolation_required: bool = Field(
        ..., description="Indica se é necessário isolamento do host ou ativo afetado"
    )
    probable_cause: str = Field(..., description="Causa provável do problema analisado")
    recommended_playbook: str = Field(
        ..., description="Nome do playbook aplicável sugerido"
    )


_ANALYZER_SYSTEM_PROMPT = """Você é um especialista em AIOps e SecOps sênior da ness.
Analise o incidente técnico fornecido, juntamente com os metadados do cliente e os playbooks disponíveis.
Você deve determinar a causa provável, o grau de urgência, se é necessário isolar o host/ativo afetado, e recomendar um plano de ação executivo e técnico.

Sua resposta DEVE ser estritamente no formato JSON que siga o seguinte schema:
{
  "executive_action_plan": "Plano de ação resumido e executivo para o cliente final",
  "technical_action_plan": "Passo a passo técnico detalhado de mitigação para a equipe de NOC/SOC",
  "urgency": "LOW / MEDIUM / HIGH / CRITICAL",
  "isolation_required": true/false,
  "probable_cause": "Causa provável do problema analisado",
  "recommended_playbook": "Nome do playbook aplicável sugerido"
}
"""


def source_urgency(incident_data: Dict[str, Any]) -> Urgency:
    severity = incident_data.get("severity")
    severity = getattr(severity, "value", severity)
    value = str(severity).strip().upper()
    if value in {"5", "DISASTER", "CRITICAL"}:
        return "CRITICAL"
    if value in {"4", "HIGH"}:
        return "HIGH"
    if value in {"1", "INFORMATION", "LOW"}:
        return "LOW"
    # Missing, unclassified and unknown severity require manual triage.
    return "MEDIUM"


def manual_triage(incident_data: Dict[str, Any]) -> AIAnalysisResult:
    return AIAnalysisResult(
        executive_action_plan=f"Incidente sob análise. Impacto em {incident_data.get('host_name', 'host')}.",
        technical_action_plan=(
            f"Investigar falha no trigger {incident_data.get('trigger_name', 'zabbix')}. "
            "Validar impacto e causa antes de executar qualquer ação corretiva."
        ),
        urgency=source_urgency(incident_data),
        isolation_required=False,
        probable_cause="Análise IA indisponível. Triagem manual necessária.",
        recommended_playbook="Default Troubleshooting",
    )


async def analyze_incident(
    incident_data: Dict[str, Any],
    customer_metadata: Optional[Dict[str, Any]] = None,
    playbooks: Optional[List[str]] = None,
) -> AIAnalysisResult:
    """Realiza análise estruturada do incidente usando LLM.

    Retorna um objeto Pydantic com a triagem estruturada do incidente.
    """
    if not settings.llm_api_key:
        logger.warning("LLM indisponível: triagem manual com severidade de origem.")
        return manual_triage(incident_data)

    # Lista de playbooks padrão/disponíveis
    available_playbooks = playbooks or [
        "Restabelecer Link WAN (SD-WAN Route Reset)",
        "Limpeza de Disco e Logs de Sistema",
        "Reiniciar Serviço do Servidor de Aplicação",
        "Isolamento de Host por Malware/Ransomware (EDR Lock)",
        "Bloquear IP no Firewall de Borda (Contabo Security)",
        "Análise de Conectividade VPN / IPSec Reset",
    ]

    ai_request = incident_ai_request(
        incident_data, (customer_metadata or {}).get("customer_name")
    )
    prompt = f"""
# Dados do Incidente:
{json.dumps(ai_request.model_dump(mode="json"), indent=2, ensure_ascii=False)}

# Escopo: somente o incidente atual; sem credenciais ou cadastro do cliente.

# Playbooks Disponíveis:
{json.dumps(sanitize_value(available_playbooks), indent=2, ensure_ascii=False)}

Gere a análise estruturada em JSON correspondente ao incidente acima.
"""

    response_schema = {
        "type": "OBJECT",
        "properties": {
            "executive_action_plan": {"type": "STRING"},
            "technical_action_plan": {"type": "STRING"},
            "urgency": {
                "type": "STRING",
                "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            },
            "isolation_required": {"type": "BOOLEAN"},
            "probable_cause": {"type": "STRING"},
            "recommended_playbook": {"type": "STRING"},
        },
        "required": [
            "executive_action_plan",
            "technical_action_plan",
            "urgency",
            "isolation_required",
            "probable_cause",
            "recommended_playbook",
        ],
    }

    started = time.perf_counter()
    usage: Dict[str, Any] = {}
    outcome = "error"
    try:
        raw_text, usage = await achat_completion(
            _ANALYZER_SYSTEM_PROMPT,
            prompt,
            json_schema=response_schema,
            temperature=0.2,
            max_tokens=2048,
            timeout=_TIMEOUT,
        )

        data = json.loads(raw_text)
        analysis = AIAnalysisResult(**data)
        minimum = source_urgency(incident_data)
        if URGENCY_ORDER.index(analysis.urgency) < URGENCY_ORDER.index(minimum):
            analysis.urgency = minimum
        outcome = "ok"
        return analysis

    except Exception as exc:
        logger.error("Falha ao rodar analisador IA: %s", type(exc).__name__)
        return manual_triage(incident_data)
    finally:
        log_ai_call("incident_analysis", outcome, started, usage)
