import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_TIMEOUT = httpx.Timeout(5.0)


async def enrich_ip(ip_address: str) -> dict[str, Any]:
    """Consulta reputação e inteligência de ameaças para um endereço IP."""
    from app.integrations.misp import search_misp_ioc

    result: dict[str, Any] = {
        "ip": ip_address,
        "abuseipdb": None,
        "virustotal": None,
        "misp": None,
    }

    # 1. Consulta AbuseIPDB
    key_abuse = getattr(settings, "abuseipdb_api_key", None)
    if key_abuse:
        try:
            url = "https://api.abuseipdb.com/api/v2/check"
            headers = {"Key": key_abuse, "Accept": "application/json"}
            params: dict[str, str | int] = {
                "ipAddress": ip_address,
                "maxAgeInDays": 90,
            }
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    result["abuseipdb"] = {
                        "abuse_score": data.get("abuseConfidenceScore", 0),
                        "country_code": data.get("countryCode"),
                        "domain": data.get("domain"),
                        "usage_type": data.get("usageType"),
                        "is_tor": data.get("isTor", False),
                    }
                else:
                    logger.warning(
                        "AbuseIPDB retornou status %d para o IP %s",
                        resp.status_code,
                        ip_address,
                    )
        except Exception as e:
            logger.error("Erro ao consultar AbuseIPDB para o IP %s: %s", ip_address, e)

    # 2. Consulta VirusTotal IP
    key_vt = getattr(settings, "virustotal_api_key", None)
    if key_vt:
        try:
            url = f"https://www.virustotal.com/api/v3/ip_addresses/{ip_address}"
            headers = {"x-apikey": key_vt}
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    stats = data.get("attributes", {}).get("last_analysis_stats", {})
                    result["virustotal"] = {
                        "malicious": stats.get("malicious", 0),
                        "suspicious": stats.get("suspicious", 0),
                        "harmless": stats.get("harmless", 0),
                        "undetected": stats.get("undetected", 0),
                    }
                else:
                    logger.warning(
                        "VirusTotal retornou status %d para o IP %s",
                        resp.status_code,
                        ip_address,
                    )
        except Exception as e:
            logger.error("Erro ao consultar VirusTotal para o IP %s: %s", ip_address, e)

    # 3. Consulta MISP Threat Intel
    misp_res = await search_misp_ioc(ip_address)
    if misp_res["found"]:
        result["misp"] = misp_res

    return result


async def enrich_hash(file_hash: str) -> dict[str, Any]:
    """Consulta inteligência de ameaças para um hash de arquivo (MD5/SHA256)."""
    from app.integrations.misp import search_misp_ioc

    result: dict[str, Any] = {
        "hash": file_hash,
        "virustotal": None,
        "misp": None,
    }

    key_vt = getattr(settings, "virustotal_api_key", None)
    if key_vt:
        try:
            url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
            headers = {"x-apikey": key_vt}
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    stats = data.get("attributes", {}).get("last_analysis_stats", {})
                    result["virustotal"] = {
                        "malicious": stats.get("malicious", 0),
                        "suspicious": stats.get("suspicious", 0),
                        "harmless": stats.get("harmless", 0),
                        "undetected": stats.get("undetected", 0),
                    }
                else:
                    logger.warning(
                        "VirusTotal retornou status %d para o hash %s",
                        resp.status_code,
                        file_hash,
                    )
        except Exception as e:
            logger.error(
                "Erro ao consultar VirusTotal para o hash %s: %s", file_hash, e
            )

    # Consulta MISP Threat Intel
    misp_res = await search_misp_ioc(file_hash)
    if misp_res["found"]:
        result["misp"] = misp_res

    return result
