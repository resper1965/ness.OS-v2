# -------------------------------------------------------
# NessOps — Integração MISP Threat Intelligence Platform
# -------------------------------------------------------
"""
Cliente assíncrono para consulta de Indicadores de Comprometimento (IOCs) no servidor MISP.
Permite pesquisar IPs, domínios, URLs e hashes (MD5/SHA256) na base de inteligência de ameaças.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_TIMEOUT = httpx.Timeout(5.0)


async def search_misp_ioc(value: str) -> dict[str, Any]:
    """Consulta um IOC (IP, hash, domínio) na REST API do MISP externo.

    Args:
        value: O indicador a pesquisar (ex: "185.220.101.5" ou "d41d8cd98f00b204e9800998ecf8427e").

    Returns:
        Dict com resultado da busca no MISP (encontrado, total de eventos, tags e detalhes).
    """
    result: dict[str, Any] = {
        "query_value": value,
        "found": False,
        "match_count": 0,
        "events": [],
    }

    misp_url = getattr(settings, "misp_url", "").rstrip("/")
    misp_key = getattr(settings, "misp_api_key", "")
    verify_cert = getattr(settings, "misp_verify_cert", False)

    if not misp_url or not misp_key:
        logger.debug("MISP não consultado (URL ou API Key não configurados).")
        return result

    search_endpoint = f"{misp_url}/attributes/restSearch"
    headers = {
        "Authorization": misp_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "returnFormat": "json",
        "value": value,
        "limit": 10,
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, verify=verify_cert) as client:
            resp = await client.post(search_endpoint, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                response_data = data.get("response", {})
                attributes = response_data.get("Attribute", [])

                if attributes:
                    result["found"] = True
                    result["match_count"] = len(attributes)

                    events_map: dict[str, dict[str, Any]] = {}
                    for attr in attributes:
                        event_id = str(attr.get("event_id", "unknown"))
                        if event_id not in events_map:
                            event_info = attr.get("Event", {})
                            tags = [
                                t.get("name")
                                for t in attr.get("Tag", []) + event_info.get("Tag", [])
                                if isinstance(t, dict) and t.get("name")
                            ]
                            events_map[event_id] = {
                                "event_id": event_id,
                                "info": event_info.get("info", attr.get("comment", "")),
                                "threat_level_id": event_info.get(
                                    "threat_level_id", "0"
                                ),
                                "date": event_info.get("date", ""),
                                "tags": list(set(tags)),
                            }

                    result["events"] = list(events_map.values())
                    logger.info(
                        "IOC '%s' encontrado no MISP em %d evento(s).",
                        value,
                        len(events_map),
                    )
            else:
                logger.warning(
                    "MISP retornou status HTTP %d para IOC '%s'",
                    resp.status_code,
                    value,
                )
    except Exception as e:
        logger.error("Erro ao consultar MISP para o IOC '%s': %s", value, e)

    return result
