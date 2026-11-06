"""hub-glpi-integrity-check: a entidade esperada vem do cadastro (resolvedor async)."""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "hub-glpi-integrity-check.py"

def load():
    spec = importlib.util.spec_from_file_location("integrity_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class FakeSession:
    def __init__(self, incidents, assets):
        self.batches = [incidents, assets]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def scalars(self, _stmt):
        return SimpleNamespace(all=lambda: self.batches.pop(0))

def run(monkeypatch, tmp_path, capsys, entity, resolver):
    module = load()
    incident = SimpleNamespace(
        id=1,
        fingerprint="fp",
        deskmanager_ticket_id="77",
        asset_id=None,
        host_id="10978",
        tags={"ninf_customer_name": "Cavan"},
    )
    snapshot = tmp_path / "snapshot.json"
    ticket = {
        "id": 77,
        "fingerprint": "fp",
        "entity": entity,
        "deleted": False,
        "followups": [1],
        "assets": [],
    }
    snapshot.write_text(json.dumps({"tickets": [ticket]}))
    monkeypatch.setattr(sys, "argv", ["x", str(snapshot)])
    monkeypatch.setattr(module, "SessionLocal", lambda: FakeSession([incident], []))
    monkeypatch.setattr(module, "resolve_glpi_entity_id", resolver)
    asyncio.run(module.main())
    return json.loads(capsys.readouterr().out)["findings"]

async def resolve_cavan(_session, name):
    assert name == "Cavan"
    return 8

def test_matching_entity_has_no_mismatch(monkeypatch, tmp_path, capsys):
    assert run(monkeypatch, tmp_path, capsys, 8, resolve_cavan) == []

def test_different_entity_is_mismatch(monkeypatch, tmp_path, capsys):
    findings = run(monkeypatch, tmp_path, capsys, 9, resolve_cavan)
    assert [f["reason"] for f in findings] == ["entity_mismatch"]

def test_unmapped_customer_is_mismatch(monkeypatch, tmp_path, capsys):
    async def refuse(_session, _name):
        raise ValueError("Cliente sem entidade GLPI mapeada; ticket recusado")

    findings = run(monkeypatch, tmp_path, capsys, 0, refuse)
    assert [f["reason"] for f in findings] == ["entity_mismatch"]
