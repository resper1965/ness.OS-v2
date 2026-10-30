"""
Router: /api/secops -- n.secops: CVE Intelligence + Zabbix Health + Wazuh SOC
Expoe achados de seguranca, CVEs criticos dos clientes e saude do Zabbix.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import (
    require_authenticated,
    require_noc,
    resolve_tenant_scope,
)
from app.core.triage_engine import TriageAction, TriageEngine
from app.database import get_db
from app.models.models import SocDecision, TenantMapping
from app.models.users import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/secops", tags=["secops"])

# ── CVE Intelligence Database (OSINT 06/07/2026) ────────────────────────────
CVE_DATABASE = [
    {
        "id": "CVE-2024-21762",
        "title": "FortiOS SSL VPN — RCE sem autenticação",
        "severity": "critical",
        "cvss": 9.8,
        "affected_tech": "FortiGate / FortiOS",
        "affected_clients": ["Alupar", "TBE", "TNE", "Target", "LTB", "NumenIT"],
        "exploited_wild": True,
        "patch_available": True,
        "patch_version": "FortiOS ≥ 7.0.17 / 7.2.7 / 7.4.3",
        "description": "Out-of-Bounds Write no SSL VPN permite RCE não autenticado remoto. Exploração ativa confirmada — dispositivos sem patch são considerados comprometidos.",
        "action": "Atualizar FortiOS imediatamente. Auditar logs de acesso VPN SSL.",
        "published": "2024-02-09",
        "references": ["https://fortiguard.com/psirt/FG-IR-24-015"],
    },
    {
        "id": "CVE-2024-55591",
        "title": "FortiOS Auth Bypass via WebSocket → Super Admin",
        "severity": "critical",
        "cvss": 9.6,
        "affected_tech": "FortiGate / FortiProxy",
        "affected_clients": ["Alupar", "TBE", "TNE", "Target", "LTB", "NumenIT"],
        "exploited_wild": True,
        "patch_available": True,
        "patch_version": "FortiOS ≥ 7.0.17 / FortiProxy ≥ 7.0.20",
        "description": "Bypass de autenticação via WebSocket Node.js permite que atacante não autenticado obtenha privilégio super-admin. Exploração ativa em produção.",
        "action": "Patch urgente. Verificar se algum FortiGate tem interface de gestão exposta na Internet.",
        "published": "2025-01-14",
        "references": ["https://fortiguard.com/psirt/FG-IR-24-422"],
    },
    {
        "id": "FortiBleed-2026",
        "title": "FortiBleed — 1.737 IPs brasileiros comprometidos",
        "severity": "critical",
        "cvss": 9.5,
        "affected_tech": "FortiGate SSL VPN",
        "affected_clients": ["Alupar", "TBE", "TNE", "Target", "LTB", "NumenIT"],
        "exploited_wild": True,
        "patch_available": False,
        "patch_version": "Rotação de credenciais VPN + MFA obrigatório",
        "description": "Campanha global: 73.000+ dispositivos Fortinet com credenciais VPN SSL expostas. Brasil ocupa 11ª posição (≈1.737 dispositivos). 309 credenciais BR já comprometidas.",
        "action": "Rotacionar TODAS as credenciais VPN SSL. Habilitar MFA. Verificar IPs dos clientes no Shodan.",
        "published": "2026-06-01",
        "references": ["https://gov.br/ctir"],
    },
    {
        "id": "CVE-2025-22224",
        "title": "VMware ESXi — VM Escape → RCE no host (CVSS 9.8)",
        "severity": "critical",
        "cvss": 9.8,
        "affected_tech": "VMware ESXi",
        "affected_clients": ["Alupar", "TNE"],
        "exploited_wild": True,
        "patch_available": True,
        "patch_version": "ESXi 8.0 Update 3d / ESXi 7.0 Update 3s",
        "description": "Zero-day explorado ativamente. TOCTOU → Out-of-Bounds Write no VMXNET3. Permite escape de VM para o kernel do host ESXi. Grupos de ransomware usam ativamente.",
        "action": "Aplicar patch VMSA-2025-0004 urgentemente. Se não patched desde Q1/2025, considerar hosts comprometidos.",
        "published": "2025-03-04",
        "references": [
            "https://support.broadcom.com/web/ecx/support-content-notification/-/external/content/SecurityAdvisories/0/25098"
        ],
    },
    {
        "id": "CVE-2025-22225",
        "title": "VMware ESXi — Arbitrary Write → VM Escape",
        "severity": "critical",
        "cvss": 8.2,
        "affected_tech": "VMware ESXi",
        "affected_clients": ["Alupar", "TNE"],
        "exploited_wild": True,
        "patch_available": True,
        "patch_version": "ESXi 8.0 Update 3d / ESXi 7.0 Update 3s",
        "description": "Escrita arbitrária em kernel ESXi permite escape de VM para o host. Usado em conjunto com CVE-2025-22224 em ataques encadeados.",
        "action": "Idem CVE-2025-22224 — mesmo pacote de patch VMSA-2025-0004.",
        "published": "2025-03-04",
        "references": [
            "https://support.broadcom.com/web/ecx/support-content-notification/-/external/content/SecurityAdvisories/0/25098"
        ],
    },
    {
        "id": "CVE-2026-34908",
        "title": "UniFi OS — Controle de Acesso Inadequado (CVSS 10.0)",
        "severity": "critical",
        "cvss": 10.0,
        "affected_tech": "UniFi OS / UniFi Access Points",
        "affected_clients": ["Alupar"],
        "exploited_wild": True,
        "patch_available": True,
        "patch_version": "UniFi OS mais recente (via UniFi Network App)",
        "description": "Controle de acesso inadequado com score máximo CVSS 10.0. Exploração ativa confirmada. Afeta todos os APs UniFi com UniFi OS.",
        "action": "Atualizar UniFi OS IMEDIATAMENTE. Não expor interface 8443/443 à Internet.",
        "published": "2026-05-20",
        "references": ["https://community.ui.com/releases"],
    },
    {
        "id": "CVE-2026-34909",
        "title": "UniFi OS — Path Traversal (CVSS 10.0)",
        "severity": "critical",
        "cvss": 10.0,
        "affected_tech": "UniFi OS",
        "affected_clients": ["Alupar"],
        "exploited_wild": True,
        "patch_available": True,
        "patch_version": "UniFi OS mais recente",
        "description": "Path Traversal crítico no UniFi OS com CVSS 10.0. Exploração ativa em conjunto com CVE-2026-34908 e CVE-2026-34910.",
        "action": "Atualizar UniFi OS IMEDIATAMENTE.",
        "published": "2026-05-20",
        "references": ["https://community.ui.com/releases"],
    },
    {
        "id": "CVE-2024-42327",
        "title": "Zabbix Server — SQL Injection via API → Super Admin",
        "severity": "critical",
        "cvss": 9.9,
        "affected_tech": "Zabbix Server",
        "affected_clients": ["ness. (infraestrutura própria)"],
        "exploited_wild": False,
        "patch_available": True,
        "patch_version": "Zabbix ≥ 7.0.1 / 6.4.17 / 6.0.32",
        "description": "SQL Injection na API do Zabbix permite escalada para Super Admin e RCE no servidor. O Zabbix da ness. é o próprio hub de monitoramento — comprometimento = acesso a todos os clientes.",
        "action": "Confirmar versão do Zabbix Server. Instalar patch. Restringir acesso à API por IP.",
        "published": "2024-11-27",
        "references": ["https://www.zabbix.com/security_advisories"],
    },
    {
        "id": "CVE-2025-59287",
        "title": "Windows Server WSUS — RCE sem autenticação (CVSS 9.8)",
        "severity": "critical",
        "cvss": 9.8,
        "affected_tech": "Windows Server (WSUS)",
        "affected_clients": ["Alupar", "TNE", "Target"],
        "exploited_wild": True,
        "patch_available": True,
        "patch_version": "Patch emergencial Microsoft (Out/2025)",
        "description": "Desserialização insegura no WSUS (TCP 8530/8531) permite RCE remoto sem autenticação. Listado na CISA KEV.",
        "action": "Patch WSUS urgente OU bloquear TCP 8530/8531 no firewall. Desabilitar WSUS se não utilizado.",
        "published": "2025-10-14",
        "references": ["https://cisa.gov/known-exploited-vulnerabilities-catalog"],
    },
    {
        "id": "ANEEL-964-2021",
        "title": "Conformidade ANEEL RN 964/2021 — Cibersegurança Mandatória",
        "severity": "high",
        "cvss": 0.0,
        "affected_tech": "Compliance / Regulatório",
        "affected_clients": ["Alupar", "TBE", "TNE", "Nova Energia"],
        "exploited_wild": False,
        "patch_available": False,
        "patch_version": "Elaborar Política de SI + ETIR + Gestão de Riscos",
        "description": "Resolução Normativa ANEEL 964/2021 exige: Política de Cibersegurança, ETIR (Equipe de Resposta a Incidentes), gestão de riscos documentada e monitoramento contínuo. Clientes transmissores de energia são obrigados por lei.",
        "action": "Suportar Alupar, TBE e TNE na elaboração/revisão da Política de Cibersegurança para conformidade ANEEL.",
        "published": "2021-11-16",
        "references": ["https://gov.br/aneel"],
    },
]

settings = get_settings()
ZABBIX_URL = settings.zabbix_url


def _affected_clients(cve: dict[str, object]) -> list[object]:
    affected_clients = cve.get("affected_clients")
    return affected_clients if isinstance(affected_clients, list) else []


async def _zabbix(method: str, params: dict) -> Any:
    """Faz chamada à API do Zabbix Contabo."""
    if not settings.zabbix_api_token:
        raise RuntimeError("NINF_ZABBIX_API_TOKEN is not configured")
    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        resp = await client.post(
            ZABBIX_URL,
            headers={"Authorization": f"Bearer {settings.zabbix_api_token}"},
            json={
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": 1,
            },
        )
        data = resp.json()
        if "error" in data:
            raise Exception(data["error"].get("data", data["error"]))
        return data["result"]


# ── Endpoints operacionais autenticados ──────────────────────────────────────


@router.get("/cve-intel", dependencies=[Depends(require_noc)])
async def cve_intel(
    severity: str | None = Query(None, description="critical|high|medium"),
    client: str | None = Query(None, description="Filtrar por cliente"),
    exploited_only: bool = Query(False, description="Apenas com exploração ativa"),
) -> dict[str, Any]:
    """
    Retorna base de CVEs críticos dos clientes ness. (OSINT 06/07/2026).
    Inclui FortiGate, VMware ESXi, UniFi, Windows Server, Zabbix.
    """
    items = CVE_DATABASE.copy()
    if severity:
        items = [c for c in items if c["severity"] == severity]
    if client:
        items = [
            c
            for c in items
            if any(
                client.lower() in str(affected_client).lower()
                for affected_client in _affected_clients(c)
            )
        ]
    if exploited_only:
        items = [c for c in items if c["exploited_wild"]]

    critical = sum(1 for c in items if c["severity"] == "critical")
    high = sum(1 for c in items if c["severity"] == "high")
    exploited = sum(1 for c in items if c["exploited_wild"])

    return {
        "updated_at": "2026-07-06T18:00:00Z",
        "source": "ness. OSINT Intelligence",
        "summary": {
            "total": len(items),
            "critical": critical,
            "high": high,
            "exploited_in_wild": exploited,
        },
        "items": items,
    }


@router.get("/zabbix-health", dependencies=[Depends(require_noc)])
async def zabbix_health() -> dict[str, Any]:
    """
    Verifica saúde do Zabbix Contabo em tempo real.
    Retorna: proxies desconectados, actions desabilitadas, hosts sem template,
    problemas ativos por severidade.
    """
    checks: list[dict] = []
    score = 100

    try:
        # ── 1. Proxies conectados ──────────────────────────────────────────
        proxies = await _zabbix(
            "proxy.get",
            {
                "output": ["proxyid", "name", "operating_mode", "lastaccess"],
                "selectHosts": ["hostid"],
            },
        )
        proxy_never_seen = [p for p in proxies if int(p.get("lastaccess", 0)) == 0]
        proxy_status = "danger" if proxy_never_seen else "secure"
        if proxy_never_seen:
            score -= 25
        checks.append(
            {
                "check": "Proxies Conectados",
                "status": proxy_status,
                "value": f"{len(proxies) - len(proxy_never_seen)}/{len(proxies)}",
                "message": (
                    f"{len(proxy_never_seen)} proxies nunca conectaram ao servidor"
                    if proxy_never_seen
                    else "Todos os proxies conectados"
                ),
                "details": [p["name"] for p in proxy_never_seen],
            }
        )

        # ── 2. Hosts sem proxy atribuído ───────────────────────────────────
        hosts_total = int(await _zabbix("host.get", {"countOutput": True}))
        hosts_with_proxy = sum(len(p.get("hosts", [])) for p in proxies)
        hosts_no_proxy = hosts_total - hosts_with_proxy
        proxy_assign_status = (
            "danger"
            if hosts_no_proxy > 100
            else ("warning" if hosts_no_proxy > 0 else "secure")
        )
        if hosts_no_proxy > 0:
            score -= 15
        checks.append(
            {
                "check": "Distribuição por Proxies",
                "status": proxy_assign_status,
                "value": f"{hosts_with_proxy}/{hosts_total}",
                "message": (
                    f"{hosts_no_proxy} hosts monitorados diretamente (sem proxy)"
                    if hosts_no_proxy > 0
                    else "Todos os hosts com proxy atribuído"
                ),
                "details": [],
            }
        )

        # ── 3. Actions (alertas) habilitadas ──────────────────────────────
        actions_all = await _zabbix(
            "action.get", {"output": ["actionid", "name", "status"]}
        )
        actions_disabled = [a for a in actions_all if str(a.get("status", "1")) == "1"]
        actions_status = (
            "danger"
            if len(actions_disabled) == len(actions_all)
            else ("warning" if actions_disabled else "secure")
        )
        if len(actions_disabled) == len(actions_all):
            score -= 30
        elif actions_disabled:
            score -= 10
        checks.append(
            {
                "check": "Actions de Alerta",
                "status": actions_status,
                "value": f"{len(actions_all) - len(actions_disabled)}/{len(actions_all)} ativas",
                "message": (
                    "NENHUMA action habilitada — sem alertas ativos!"
                    if len(actions_disabled) == len(actions_all)
                    else (
                        f"{len(actions_disabled)} action(s) desabilitada(s)"
                        if actions_disabled
                        else "Todas as actions habilitadas"
                    )
                ),
                "details": [a["name"] for a in actions_disabled],
            }
        )

        # ── 4. Hosts sem template ──────────────────────────────────────────
        hosts_detail = await _zabbix(
            "host.get",
            {
                "output": ["hostid", "host"],
                "selectParentTemplates": ["templateid"],
                "filter": {"status": "0"},
            },
        )
        no_template = [h["host"] for h in hosts_detail if not h.get("parentTemplates")]
        tpl_status = (
            "danger"
            if len(no_template) > 10
            else ("warning" if no_template else "secure")
        )
        if no_template:
            score -= 10
        checks.append(
            {
                "check": "Cobertura de Templates",
                "status": tpl_status,
                "value": f"{len(hosts_detail) - len(no_template)}/{len(hosts_detail)}",
                "message": (
                    f"{len(no_template)} host(s) sem template — sem monitoramento de itens"
                    if no_template
                    else "100% dos hosts com template vinculado"
                ),
                "details": no_template[:10],
            }
        )

        # ── 5. Problemas ativos por severidade ────────────────────────────
        problems = await _zabbix(
            "problem.get", {"output": ["eventid", "name", "severity"]}
        )
        sev_count = {str(s): 0 for s in range(6)}
        for p in problems:
            sev_count[str(p.get("severity", "0"))] = (
                sev_count.get(str(p.get("severity", "0")), 0) + 1
            )
        disaster = sev_count.get("5", 0)
        high_p = sev_count.get("4", 0)
        prob_status = (
            "danger" if disaster > 0 else ("warning" if high_p > 5 else "secure")
        )
        if disaster > 0:
            score -= 10
        checks.append(
            {
                "check": "Problemas Ativos",
                "status": prob_status,
                "value": f"{len(problems)} total",
                "message": f"Disaster: {disaster} | High: {high_p} | Average: {sev_count.get('3', 0)}",
                "details": [],
            }
        )

        # ── 6. SNMP community global ───────────────────────────────────────
        gmacros = await _zabbix(
            "usermacro.get", {"output": "extend", "globalmacro": True}
        )
        snmp_macro = next(
            (m for m in gmacros if m["macro"] == "{$SNMP_COMMUNITY}"), None
        )
        snmp_value = snmp_macro["value"] if snmp_macro else "não configurada"
        snmp_status = "danger" if snmp_value in ("public", "private", "") else "secure"
        if snmp_status == "danger":
            score -= 10
        checks.append(
            {
                "check": "SNMP Community",
                "status": snmp_status,
                "value": f"{{$SNMP_COMMUNITY}} = {snmp_value}",
                "message": (
                    f"Community '{snmp_value}' é insegura — padrão reconhecido por atacantes"
                    if snmp_status == "danger"
                    else "Community SNMP configurada de forma segura"
                ),
                "details": [],
            }
        )

        overall = "secure" if score >= 80 else ("warning" if score >= 50 else "danger")

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "score": max(0, score),
            "overall": overall,
            "checks": checks,
            "zabbix_url": "https://zabbix.ness.com.br",
        }

    except Exception as e:
        logger.error("Zabbix health check failed: %s", type(e).__name__)
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "score": 0,
            "overall": "unknown",
            "error": type(e).__name__,
            "checks": [],
            "zabbix_url": "https://zabbix.ness.com.br",
        }


# ── Módulo n.secops: Triagem de Alertas Wazuh SOC via IA & Camada 4 ─────────────

_triage_engine = TriageEngine()


def _extract_ips_and_hashes(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Extrai IPs públicos e hashes de arquivo do payload de alerta do Wazuh."""
    import re

    ips = set()
    hashes = set()

    # Padrão básico de IP
    ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    # Padrão MD5 (32 chars) e SHA256 (64 chars) hex
    hash_pattern = re.compile(r"\b[a-fA-F0-F0-9]{32}\b|\b[a-fA-F0-F0-9]{64}\b")

    def recurse(node: Any):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str):
                    if hash_pattern.match(v):
                        hashes.add(v)
                    elif ip_pattern.match(v):
                        # Ignora loopbacks e IPs privados
                        if not (
                            v.startswith("10.")
                            or v.startswith("192.168.")
                            or v.startswith("127.")
                            or v.startswith("172.")
                            or v.startswith("169.254.")
                        ):
                            ips.add(v)
                else:
                    recurse(v)
        elif isinstance(node, list):
            for item in node:
                recurse(item)

    recurse(payload)
    return list(ips), list(hashes)


