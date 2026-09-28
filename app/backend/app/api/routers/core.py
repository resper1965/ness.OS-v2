"""
ness.OS — Router: Core
Visão global consolidada: métricas unificadas de todos os módulos,
mapa de saúde da carteira, KPIs operacionais, resumo executivo.

Endpoints:
  GET /api/core/overview      — resumo executivo (CEO/Manager view)
  GET /api/core/health-map    — status por cliente (grid de tiles)
  GET /api/core/kpis          — indicadores operacionais
  GET /api/core/modules       — status de cada módulo (infraops/secops)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.core.dependencies import require_authenticated, require_noc
from app.integrations.atera import AteraClient
from app.integrations.zabbix import ZabbixClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/core", tags=["core"])

_TIMEOUT = 8.0


async def _safe(coro, name: str) -> Any | None:
    """Executa corrotina com timeout sem converter falha em dado válido."""
    try:
        return await asyncio.wait_for(coro, timeout=_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("core: %s timeout após %.0fs", name, _TIMEOUT)
        return None
    except Exception as exc:
        logger.error("core: %s failed: %s", name, type(exc).__name__)
        return None


# ── Helpers de coleta ────────────────────────────────────────────────────────


async def _infra_summary() -> dict:
    """Resumo n.infraops: Zabbix + Atera."""
    settings = get_settings()
    zabbix = ZabbixClient()

    async def _zabbix():
        hosts = await zabbix._call(
            "host.get", {"output": ["hostid"], "filter": {"status": 0}}
        )
        problems = await zabbix._call(
            "problem.get",
            {
                "output": ["eventid", "severity"],
                "recent": True,
                "suppressed": False,
            },
        )
        critical = [p for p in (problems or []) if int(p.get("severity", 0)) >= 4]
        return {
            "hosts_active": len(hosts or []),
            "alerts_total": len(problems or []),
            "alerts_critical": len(critical),
        }

    async def _atera():
        client = AteraClient(api_key=settings.atera_api_key)
        summary = await client.get_dashboard_summary()
        if summary.get("degraded"):
            raise RuntimeError("Atera summary unavailable")
        return {
            "agents": summary.get("agents_total"),
            "alerts": summary.get("alerts_total"),
        }

    zabbix_data, atera_data = await asyncio.gather(
        _safe(_zabbix(), "zabbix"),
        _safe(_atera(), "atera") if settings.atera_api_key else asyncio.sleep(0),
    )
    zabbix_status = "ok" if zabbix_data is not None else "unavailable"
    atera_status = (
        "ok" if atera_data is not None and settings.atera_api_key else "unavailable"
    )
    zabbix_values = zabbix_data or {}
    atera_values = atera_data or {}

    return {
        "hosts_active": zabbix_values.get("hosts_active"),
        "agents_rmm": atera_values.get("agents"),
        "alerts_critical": zabbix_values.get("alerts_critical"),
        "alerts_total": zabbix_values.get("alerts_total"),
        "rmm_alerts": atera_values.get("alerts"),
        "status": "ok" if zabbix_status == atera_status == "ok" else "degraded",
        "sources": {
            "zabbix": {"status": zabbix_status},
            "atera": {
                "status": atera_status,
                "error_code": None if settings.atera_api_key else "not_configured",
            },
        },
    }


async def _secops_summary() -> dict:
    """Reserva o módulo SecOps até a integração Wazuh aprovada."""
    return {
        "incidents_open": None,
        "incidents_critical": None,
        "agents_online": None,
        "status": "unavailable",
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "/overview",
    summary="Resumo executivo unificado — ness.OS Core",
    dependencies=[Depends(require_noc)],
)
async def get_overview() -> dict:
    """
    Visão global consolidada de todos os módulos.
    Projetada para o painel principal do ness.OS (CEO/Manager/NOC).

    Coleta em paralelo: n.infraops (Zabbix + Atera) + estado do n.secops.
    Cada fonte tem timeout de 8s e degrada independentemente.
    """
    infra, secops = await asyncio.gather(
        _safe(_infra_summary(), "infra"),
        _safe(_secops_summary(), "secops"),
    )
    infra = infra or {"status": "unavailable"}
    secops = secops or {"status": "unavailable"}

    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "platform": "ness.OS",
        "version": "1.0.0",
        # Não publicar falsa precisão: o score depende do catálogo de serviços,
        # pesos, SLA e qualidade de dados ainda em homologação (ADR 0011).
        "health_score": None,
        "health_score_status": "provisional",
        "health_score_reason": "formula e fontes ainda nao homologadas",
        "modules": {
            "infraops": {
                "label": "n.infraops",
                "color": "#3B82F6",
                "status": infra.get("status", "unknown"),
                "metrics": {
                    "hosts_active": infra.get("hosts_active"),
                    "agents_rmm": infra.get("agents_rmm"),
                    "alerts_critical": infra.get("alerts_critical"),
                    "alerts_total": infra.get("alerts_total"),
                },
            },
            "secops": {
                "label": "n.secops",
                "color": "#EF4444",
                "status": secops.get("status", "unknown"),
                "metrics": {
                    "incidents_open": secops.get("incidents_open"),
                    "incidents_critical": secops.get("incidents_critical"),
                    "agents_online": secops.get("agents_online"),
                },
            },
        },
    }


@router.get(
    "/modules",
    summary="Status de cada módulo ness.OS",
    dependencies=[Depends(require_authenticated)],
)
async def get_modules_status() -> dict:
    """
    Status operacional de cada módulo: configurado, degradado ou ativo.
    Usado pelo module switcher do frontend para exibir badges de status.
    """
    settings = get_settings()
    return {
        "modules": [
            {
                "id": "infraops",
                "label": "n.infraops",
                "description": "Operação de Infraestrutura e NOC",
                "color": "#3B82F6",
                "icon": "server",
                "configured": bool(
                    settings.zabbix_api_token and settings.atera_api_key
                ),
                "route": "/infraops",
            },
            {
                "id": "secops",
                "label": "n.secops",
                "description": "Operação de Segurança e SOC",
                "color": "#EF4444",
                "icon": "shield",
                "configured": False,
                "route": "/secops",
            },
            {
                "id": "core",
                "label": "ness.OS",
                "description": "Visão Global e Gestão",
                "color": "#6366F1",
                "icon": "globe",
                "configured": True,
                "route": "/",
            },
        ]
    }


@router.get(
    "/kpis",
    summary="KPIs operacionais da ness.",
    dependencies=[Depends(require_noc)],
)
async def get_kpis() -> dict:
    """
    Indicadores operacionais consolidados para o dashboard do manager/admin.
    Inclui métricas de infraestrutura e segurança unificadas.
    """
    infra, secops = await asyncio.gather(
        _safe(_infra_summary(), "infra-kpi"),
        _safe(_secops_summary(), "secops-kpi"),
    )
    infra = infra or {"status": "unavailable", "sources": {}}
    secops = secops or {"status": "unavailable"}
    sources = infra.get("sources", {})
    zabbix_status = sources.get("zabbix", {}).get("status", "unavailable")
    atera_status = sources.get("atera", {}).get("status", "unavailable")
    zabbix_critical = infra.get("alerts_critical")
    secops_critical = secops.get("incidents_critical")

    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "kpis": [
            {
                "id": "zabbix_hosts_active",
                "label": "Hosts ativos no Zabbix",
                "value": infra.get("hosts_active"),
                "unit": "hosts",
                "module": "infraops",
                "color": "#3B82F6",
                "trend": "stable",
                "source": "zabbix",
                "status": zabbix_status,
            },
            {
                "id": "rmm_agents_reported",
                "label": "Agentes reportados pelo RMM",
                "value": infra.get("agents_rmm"),
                "unit": "agentes",
                "module": "infraops",
                "color": "#06B6D4",
                "trend": "stable",
                "source": "atera",
                "status": atera_status,
            },
            {
                "id": "zabbix_alerts_critical",
                "label": "Alertas críticos no Zabbix",
                "value": infra.get("alerts_critical"),
                "unit": "alertas ativos",
                "module": "infraops",
                "color": "#F59E0B",
                "trend": "stable",
                "alert": zabbix_critical > 5 if zabbix_critical is not None else None,
                "source": "zabbix",
                "status": zabbix_status,
            },
            {
                "id": "secops_incidents_open",
                "label": "Incidentes de segurança abertos",
                "value": secops.get("incidents_open"),
                "unit": "incidentes",
                "module": "secops",
                "color": "#EF4444",
                "trend": "stable",
                "alert": secops_critical > 0 if secops_critical is not None else None,
                "source": "wazuh",
                "status": secops.get("status", "unavailable"),
            },
        ],
    }
