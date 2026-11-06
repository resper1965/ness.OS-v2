"""cmdb_sync: uma sessão de leitura para o loop de hosts; falha de banco recusa."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from app.integrations import cmdb_sync

HOSTS = [
    {"hostid": "1", "host": "a", "name": "a", "hostgroups": [{"name": "[ Cavan ]"}]},
    {"hostid": "2", "host": "b", "name": "b", "hostgroups": [{"name": "[ TBE ]"}]},
]


def _patch(monkeypatch, session_factory):
    zabbix = MagicMock()
    zabbix._call = AsyncMock(return_value=HOSTS)
    glpi = MagicMock()
    glpi.change_active_entity = AsyncMock()
    glpi.list_items = AsyncMock(return_value=[])
    glpi.kill_session = AsyncMock()
    monkeypatch.setattr(cmdb_sync, "ZabbixClient", lambda: zabbix)
    monkeypatch.setattr(cmdb_sync, "GLPIClient", lambda: glpi)
    monkeypatch.setattr(cmdb_sync, "SessionLocal", session_factory)


@pytest.mark.asyncio
async def test_db_failure_during_resolution_refuses(monkeypatch):
    class Broken:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def execute(self, *_a, **_k):
            raise OperationalError("select", {}, Exception("db down"))

    _patch(monkeypatch, Broken)
    with pytest.raises(OperationalError):
        await cmdb_sync.reconcile()


@pytest.mark.asyncio
async def test_one_session_for_all_hosts(customers_maker, monkeypatch):
    opened = []

    def factory():
        opened.append(1)
        return customers_maker()

    _patch(monkeypatch, factory)
    result = await cmdb_sync.reconcile()
    assert len(opened) == 1
    assert {g["reason"] for g in result["gaps"]} == {"missing_glpi"}
    assert {g["entity"] for g in result["gaps"]} == {8, 2}
