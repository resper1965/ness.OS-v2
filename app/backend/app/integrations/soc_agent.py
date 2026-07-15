import json
import logging
from typing import Any, TypedDict

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0)


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


def triage_wazuh_alert(alert_payload: dict[str, Any]) -> TriageResult:
    """Realiza a triagem inteligente de um alerta do Wazuh usando o Gemini 2.5 Flash."""
    # Obter chave de API a partir de gemini_api_key
    gemini_key = getattr(settings, "gemini_api_key", None)
    if not gemini_key:
        logger.warning("Gemini API key não configurada para triagem SOC. Usando fallback padrão.")
        return {
            "classification": "HIGH",
            "confidence": 0.5,
            "summary": f"Alerta Wazuh: {alert_payload.get('description', 'Sem descrição')}. Triagem automática indisponível devido a chave de API ausente.",
            "action_taken": "Criar ticket de triagem manual",
        }

    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {"Content-Type": "application/json"}
    
    body = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"Alerta Wazuh a ser analisado:\n{json.dumps(alert_payload, indent=2, ensure_ascii=False)}"
                    }
                ]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": _SOC_SYSTEM_PROMPT}]
        },
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "classification": {
                        "type": "STRING",
                        "enum": ["FP", "LOW", "MED", "HIGH", "CRIT"]
                    },
                    "confidence": {
                        "type": "NUMBER"
                    },
                    "summary": {
                        "type": "STRING"
                    },
                    "action_taken": {
                        "type": "STRING"
                    }
                },
                "required": ["classification", "confidence", "summary", "action_taken"]
            }
        }
    }

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(
                api_url,
                json=body,
                params={"key": gemini_key},
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()
            
            text_response = (
                result.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "{}")
            )
            
            triage_data = json.loads(text_response)
            logger.info(
                "Triage SOC concluída via Gemini | classificação=%s confiança=%s",
                triage_data.get("classification"),
                triage_data.get("confidence"),
            )
            return triage_data

    except Exception as exc:
        logger.error("Falha ao realizar triagem via Gemini: %s", exc)
        return {
            "classification": "HIGH",
            "confidence": 0.5,
            "summary": f"Erro na triagem automática: {str(exc)}. Alerta original: {alert_payload.get('description', 'Sem descrição')}",
            "action_taken": "Criar ticket de triagem manual",
        }
