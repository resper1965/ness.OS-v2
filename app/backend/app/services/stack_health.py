from __future__ import annotations

from collections import Counter
from typing import Any

STATE_ORDER = {"down": 3, "degraded": 2, "ok": 1, "planned": 0, "unavailable": 0}


def _worst_status(values: list[str]) -> str:
    if not values:
        return "unavailable"
    return max(values, key=lambda value: STATE_ORDER.get(value, -1))


def _normalize_pipeline_state(status: str) -> str:
    if status == "ok":
        return "ok"
    if status == "degraded":
        return "degraded"
    return "down"


def _stack_domains(domains: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sources = domains.get("sources", {})
    contabo = domains.get("contabo", {}).get("stacks", {})
    pipeline = domains.get("pipeline", {})

    pipeline_status = _normalize_pipeline_state(str(pipeline.get("status", "error")))
    pipeline_error = pipeline.get("detail") or pipeline.get("error")

    return {
        "aiops": {
            "contabo": contabo.get("aiops", {"status": "down", "error_code": "missing"}),
            "pipeline": {
                "status": pipeline_status,
                "error_code": pipeline_error,
            },
            "glpi": sources.get("glpi", {"status": "unavailable"}),
        },
        "zabbix-prod": {
            "contabo": contabo.get(
                "zabbix-prod", {"status": "down", "error_code": "missing"}
            ),
            "zabbix": sources.get("zabbix", {"status": "unavailable"}),
        },
        "zabbix-prd-01": {
            "contabo": contabo.get(
                "zabbix-prd-01", {"status": "down", "error_code": "missing"}
            ),
        },
    }


def _build_findings(stacks: list[dict[str, Any]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for stack in stacks:
        if stack["status"] == "ok":
            continue
        contabo = stack["domains"].get("contabo", {})
        if contabo.get("status") == "ok" and stack["status"] != "ok":
            findings.append(
                {
                    "stack": stack["name"],
                    "code": "runtime_issue_with_provider_running",
                    "message": "VPS em running no provedor com domínio crítico degradado/down.",
                }
            )
            continue
        findings.append(
            {
                "stack": stack["name"],
                "code": "stack_degraded",
                "message": "Stack com domínio crítico indisponível ou desatualizado.",
            }
        )
    return findings


def build_stack_health_report(domains: dict[str, Any]) -> dict[str, Any]:
    grouped_domains = _stack_domains(domains)
    stacks: list[dict[str, Any]] = []
    for stack_name, stack_domains in grouped_domains.items():
        statuses = [str(domain.get("status", "unavailable")) for domain in stack_domains.values()]
        status = _worst_status(statuses)
        stacks.append(
            {
                "name": stack_name,
                "status": status,
                "domains": stack_domains,
                "cause": next(
                    (
                        str(domain.get("error_code"))
                        for domain in stack_domains.values()
                        if domain.get("error_code")
                    ),
                    None,
                ),
            }
        )

    counters = Counter(stack["status"] for stack in stacks)
    findings = _build_findings(stacks)
    return {
        "summary": {
            "total": len(stacks),
            "ok": counters.get("ok", 0),
            "degraded": counters.get("degraded", 0),
            "down": counters.get("down", 0),
        },
        "stacks": stacks,
        "domains": domains,
        "findings": findings,
    }
