"""Rotas autenticadas por X-Api-Key (máquina) não podem ficar atrás do Access."""

from app.core.cf_access_middleware import PUBLIC_PREFIXES
from app.main import app

MACHINE_PATHS = ("/webhook/zabbix", "/v1/alerts", "/api/secops/ingest/wazuh")


def test_machine_routes_exist_and_bypass_access():
    registered = {getattr(r, "path", "") for r in app.routes}
    for p in MACHINE_PATHS:
        assert p in registered, p
        assert p.startswith(PUBLIC_PREFIXES), p
