# -------------------------------------------------------
# n.infraops — Cliente Gemini (geração de Post-Mortem)
# -------------------------------------------------------
"""
Chama a API do Gemini 2.5 Flash para gerar relatórios pós-incidente
em Markdown. Usa a janela de 1M tokens para análise profunda de
logs, métricas e contexto do incidente.

Os dados passam pelo sanitizer ANTES de chegar aqui.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import get_settings
from app.core.ai_context import incident_prompt_data
from app.core.sanitizer import sanitize, sanitize_value
from app.models.schemas import PostMortemReport

logger = logging.getLogger(__name__)
settings = get_settings()

_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=5.0)


def generate_embedding(text: str) -> list[float]:
    """Gera embedding de 768 dimensões usando o modelo text-embedding-004 do Gemini."""
    if not settings.gemini_api_key:
        logger.warning("Gemini API key não configurada. Retornando embedding zerado.")
        return [0.0] * 768

    api_url = "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": settings.gemini_api_key,
    }
    body = {
        "model": "models/text-embedding-004",
        "content": {"parts": [{"text": sanitize(text)}]},
    }
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(
                api_url,
                json=body,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("embedding", {}).get("values", [0.0] * 768)
    except Exception as exc:
        logger.error("Falha ao gerar embedding via Gemini: %s", type(exc).__name__)
        return [0.0] * 768


# Prompt estruturado para o Gemini
_POSTMORTEM_SYSTEM_PROMPT = """\
Você é um engenheiro SRE sênior da ness. gerando um relatório pós-incidente baseado nos padrões da indústria (Google SRE Book, PagerDuty Post-Mortem).
Analise os dados do incidente e produza um relatório DENSO e PROFISSIONAL em Markdown com as seguintes seções.

## Estrutura obrigatória:

1. **Metadados do Incidente**
   - Severidade: [Severidade do Incidente]
   - MTTR (Tempo Médio de Resolução): [Duração Estimada]
   - Lead SRE: ness. AIOps Agent

2. **Resumo Executivo**
   - Escreva 2-3 frases resumidas sobre o que aconteceu, o impacto comercial e como foi mitigado.

3. **Linha do Tempo**
   - Apresente uma tabela cronológica detalhada dos eventos no formato:
     | Timestamp | Evento |
     |---|---|
     | [Horário] | Detecção do incidente via Zabbix |
     | [Horário] | Triage e escalonamento |
     | [Horário] | Aplicação da mitigação |
     | [Horário] | Resolução e validação |

4. **Causa Raiz**
   - **Análise Técnica Detalhada**: Explicação técnica aprofundada de por que a falha ocorreu.
   - **Os 5 Porquês (5 Whys)**: Aplique a técnica dos 5 Porquês sequenciais para investigar as causas sistêmicas subjacentes (Por que aconteceu? -> Por que X ocorreu? -> etc. até o 5º nível).

5. **Blast Radius**
   - Apresente como lista de itens os serviços, portas, bancos de dados, hosts ou clientes diretamente afetados.

6. **Logs Relevantes**
   - Apresente trechos de log que explicam e comprovam a conclusão da causa raiz.

7. **Ações Corretivas**
   - Apresente como lista de itens contendo ações corretivas de curto prazo (mitigações) e longo prazo (melhorias de arquitetura para prevenir reincidência), cada uma com prioridade indicada (P0, P1, P2).

8. **Métricas Analisadas**
   - Dados numéricos das métricas que apoiam a análise.

9. **Lições Aprendidas (Lessons Learned)**
   - O que funcionou bem no processo de resposta.
   - O que deu errado ou poderia ter sido melhor.
   - Onde tivemos sorte.

