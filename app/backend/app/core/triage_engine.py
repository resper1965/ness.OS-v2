# -------------------------------------------------------
# NessOps — Camada 4: Triage Worker sem LLM (Risk Engine 0-100)
# -------------------------------------------------------
"""
Motor de triagem determinística de eventos e alertas.
Calcula a pontuação de risco (0-100) antes de qualquer chamada a modelos de linguagem (LLM).

Regras de Decisão:
- Risco < 75  -> ARCHIVE (Agrega e arquiva silenciosamente, bypass total de LLM).
- Risco 75-84 -> TRIAGE_L1 (Encaminha para análise rápida/modelo pequeno).
- Risco >= 85 -> TRIAGE_L2 (Encaminha para análise profunda/modelo principal e alerta prioritário).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TriageAction(str, Enum):
    ARCHIVE = "ARCHIVE"
    TRIAGE_L1 = "TRIAGE_L1"
    TRIAGE_L2 = "TRIAGE_L2"


@dataclass
class TriageResult:
    risk_score: int
    action: TriageAction
    reasons: list[str]
    llm_bypassed: bool
    fingerprint: str
    frequency_count: int


# Tabela de palavras-chave para ativos críticos e pesos adicionais
CRITICAL_ASSET_KEYWORDS: dict[str, int] = {
    "dc": 25,
    "domain-controller": 25,
    "ad": 25,
    "db": 20,
    "database": 20,
    "prod": 15,
    "k8s": 15,
    "firewall": 20,
    "fortinet": 20,
    "gateway": 15,
}

# Armazenamento em memória para deduplicação/frequência temporal (fallback quando Redis indisponível)
_IN_MEMORY_FREQUENCY: dict[str, list[float]] = {}
_WINDOW_SECONDS = 300  # Janela de 5 minutos


def _get_frequency_count(fingerprint: str, now: float) -> int:
    """Calcula a frequência do fingerprint nos últimos N segundos."""
    if fingerprint not in _IN_MEMORY_FREQUENCY:
        _IN_MEMORY_FREQUENCY[fingerprint] = []

    timestamps = _IN_MEMORY_FREQUENCY[fingerprint]
    # Filtra apenas timestamps dentro da janela
    valid_timestamps = [t for t in timestamps if now - t <= _WINDOW_SECONDS]
    valid_timestamps.append(now)
    _IN_MEMORY_FREQUENCY[fingerprint] = valid_timestamps
    return len(valid_timestamps)


class TriageEngine:
    """Motor de triagem determinístico sem LLM (Camada 4)."""

    def __init__(self, risk_threshold_l1: int = 75, risk_threshold_l2: int = 85):
        self.threshold_l1 = risk_threshold_l1
        self.threshold_l2 = risk_threshold_l2

    def evaluate_alert(
        self,
        alert_data: dict[str, Any],
        threat_intel: dict[str, Any] | None = None,
        fingerprint: str = "default_fp",
    ) -> TriageResult:
        """Calcula o score de risco (0-100) multifatorial.

        Fatores considerados:
        1. Wazuh Level / Severidade Zabbix
        2. Criticidade do Ativo (Host)
        3. Frequência / Recorrência Temporal
        4. Reputação de Threat Intel (AbuseIPDB / VirusTotal)
        """
        reasons: list[str] = []
        score = 0
        now = time.time()

        # 1. Wazuh Level (0 a 15) -> Base score (até 60 pontos)
        wazuh_level = int(alert_data.get("level", alert_data.get("rule_level", 0)))
        if wazuh_level > 0:
            level_score = min(60, wazuh_level * 4)
            score += level_score
            reasons.append(f"Wazuh Level {wazuh_level} (+{level_score} pts)")

        # Fallback para severidade genérica/Zabbix se level não informado
        if wazuh_level == 0:
            severity = str(alert_data.get("severity", "")).lower()
            if severity in ("critical", "high", "disaster"):
                score += 50
                reasons.append("Severidade do alerta ALTA (+50 pts)")
            elif severity in ("warning", "average", "medium"):
                score += 30
                reasons.append("Severidade do alerta MÉDIA (+30 pts)")
            elif severity in ("information", "low"):
                score += 10
                reasons.append("Severidade do alerta BAIXA (+10 pts)")

        # 2. Criticidade do Ativo
        hostname = str(alert_data.get("host", alert_data.get("hostname", ""))).lower()
        asset_score = 0
        for keyword, weight in CRITICAL_ASSET_KEYWORDS.items():
            if keyword in hostname:
                asset_score = max(asset_score, weight)
        if asset_score > 0:
            score += asset_score
            reasons.append(f"Ativo Crítico detectado ({hostname}) (+{asset_score} pts)")

        # 3. Frequência / Recorrência Temporal
        freq_count = _get_frequency_count(fingerprint, now)
        if freq_count > 1:
            freq_score = min(25, (freq_count - 1) * 5)
            score += freq_score
            reasons.append(
                f"Recorrência temporal ({freq_count}x em 5m) (+{freq_score} pts)"
            )

        # 4. Threat Intel (AbuseIPDB / VirusTotal / MISP)
        if threat_intel:
            abuse_score = 0
            vt_malicious = 0
            misp_found = False
            misp_matches = 0

            if threat_intel.get("abuseipdb"):
                abuse_score = threat_intel["abuseipdb"].get("abuse_score", 0)
            if threat_intel.get("virustotal"):
                vt_malicious = threat_intel["virustotal"].get("malicious", 0)
            if threat_intel.get("misp"):
                misp_found = threat_intel["misp"].get("found", False)
                misp_matches = threat_intel["misp"].get("match_count", 0)

            intel_score = 0
            if abuse_score >= 50 or vt_malicious >= 2:
                intel_score += 25
                reasons.append(
                    f"Threat Intel Publico Malicioso (AbuseIPDB: {abuse_score}%, VT: {vt_malicious}) (+25 pts)"
                )
            if misp_found and misp_matches > 0:
                intel_score += 25
                reasons.append(
                    f"MISP Threat Intel IOC Confirmado ({misp_matches} evento(s) MISP) (+25 pts)"
                )
            score += intel_score

        # Garantir limite de 0 a 100
        final_score = max(0, min(100, score))

        # Determinar Ação
        if final_score < self.threshold_l1:
            action = TriageAction.ARCHIVE
            llm_bypassed = True
        elif final_score < self.threshold_l2:
            action = TriageAction.TRIAGE_L1
            llm_bypassed = False
        else:
            action = TriageAction.TRIAGE_L2
            llm_bypassed = False

        logger.info(
            "Triage Engine avaliou alerta FP [%s]: Score=%d, Action=%s, Bypassed=%s",
            fingerprint,
            final_score,
            action.value,
            llm_bypassed,
        )

        return TriageResult(
            risk_score=final_score,
            action=action,
            reasons=reasons,
            llm_bypassed=llm_bypassed,
            fingerprint=fingerprint,
            frequency_count=freq_count,
        )
