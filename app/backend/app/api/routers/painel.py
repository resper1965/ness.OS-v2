"""Painel por cliente (P1): blocos Agora, Disponibilidade, Segurança, Exposição e Cobertura.

Só lê o que o Hub já tem. O escopo vem de `resolve_tenant_scope`: operador escolhe o cliente,
os demais papéis ficam presos ao próprio tenant. O bloco Prazo (lido do GLPI) fica para o passo seguinte.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    require_authenticated,
    require_noc,
    resolve_tenant_scope,
)
from app.database import get_db
from app.models.models import (
    Asset,
    AssetStatus,
    Customer,
    CustomerAlias,
    Incident,
    SocDecision,
    Vulnerability,
)
from app.models.users import User

router = APIRouter(prefix="/api/painel", tags=["painel"])

# Status que ainda pedem ação: reconhecer o incidente não o tira da fila.
ATIVOS = ("open", "acknowledged")
# ponytail: o Zabbix não marca "queda"; vale rede com título de indisponibilidade. Upgrade: tag própria na trigger.
QUEDA = ("%tunnel down%", "%unavailable by icmp%", "%link down%", "%is down%")
SEV = ("Critical", "High", "Medium", "Low")


async def _names(db: AsyncSession, scope: str) -> set[str]:
    """Cada fonte grava o cliente de um jeito (chave, nome, apelido); o cadastro junta todos."""
    stmt = (
        select(Customer)
        .outerjoin(CustomerAlias, CustomerAlias.customer_id == Customer.id)
        .where(
            Customer.active.is_(True),
            or_(
                Customer.key == scope,
                func.lower(Customer.display_name) == scope,
                CustomerAlias.alias_norm == scope,
            ),
        )
        .limit(1)
    )
    c = (await db.execute(stmt)).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    aliases = (
        await db.execute(
            select(CustomerAlias.alias_norm).where(CustomerAlias.customer_id == c.id)
        )
    ).scalars()
    return {scope, c.key.lower(), c.display_name.lower(), *aliases}


async def _contar(db: AsyncSession, stmt: Select) -> dict[str, int]:
    return {k: n for k, n in (await db.execute(stmt)).all()}


@router.get("/clientes", dependencies=[Depends(require_noc)])
async def clientes(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = await db.execute(
        select(Customer.key, Customer.display_name)
        .where(Customer.active.is_(True), Customer.glpi_entity_id.is_distinct_from(0))
        .order_by(func.lower(Customer.display_name))
    )
    return [{"key": k, "nome": n} for k, n in rows.all()]


@router.get("")
async def painel(
    customer_id: str | None = Query(None, max_length=128),
    user: User = Depends(require_authenticated),
    db: AsyncSession = Depends(get_db),
) -> dict:
    scope = resolve_tenant_scope(user, customer_id)
    if not scope:
        raise HTTPException(status_code=422, detail="Informe o cliente")
    names = await _names(db, scope.strip().lower())
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=30)

    inc_name = func.lower(Incident.tags["ninf_customer_name"].astext).in_(names)
    branch = func.coalesce(Incident.tags["ninf_branch"].astext, "noc")
    opened = (
        Incident.status.in_(ATIVOS),
        inc_name,
        Incident.tags["ninf_ticket_state"].astext == "opened",
    )

    por_ramo = await _contar(
        db, select(branch, func.count()).where(*opened).group_by(branch)
    )
    sev45 = (
        await db.execute(select(func.count()).where(*opened, Incident.severity >= 4))
    ).scalar_one()

    down_where = (
        Incident.status.in_(ATIVOS),
        inc_name,
        Incident.tags["ninf_zabbix_status"].astext == "problem",
        Incident.tags["class"].astext == "network",
        or_(*(Incident.title.ilike(p) for p in QUEDA)),
    )
    down_total = (
        await db.execute(select(func.count()).where(*down_where))
    ).scalar_one()
    down = (
        await db.execute(
            select(
                Incident.id,
                Incident.host_name,
                Incident.title,
                Incident.severity,
                Incident.first_seen,
            )
            .where(*down_where)
            .order_by(Incident.severity.desc(), Incident.first_seen)
            .limit(10)
        )
    ).all()

    soc_where = (
        func.lower(SocDecision.customer_id).in_(names),
        SocDecision.created_at >= since,
    )
    triados = await _contar(
        db,
        select(SocDecision.classification, func.count())
        .where(*soc_where)
        .group_by(SocDecision.classification),
    )
    rule = SocDecision.raw_alert["rule"]["description"].astext
    top_regras = (
        await db.execute(
            select(rule, func.count())
            .where(*soc_where, rule.is_not(None))
            .group_by(rule)
            .order_by(func.count().desc())
            .limit(5)
        )
    ).all()

    vuln_where = func.lower(Vulnerability.customer_id).in_(names)
    vuln = await _contar(
        db,
        select(Vulnerability.severity, func.count())
        .where(vuln_where)
        .group_by(Vulnerability.severity),
    )
    maquinas, criticas, sem_suporte = (
        await db.execute(
            select(
                func.count(func.distinct(Vulnerability.agent)),
                func.count(func.distinct(Vulnerability.agent)).filter(
                    Vulnerability.severity == "Critical"
                ),
                func.count(func.distinct(Vulnerability.agent)).filter(
                    Vulnerability.eol.is_(True)
                ),
            ).where(vuln_where)
        )
    ).one()
    carga = (
        await db.execute(select(func.max(Vulnerability.loaded_at)).where(vuln_where))
    ).scalar_one()

    ativo = (
        func.lower(Asset.customer_id).in_(names),
        Asset.status == AssetStatus.ACTIVE,
    )
    tipos = await db.execute(
        select(Asset.asset_type, func.count()).where(*ativo).group_by(Asset.asset_type)
    )
    por_tipo = {t.value: n for t, n in tipos.all()}

    return {
        "customer": scope,
        "generated_at": now.isoformat(),
        "agora": {
            "noc": por_ramo.get("noc", 0),
            "soc": por_ramo.get("soc", 0),
            "criticos": sev45,
        },
        "disponibilidade": {
            "fora_do_ar": down_total,
            "itens": [
                {
                    "id": i,
                    "host": h,
                    "titulo": t,
                    "severidade": s,
                    "desde": f.isoformat(),
                }
                for i, h, t, s, f in down
            ],
        },
        "seguranca": {
            "periodo_dias": 30,
            "por_classe": triados,
            "total": sum(triados.values()),
            "top_regras": [{"regra": r, "total": n} for r, n in top_regras],
        },
        "exposicao": {
            "por_severidade": {k: vuln.get(k, 0) for k in SEV},
            "maquinas": maquinas,
            "maquinas_criticas": criticas,
            "maquinas_sem_suporte": sem_suporte,
            "coleta": carga.isoformat() if carga else None,
        },
        "cobertura": {
            "inventario": sum(por_tipo.values()),
            "por_tipo": por_tipo,
            "maquinas_varridas": maquinas,
        },
    }
