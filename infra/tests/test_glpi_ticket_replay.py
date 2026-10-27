from types import SimpleNamespace

from infra.scripts.glpi_ticket_replay import replay


class Payload:
    def __init__(self, **kw):
        self.kw = kw

    def model_dump(self, mode):
        return self.kw


def row(id, fp):
    return SimpleNamespace(
        id=id,
        fingerprint=fp,
        host_id="h",
        host_name="srv",
        trigger_id="t",
        title=f"t{id}",
        severity=3,
        tags={"ninf_zabbix_event_id": "9", "env": "prod"},
    )


def test_dry_run_does_not_enqueue_and_fingerprint_mismatch_is_skipped():
    sent = []
    rows = [row(1, "ok"), row(2, "stale")]
    fp = lambda p: "ok"
    assert replay(rows, Payload, fp, lambda *a: sent.append(a), False) == [
        (1, "t1", False)
    ]
    assert sent == []
    assert replay(rows, Payload, fp, lambda *a: sent.append(a), True) == [
        (1, "t1", True)
    ]
    payload, fingerprint = sent[0]
    assert (
        fingerprint == "ok"
        and payload["event_id"] == "9"
        and payload["tags"] == {"env": "prod"}
    )
