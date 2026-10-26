# -------------------------------------------------------
# n.infraops — Testes unitários do Fingerprint
# -------------------------------------------------------
from datetime import datetime
from app.core.fingerprint import generate_fingerprint
from app.models.schemas import ZabbixAlertPayload, ZabbixSeverity


def test_generate_fingerprint_deterministic():
    payload1 = ZabbixAlertPayload(
        event_id="1001",
        host_id="10001",
        host_name="web-server-01",
        host_ip="192.168.1.10",
        trigger_id="20002",
        trigger_name="CPU usage is high",
        severity=ZabbixSeverity.HIGH,
        timestamp=datetime.utcnow(),
    )

    # Outro payload com timestamp e event_id diferentes, mas mesmo host_id e trigger_id
    payload2 = ZabbixAlertPayload(
        event_id="1002",
        host_id="10001",
        host_name="web-server-01",
        host_ip="192.168.1.10",
        trigger_id="20002",
        trigger_name="CPU usage is high",
        severity=ZabbixSeverity.HIGH,
        timestamp=datetime.utcnow(),
    )

    fp1 = generate_fingerprint(payload1)
    fp2 = generate_fingerprint(payload2)

    # Devem ser iguais (mesmo host + trigger)
    assert fp1 == fp2
    assert len(fp1) == 64  # Hash SHA-256 tem 64 caracteres hex