## Regras:
- Seja extremamente objetivo, analítico e técnico.
- NÃO invente dados. Se não houver informação suficiente, diga explicitamente.
- Todos os IPs e credenciais sensíveis devem ser sanitizados para [IP_REDACTED].
- Formato de saída: Markdown válido.
- Responda em Português (Brasil).
"""


def build_postmortem_prompt(
    incident: dict[str, Any],
    metrics: list[dict[str, Any]],
    related_logs: list[str],
    similar_incidents: list[dict[str, Any]] | None = None,
) -> str:
    """Monta o prompt completo para o Gemini.

    Args:
        incident: Dados sanitizados do incidente.
        metrics: Métricas do TimescaleDB (últimas 24h do host).
        related_logs: Logs sanitizados relacionados ao trigger.
        similar_incidents: Incidentes anteriores similares (do pgvector).

    Returns:
        Prompt em texto plano pronto para envio.
    """
    context_parts = [
        "# Dados do Incidente",
        f"```json\n{json.dumps(incident_prompt_data(incident), indent=2, ensure_ascii=False)}\n```",
        "",
        "# Métricas Recentes (últimas 24h)",
        f"```json\n{json.dumps(sanitize_value(metrics[:50]), indent=2, ensure_ascii=False)}\n```",
        "",
        "# Logs Relacionados",
    ]

    for log_entry in related_logs[:100]:  # Cap para não estourar contexto
        context_parts.append(f"- {sanitize(log_entry)}")

    if similar_incidents:
        context_parts.append("")
        context_parts.append("# Incidentes Similares Anteriores")
        for si in similar_incidents[:5]:
            if (
                not incident.get("customer_name")
                or str(si.get("customer_name", "")).casefold()
                != str(incident["customer_name"]).casefold()
            ):
                continue
            si = sanitize_value(si)
            context_parts.append(
                f"- [{si.get('fingerprint', '?')[:12]}] "
                f"{si.get('title', '?')} — {si.get('root_cause', 'N/A')}"
            )

    context_parts.append("")
    context_parts.append("Gere o relatório pós-incidente completo.")

    return "\n".join(context_parts)


def generate_postmortem(
    incident: dict[str, Any],
    metrics: list[dict[str, Any]],
    related_logs: list[str],
    similar_incidents: list[dict[str, Any]] | None = None,
) -> PostMortemReport:
    """Chama o Gemini 2.5 Flash e retorna o relatório estruturado.

    Usa a API REST do Google AI Studio (generateContent).
    """
    prompt = build_postmortem_prompt(incident, metrics, related_logs, similar_incidents)

    api_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )

    request_body = {
        "system_instruction": {"parts": [{"text": _POSTMORTEM_SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 8192,
            "responseMimeType": "text/plain",
        },
    }

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(
                api_url,
                json=request_body,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": settings.gemini_api_key,
                },
            )
            response.raise_for_status()
            result = response.json()

        # Extrair texto gerado
        markdown = (
            result.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        # Extrair metadados de uso
        usage = result.get("usageMetadata", {})

        logger.info(
            "Post-mortem gerado | fingerprint=%s tokens_in=%d tokens_out=%d",
            incident.get("fingerprint", "?"),
            usage.get("promptTokenCount", 0),
            usage.get("candidatesTokenCount", 0),
        )

        return PostMortemReport(
            incident_fingerprint=incident.get("fingerprint", ""),
            deskmanager_ticket_id=incident.get("deskmanager_ticket_id"),
            host_name=incident.get("host_name"),
            customer_name=incident.get("customer_name") or incident.get("client"),
            markdown_report=markdown,
            summary=_extract_section(markdown, "Resumo Executivo"),
            root_cause=_extract_section(markdown, "Causa Raiz"),
            blast_radius=_extract_list_section(markdown, "Blast Radius"),
            corrective_actions=_extract_list_section(markdown, "Ações Corretivas"),
            timeline=_extract_timeline(markdown),
            embedding=generate_embedding(markdown),
            gemini_model_used=settings.gemini_model,
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
        )

    except httpx.HTTPError as exc:
        logger.error("Falha na chamada ao Gemini: %s", type(exc).__name__)
        # Fallback: relatório mínimo sem IA
        return PostMortemReport(
            incident_fingerprint=incident.get("fingerprint", ""),
            deskmanager_ticket_id=incident.get("deskmanager_ticket_id"),
            host_name=incident.get("host_name"),
            customer_name=incident.get("customer_name") or incident.get("client"),
            markdown_report=(
                "# Relatório Pós-Incidente\n\n"
                "> ⚠️ Geração automática falhou. Análise manual necessária.\n\n"
                f"**Incidente:** {incident.get('title', '?')}\n"
                f"**Host:** {incident.get('host_name', '?')}\n"
                f"**Erro Gemini:** {type(exc).__name__}\n"
            ),
            summary="Geração automática falhou",
            root_cause="Análise manual necessária",
            gemini_model_used=settings.gemini_model,
        )


# --- Parsers auxiliares (extração de seções do Markdown) ---


def _extract_section(markdown: str, heading: str) -> str:
    """Extrai o conteúdo de uma seção H2 do Markdown."""
    lines = markdown.split("\n")
    capturing = False
    result: list[str] = []

    for line in lines:
        if line.strip().startswith("##") and heading.lower() in line.lower():
            capturing = True
            continue
        if capturing and line.strip().startswith("##"):
            break
        if capturing:
            result.append(line)

    return "\n".join(result).strip() or f"Seção '{heading}' não encontrada."


def _extract_list_section(markdown: str, heading: str) -> list[str]:
    """Extrai items de lista (- item) de uma seção H2."""
    section = _extract_section(markdown, heading)
    return [
        line.lstrip("- ").strip()
        for line in section.split("\n")
        if line.strip().startswith("-")
    ]


def _extract_timeline(markdown: str) -> list[dict[str, str]]:
    """Extrai timeline de uma tabela Markdown (| timestamp | evento |)."""
    section = _extract_section(markdown, "Linha do Tempo")
    events: list[dict[str, str]] = []

    for line in section.split("\n"):
        if "|" in line and "---" not in line and "timestamp" not in line.lower():
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                events.append({"timestamp": parts[0], "event": parts[1]})

    return events
