# -------------------------------------------------------
# NessOps — Detecção de Anomalias (Z-Score Robusto)
# -------------------------------------------------------
"""
Z-Score Robusto usando Mediana + MAD (Median Absolute Deviation).

O Z-Score gaussiano clássico falha com métricas de infraestrutura
porque CPU, I/O e latência são distribuições assimétricas (skewed).
A Mediana e o MAD são resistentes a outliers por definição.

Fórmula:
    Z_robusto = (X - mediana) / (MAD × 1.4826)

O fator 1.4826 é a constante de consistência que torna o MAD
um estimador não-enviesado do desvio padrão para distribuições
normais (1 / Φ⁻¹(3/4) ≈ 1.4826).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

# Constante de consistência para distribuição normal
_CONSISTENCY_CONSTANT: Final[float] = 1.4826


@dataclass(frozen=True, slots=True)
class RobustZScoreResult:
    """Resultado do cálculo de Z-Score Robusto."""

    z_scores: NDArray[np.float64]
    median: float
    mad: float
    mad_scaled: float  # MAD × 1.4826


def robust_zscore(data: NDArray[np.float64]) -> RobustZScoreResult:
    """Calcula Z-Score Robusto para um array de métricas.

    Args:
        data: Array 1D de valores numéricos (ex: CPU % nos últimos 7 dias).

    Returns:
        RobustZScoreResult com z_scores, mediana e MAD.

    Raises:
        ValueError: Se data tiver menos de 2 elementos.
    """
    if len(data) < 2:
        raise ValueError(f"Mínimo 2 datapoints, recebeu {len(data)}")

    median: float = float(np.median(data))
    mad: float = float(np.median(np.abs(data - median)))
    mad_scaled: float = mad * _CONSISTENCY_CONSTANT

    if mad_scaled < 1e-10:
        # MAD = 0 → todos os valores são (quase) iguais → sem anomalia
        z_scores = np.zeros_like(data, dtype=np.float64)
    else:
        z_scores = (data - median) / mad_scaled

    return RobustZScoreResult(
        z_scores=z_scores,
        median=median,
        mad=mad,
        mad_scaled=mad_scaled,
    )


def detect_anomalies(
    data: NDArray[np.float64],
    threshold: float = 3.0,
) -> tuple[NDArray[np.bool_], RobustZScoreResult]:
    """Detecta anomalias usando Z-Score Robusto.

    Args:
        data: Array de valores de uma métrica.
        threshold: Limiar de Z-Score (padrão 3.0 = 99.7%).

    Returns:
        Tupla (mask_booleana_anomalias, resultado_zscore).
    """
    result = robust_zscore(data)
    anomalies = np.abs(result.z_scores) > threshold
    return anomalies, result


def detect_single(
    current_value: float,
    historical_data: NDArray[np.float64],
    threshold: float = 3.0,
) -> tuple[bool, float, RobustZScoreResult]:
    """Verifica se um ÚNICO valor atual é anômalo contra o histórico.

    Caso de uso: um novo datapoint chega do Zabbix, comparamos
    contra os últimos N valores da mesma métrica.

    Args:
        current_value: Valor atual da métrica.
        historical_data: Array com histórico (sem o valor atual).
        threshold: Limiar de Z-Score.

    Returns:
        Tupla (is_anomaly, z_score_do_valor_atual, resultado_completo).
    """
    full_data = np.append(historical_data, current_value)
    result = robust_zscore(full_data)
    z_current = float(result.z_scores[-1])
    is_anomaly = abs(z_current) > threshold
    return is_anomaly, z_current, result
