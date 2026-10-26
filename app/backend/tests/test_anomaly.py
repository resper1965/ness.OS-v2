# -------------------------------------------------------
# n.infraops — Testes unitários do Anomaly Detection
# -------------------------------------------------------
import numpy as np
import pytest
from app.ml.anomaly import robust_zscore, detect_anomalies, detect_single


def test_robust_zscore_basic():
    # Dados homogêneos: sem anomalias
    data = np.array([10.0, 10.2, 9.8, 10.1, 9.9, 10.0], dtype=np.float64)
    result = robust_zscore(data)

    assert result.median == pytest.approx(10.0)
    # Como todos são próximos de 10, o MAD é muito baixo
    assert result.mad == pytest.approx(0.1)
    # Nenhum valor deve ter um Z-Score alto
    assert np.all(np.abs(result.z_scores) < 2.0)


def test_robust_zscore_with_outlier():
    # Histórico normal em torno de 10, com um outlier gigante de 100 (número ímpar de elementos para mediana exata)
    data = np.array([10.0, 10.2, 9.8, 10.1, 9.9, 10.0, 100.0], dtype=np.float64)
    result = robust_zscore(data)

    # Mediana deve resistir ao outlier
    assert result.median == pytest.approx(10.0)
    assert result.mad == pytest.approx(0.1)

    # O outlier (índice 6) deve ter um Z-Score enorme
    assert result.z_scores[6] > 30.0
    # O resto dos dados deve ter Z-Score normal
    assert np.all(np.abs(result.z_scores[:6]) < 2.0)


def test_detect_anomalies():
    data = np.array([10.0, 10.2, 9.8, 10.1, 9.9, 50.0], dtype=np.float64)
    anomalies, result = detect_anomalies(data, threshold=3.0)

    # Apenas o último elemento (50.0) deve ser marcado como anomalia
    assert not anomalies[0]
    assert not anomalies[1]
    assert not anomalies[2]
    assert not anomalies[3]
    assert not anomalies[4]
    assert anomalies[5]


def test_detect_single():
    historical = np.array([10.0, 10.2, 9.8, 10.1, 9.9], dtype=np.float64)

    # Caso 1: Novo valor dentro da normalidade (10.0)
    is_anomaly, z_score, _ = detect_single(10.0, historical, threshold=3.0)
    assert not is_anomaly
    assert abs(z_score) < 1.0

    # Caso 2: Novo valor anômalo (80.0)
    is_anomaly, z_score, _ = detect_single(80.0, historical, threshold=3.0)
    assert is_anomaly
    assert z_score > 30.0


def test_robust_zscore_zero_mad():
    # Se todos os valores são exatamente iguais, o MAD será 0
    data = np.array([10.0, 10.0, 10.0, 10.0], dtype=np.float64)
    result = robust_zscore(data)

    assert result.mad == 0.0
    assert result.mad_scaled == 0.0
    # Deve retornar Z-Scores de 0 ao invés de lançar erro de divisão por zero
    assert np.all(result.z_scores == 0.0)


def test_robust_zscore_insufficient_data():
    data = np.array([10.0], dtype=np.float64)
    with pytest.raises(ValueError, match="Mínimo 2 datapoints"):
        robust_zscore(data)
