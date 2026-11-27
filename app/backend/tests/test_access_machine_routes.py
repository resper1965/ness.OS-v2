"""Rotas autenticadas por X-Api-Key (máquina) não podem ficar atrás do Access."""

from app.core.cf_access_middleware import PUBLIC_PREFIXES
from app.main import app

MACHINE_PATHS = ("/webhook/zabbix", "/v1/alerts", "/api/secops/ingest/wazuh")


def test_machine_routes_exist_and_bypass_access():
    paths = {getattr(r, "path", "") for r in app.routes}
    for p in MACHINE_PATHS:
        assert any(x.startswith(p.rsplit("/", 1)[0]) for x in paths), p
        assert p.startswith(PUBLIC_PREFIXES), p