def _triage_input(
    payload: dict[str, Any], enrichment: dict[str, list[dict[str, Any]]]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Translate Wazuh's nested event and enrichment lists to the risk contract."""
    raw_rule = payload.get("rule")
    raw_agent = payload.get("agent")
    rule: dict[str, Any] = raw_rule if isinstance(raw_rule, dict) else {}
    agent: dict[str, Any] = raw_agent if isinstance(raw_agent, dict) else {}
    level = rule.get("level", payload.get("level", payload.get("rule_level", 0)))
    try:
        level, level_invalid = int(level), False
    except (TypeError, ValueError, OverflowError):  # None, "abc", NaN, Infinity
        level, level_invalid = 0, True  # nunca 500 nem descarte: segue para atendimento
    alert = {
        **payload,
        "level": level,
        "level_invalid": level_invalid,
        "host": agent.get("name", payload.get("host", payload.get("hostname", ""))),
    }

    sources = [*enrichment.get("ips", []), *enrichment.get("hashes", [])]
    abuse_score = max(
        (
            int(source.get("abuseipdb", {}).get("abuse_score", 0))
            for source in sources
            if isinstance(source.get("abuseipdb"), dict)
        ),
        default=0,
    )
    vt_malicious = max(
        (
            int(source.get("virustotal", {}).get("malicious", 0))
            for source in sources
            if isinstance(source.get("virustotal"), dict)
        ),
        default=0,
    )
    misp_matches = sum(
        int(source.get("misp", {}).get("match_count", 0))
        for source in sources
        if isinstance(source.get("misp"), dict) and source["misp"].get("found")
    )
    return alert, {
        "abuseipdb": {"abuse_score": abuse_score},
        "virustotal": {"malicious": vt_malicious},
        "misp": {"found": misp_matches > 0, "match_count": misp_matches},
    }


async def _resolve_tenant(db: AsyncSession, payload: dict[str, Any]) -> str | None:
    """Cliente pelo vínculo administrativo (grupo Wazuh -> tenant_mappings).

    O grupo recebido é só chave de busca, nunca autorização. Sem vínculo ou com
    vínculos para clientes diferentes devolve None: fica pendente de revisão.
    """
    agent = payload.get("agent")
    names: set[str] = set()
    for key in ("group", "groups"):  # plan 2026-09-18 documents the plural form
        found = agent.get(key) if isinstance(agent, dict) else None
        if isinstance(found, list):
            names |= {g for g in found if isinstance(g, str) and g}
    if not names:
        return None
    rows = (
        (
            await db.execute(
                select(TenantMapping.internal_customer_id)
                .where(
                    TenantMapping.external_platform == "wazuh",
                    TenantMapping.external_customer_id.in_(names),
                )
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    return rows[0] if len(rows) == 1 else None


@router.get("/triage-stats", dependencies=[Depends(require_noc)])
async def get_triage_stats(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Retorna estatísticas persistidas de triagem e bypass de LLM."""
    actions = (await db.execute(select(SocDecision.action_taken))).scalars().all()
    total = len(actions)
    # Pendente de cliente não é decisão de score: fora da meta de bypass.
    pending = sum(action == "PENDING_TENANT_REVIEW" for action in actions)
    bypassed = sum(action == "ARCHIVE_NO_LLM" for action in actions)
    evaluated = total - pending
    llm_called = evaluated - bypassed
    pct_bypassed = round(bypassed / evaluated * 100.0, 2) if evaluated else None
    if pct_bypassed is None:
        status = "unavailable"
    elif pct_bypassed >= 95.0:
        status = "optimal"
    else:
        status = "suboptimal"

    return {
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "total_processed": total,
        "llm_bypassed_count": bypassed,
        "llm_called_count": llm_called,
        "pending_tenant_review_count": pending,
        "bypassed_percentage": pct_bypassed,
        "target_meta_percentage": 95.0,
        "status": status,
    }


@router.post("/triage", dependencies=[Depends(require_noc)])
async def triage_alert(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_noc),
) -> dict[str, Any]:
    """
    Recebe alerta do Wazuh, resolve o cliente por vínculo, executa a triagem determinística
    (Risk Engine) e Threat Intel. Atendimento é independente do score e do modelo.
    """
    logger.info("Recebido alerta Wazuh para triagem.")
    from app.integrations.n8n import notify_soc_triage_decision
    from app.integrations.soc_agent import triage_wazuh_alert
    from app.integrations.threat_intel import enrich_hash, enrich_ip

    # 1. Cliente pelo vínculo administrativo, antes de qualquer saída de dados
    tenant = await _resolve_tenant(db, payload)
    pending = tenant is None

    # 1b. Idempotência: replay do mesmo alerta devolve a decisão salva, sem IA nem despacho
    dedup_key = _dedup_key(tenant, payload)
    if dedup_key and (prior := await _decision_by_key(db, dedup_key)):
        return _duplicate_response(prior)

    # 2. Enriquecimento de Ameaças (Threat Intel); sem cliente, nada sai
    enriched_data: dict[str, list[dict[str, Any]]] = {"ips": [], "hashes": []}
    if not pending:
        ips, hashes = _extract_ips_and_hashes(payload)
        for ip in ips[:3]:  # Limita a 3 IPs para evitar gargalo
            intel = await enrich_ip(ip)
            if intel["abuseipdb"] or intel["virustotal"]:
                enriched_data["ips"].append(intel)
        for h in hashes[:3]:
            intel = await enrich_hash(h)
            if intel["virustotal"]:
                enriched_data["hashes"].append(intel)
    payload["threat_intel_enrichment"] = enriched_data

    # 3. Avaliação de Risco Determinística (Camada 4 - Triage Worker sem LLM)
    rule_id = str(payload.get("rule", {}).get("id", "unknown"))
    agent_id = str(payload.get("agent", {}).get("id", "unknown"))
    agent_name = payload.get("agent", {}).get("name", "unknown")
    # tenant no fingerprint: agent_id é local ao Wazuh de cada cliente (ex.: "001")
    fingerprint = f"{tenant}:{agent_id}:{rule_id}"

    alert_data, threat_intel = _triage_input(payload, enriched_data)
    eval_result = _triage_engine.evaluate_alert(
        alert_data=alert_data,
        threat_intel=threat_intel,
        fingerprint=fingerprint,
    )

    # 4. Atendimento é decidido aqui, independente do score e do modelo.
    # ponytail: piso provisório (NINF_SOC_ATTENDANCE_MIN_LEVEL) até a política
    # do SOC ser aprovada; abaixo dele o score segue valendo como antes.
    must_attend = (
        pending
        or eval_result.action != TriageAction.ARCHIVE
        or alert_data["level_invalid"]
        or alert_data["level"] >= settings.soc_attendance_min_level
    )

    if tenant is None:
        triage_result: dict[str, Any] = {
            "classification": "PENDING_REVIEW",
            "confidence": 0.0,
            "summary": (
                "Cliente não resolvido por vínculo administrativo (wazuh): "
                "ausente ou ambíguo. Revisão técnica; sem enriquecimento nem IA."
            ),
            "action_taken": "PENDING_TENANT_REVIEW",
            "risk_score": eval_result.risk_score,
            "llm_bypassed": True,
        }
    elif not must_attend:
        summary = (
            f"Arquivado por Triage Worker (Risk Score: {eval_result.risk_score}/100 < 75). "
            f"Motivos: {', '.join(eval_result.reasons)}."
        )
        triage_result = {
            "classification": "LOW_PRIORITY",
            "confidence": 0.5,
            "summary": summary,
            "action_taken": "ARCHIVE_NO_LLM",
            "risk_score": eval_result.risk_score,
            "llm_bypassed": True,
        }
        logger.info(
            "Alerta %s arquivado sem LLM (Risk Score %d < 75)",
            fingerprint,
            eval_result.risk_score,
        )
    else:
        # Falha do modelo devolve fallback manual; o despacho não depende dele
        triage_result = dict(await triage_wazuh_alert(payload, tenant))
        triage_result["risk_score"] = eval_result.risk_score
        triage_result["llm_bypassed"] = False
    triage_result["attendance_required"] = must_attend

    customer_id = tenant

    # 6. Persiste a decisão no banco de dados
    payload = {
        **payload,
        "_ness_triage_request": {
            "user_id": user.id,
            "requested_at": datetime.now(UTC).isoformat(),
            "corrective_action_approved": False,
        },
    }
    try:
        decision = SocDecision(
            wazuh_rule_id=rule_id,
            agent_id=agent_id,
            agent_name=agent_name,
            customer_id=customer_id,
            classification=triage_result["classification"],
            confidence=triage_result["confidence"],
            summary=triage_result["summary"],
            action_taken=triage_result["action_taken"],
            raw_alert=payload,
        )
        decision.dedup_key = dedup_key
        db.add(decision)
        await db.commit()
    except IntegrityError:
        # Corrida: outro pedido gravou a mesma chave entre a consulta e o commit
        await db.rollback()
        if dedup_key and (prior := await _decision_by_key(db, dedup_key)):
            return _duplicate_response(prior)
        raise HTTPException(
            503, "Decisão não registrada; despacho não realizado"
        ) from None
    except Exception as e:
        logger.error("Falha ao persistir SocDecision: %s", type(e).__name__)
        await db.rollback()
        raise HTTPException(
            503, "Decisão não registrada; despacho não realizado"
        ) from e

    # 7. Despacha para n8n apenas se não for arquivado silenciosamente
    if must_attend:
        n8n_payload = {
            "wazuh_rule_id": rule_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "customer_id": customer_id,
            "tenant_pending": pending,
            "classification": triage_result["classification"],
            "confidence": triage_result["confidence"],
            "summary": triage_result["summary"],
            "action_taken": triage_result["action_taken"],
            "risk_score": eval_result.risk_score,
            "threat_intel": enriched_data,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        dispatch = notify_soc_triage_decision(n8n_payload)
        triage_result["dispatch_status"] = dispatch.get(
            "status", "failed" if "error" in dispatch else "sent"
        )
    else:
        triage_result["dispatch_status"] = "not_requested"

    triage_result["decision_id"] = decision.id
    triage_result["corrective_action_approved"] = False

    return triage_result


def _dedup_key(tenant: str | None, payload: dict[str, Any]) -> str | None:
    """Chave estável do alerta: tenant + id do Wazuh (ou agente+regra+timestamp).

    Sem id nem timestamp não há como distinguir replay de novo evento: sem chave.
    ponytail: replay após falha de despacho não reenvia ao n8n; reenvio exigiria
    gravar dispatch_status na decisão.
    """
    agent = payload.get("agent") or {}
    rule = payload.get("rule") or {}
    ident = payload.get("id") or (
        f"{agent.get('id')}:{rule.get('id')}:{payload.get('timestamp')}"
        if payload.get("timestamp")
        else None
    )
    if not ident:
        return None
    # Id do Wazuh é epoch.contador por manager: sem tenant, o escopo evita que
    # pendentes de clientes diferentes se suprimam entre si.
    scope = tenant or "-|{}|{}|{}".format(
        (payload.get("manager") or {}).get("name"),
        agent.get("name"),
        sorted(str(g) for k in ("group", "groups") for g in agent.get(k) or []),
    )
    return hashlib.sha256(f"{scope}|{ident}".encode()).hexdigest()


async def _decision_by_key(db: AsyncSession, key: str) -> SocDecision | None:
    result = await db.execute(select(SocDecision).where(SocDecision.dedup_key == key))
    return result.scalars().first()


def _duplicate_response(d: SocDecision) -> dict[str, Any]:
    return {
        "classification": d.classification,
        "confidence": d.confidence,
        "summary": d.summary,
        "action_taken": d.action_taken,
        "decision_id": d.id,
        "duplicate": True,
        "dispatch_status": "duplicate",
        "corrective_action_approved": False,
    }


@router.get("/decisions")
async def list_soc_decisions(
    customer_id: str | None = Query(None),
    classification: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_authenticated),
) -> dict[str, Any]:
    """Retorna a lista de decisões de triagem do SOC persistidas."""
    tenant_scope = resolve_tenant_scope(current_user, customer_id)
    stmt = select(SocDecision).order_by(SocDecision.created_at.desc()).limit(limit)
    if tenant_scope:
        stmt = stmt.where(SocDecision.customer_id == tenant_scope)
    if classification:
        stmt = stmt.where(SocDecision.classification == classification)

    result = await db.execute(stmt)
    decisions = result.scalars().all()

    return {
        "source": "wazuh_soc",
        "total": len(decisions),
        "items": [
            {
                "id": d.id,
                "wazuh_rule_id": d.wazuh_rule_id,
                "agent_id": d.agent_id,
                "agent_name": d.agent_name,
                "customer_id": d.customer_id,
                "classification": d.classification,
                "confidence": d.confidence,
                "summary": d.summary,
                "action_taken": d.action_taken,
                "created_at": d.created_at,
            }
            for d in decisions
        ],
    }
