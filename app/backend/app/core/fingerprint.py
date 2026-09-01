# -------------------------------------------------------
# NessOps — Fingerprint SHA-256 determinístico
# -------------------------------------------------------
"""
Gera um hash determinístico a partir dos campos-chave do alerta.
Alertas com mesmo fingerprint pertencem ao mesmo incidente.
"""

from __future__ import annotations

import hashlib

from app.models.schemas import ZabbixAlertPayload


def generate_fingerprint(alert: ZabbixAlertPayload) -> str:
    """SHA-256 do par (host_id, trigger_id).

    Dois alertas do mesmo host e trigger = mesmo incidente.
    O hash é determinístico e independente de ordem/timestamp.
    """
    raw = f"{alert.host_id}:{alert.trigger_id}"
    return hashlib.sha256(raw.encode()).hexdigest()
