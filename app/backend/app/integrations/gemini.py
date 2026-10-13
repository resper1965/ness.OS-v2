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
from app.models.schemas import PostMortemReport

logger = logging.getLogger(__name__)
settings = get_settings()

_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=5.0)

# Prompt estruturado para o Gemini
_POSTMORTEM_SYSTEM_PROMPT = """\
Você é um engenheiro SRE sênior da ness. gerando um relatório pós-incidente.
Analise os dados do incidente e produza um relatório DENSO em Markdown com:

## Estrutura obrigatória:
1. **Resumo Executivo** — 2-3 frases sobre o que aconteceu
2. **Linha do Tempo** — Tabela cronológica dos eventos (timestamp | evento)
3. **Causa Raiz** — Análise técnica detalhada
4. **Blast Radius** — Serviços e hosts afetados
5. **Logs Relevantes** — Trechos de log que sustentam a conclusão
6. **Ações Corretivas** — O que deve ser feito para evitar recorrência
7. **Métricas Analisadas** — Dados numéricos que apoiam a análise

## Regras:
- Seja objetivo e técnico.
- NÃO invente dados. Se não houver informação suficiente, diga explicitamente.
- Todos os IPs e credenciais já foram sanitizados. Use [IP_REDACTED] onde necessário.
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
        f"```json\n{json.dumps(incident, indent=2, ensure_ascii=False)}\n```",
        "",
        "# Métricas Recentes (últimas 24h)",
        f"```json\n{json.dumps(metrics[:50], indent=2, ensure_ascii=False)}\n```",
        "",
        "# Logs Relacionados",
    ]

    for log_entry in related_logs[:100]:  # Cap para não estourar contexto
        context_parts.append(f"- {log_entry}")

    if similar_incidents:
        context_parts.append("")
        context_parts.append("# Incidentes Similares Anteriores")
        for si in similar_incidents[:5]:
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
                params={"key": settings.gemini_api_key},
                headers={"Content-Type": "application/json"},
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
            markdown_report=markdown,
            summary=_extract_section(markdown, "Resumo Executivo"),
            root_cause=_extract_section(markdown, "Causa Raiz"),
            blast_radius=_extract_list_section(markdown, "Blast Radius"),
            corrective_actions=_extract_list_section(markdown, "Ações Corretivas"),
            timeline=_extract_timeline(markdown),
            gemini_model_used=settings.gemini_model,
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
        )

    except httpx.HTTPError as exc:
        logger.error("Falha na chamada ao Gemini: %s", exc)
        # Fallback: relatório mínimo sem IA
        return PostMortemReport(
            incident_fingerprint=incident.get("fingerprint", ""),
            markdown_report=(
                "# Relatório Pós-Incidente\n\n"
                "> ⚠️ Geração automática falhou. Análise manual necessária.\n\n"
                f"**Incidente:** {incident.get('title', '?')}\n"
                f"**Host:** {incident.get('host_name', '?')}\n"
                f"**Erro Gemini:** {exc}\n"
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
