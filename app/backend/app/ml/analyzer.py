import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=5.0)

class AIAnalysisResult(BaseModel):
    executive_action_plan: str = Field(..., description="Plano de ação resumido e executivo para o cliente final")
    technical_action_plan: str = Field(..., description="Passo a passo técnico detalhado de mitigação para a equipe de NOC/SOC")
    urgency: str = Field(..., description="Grau de urgência determinado: LOW, MEDIUM, HIGH, CRITICAL")
    isolation_required: bool = Field(..., description="Indica se é necessário isolamento do host ou ativo afetado")
    probable_cause: str = Field(..., description="Causa provável do problema analisado")
    recommended_playbook: str = Field(..., description="Nome do playbook aplicável sugerido")

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

async def analyze_incident(
    incident_data: Dict[str, Any],
    customer_metadata: Optional[Dict[str, Any]] = None,
    playbooks: Optional[List[str]] = None
) -> AIAnalysisResult:
    """Realiza análise estruturada do incidente usando Gemini AI.
    
    Retorna um objeto Pydantic com a triagem estruturada do incidente.
    """
    if not settings.gemini_api_key:
        logger.warning("Gemini API key não configurada. Retornando análise padrão/mock.")
        return AIAnalysisResult(
            executive_action_plan="Sem chave Gemini. Verificação manual necessária.",
            technical_action_plan="Verificar logs locais do Zabbix/sistema.",
            urgency="MEDIUM",
            isolation_required=False,
            probable_cause="Indeterminada (Sem IA)",
            recommended_playbook="Default Troubleshooting"
        )

    # Lista de playbooks padrão/disponíveis
    available_playbooks = playbooks or [
        "Restabelecer Link WAN (SD-WAN Route Reset)",
        "Limpeza de Disco e Logs de Sistema",
        "Reiniciar Serviço do Servidor de Aplicação",
        "Isolamento de Host por Malware/Ransomware (EDR Lock)",
        "Bloquear IP no Firewall de Borda (Contabo Security)",
        "Análise de Conectividade VPN / IPSec Reset",
    ]

    prompt = f"""
# Dados do Incidente:
{json.dumps(incident_data, indent=2, ensure_ascii=False)}

# Metadados do Cliente:
{json.dumps(customer_metadata or {}, indent=2, ensure_ascii=False)}

# Playbooks Disponíveis:
{json.dumps(available_playbooks, indent=2, ensure_ascii=False)}

Gere a análise estruturada em JSON correspondente ao incidente acima.
"""

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "executive_action_plan": {"type": "STRING"},
            "technical_action_plan": {"type": "STRING"},
            "urgency": {"type": "STRING", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
            "isolation_required": {"type": "BOOLEAN"},
            "probable_cause": {"type": "STRING"},
            "recommended_playbook": {"type": "STRING"}
        },
        "required": ["executive_action_plan", "technical_action_plan", "urgency", "isolation_required", "probable_cause", "recommended_playbook"]
    }

    request_body = {
        "system_instruction": {"parts": [{"text": _ANALYZER_SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        },
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.post(
                api_url,
                json=request_body,
                params={"key": settings.gemini_api_key},
                headers={"Content-Type": "application/json"}
            )
            res.raise_for_status()
            result = res.json()

        raw_text = (
            result.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        
        data = json.loads(raw_text)
        return AIAnalysisResult(**data)

    except Exception as exc:
        logger.error("Falha ao rodar analisador IA: %s", exc)
        return AIAnalysisResult(
            executive_action_plan=f"Incidente sob análise. Impacto em {incident_data.get('host_name', 'host')}.",
            technical_action_plan=f"Investigar falha no trigger {incident_data.get('trigger_name', 'zabbix')}.",
            urgency="MEDIUM",
            isolation_required=False,
            probable_cause=f"Falha de comunicação/IA: {str(exc)}",
            recommended_playbook="Default Troubleshooting"
        )
