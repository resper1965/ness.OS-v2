"""Parâmetros da política de atendimento SOC por contrato e parâmetros globais da plataforma.

Resolução (a cada chamada, sem cache: edição vale no ciclo seguinte):
contrato ATIVO e vigente do tenant -> contrato padrão (NÃO contratual) -> DEFAULTS.
Os DEFAULTS repetem as constantes que existiam no código e só entram se o padrão
cadastrado não existir; o valor editável é o do contrato padrão. Parâmetro não é dado
pessoal do cliente.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select

from app.models import Contract, ContractPolicyParam, PlatformParam
from app.services.sla import vigent_contracts

logger = logging.getLogger("nessops.policy_params")

# Padrões = constantes de antes (secops/triage_engine/pipeline_health). NÃO contratuais.
CONTRACT_DEFAULTS: dict[str, int] = {
    "soc_attend_min_level": 12,
    "soc_archive_score_floor": 75,
    "ot_retrospective_hours": 24,
    "weekly_sample_per_client": 20,
    "weekly_sample_pct": 10,
    "weekly_sample_threshold": 200,
}
# Teto da política SOC: o contrato só pode ser mais exigente (nunca mais frouxo).
# Nível/score menor atende mais; janela OT menor revisa mais; percentual é limite físico.
CEILINGS: dict[str, int] = {
    "soc_attend_min_level": 12,
    "soc_archive_score_floor": 75,
    "ot_retrospective_hours": 24,
    "weekly_sample_pct": 100,
}
# Amostra semanal: o contrato só amplia (mais revisão), nunca reduz abaixo da política.
FLOORS: dict[str, int] = {"weekly_sample_per_client": 20, "weekly_sample_pct": 10}
PLATFORM_DEFAULTS: dict[str, int] = {
    "source_max_age_seconds": 900,
    "queue_max_age_seconds": 300,
    "worker_failure_window_seconds": 900,
    "probe_timeout_seconds": 20,
}
# probe + cobertura (5 s) precisam caber no monitor de 35 s.
PLATFORM_MAX: dict[str, int] = {
    **{k: 86400 for k in PLATFORM_DEFAULTS},
    "probe_timeout_seconds": 28,
}


@dataclass(frozen=True)
class ParamValue:
    value: int
    contractual: bool


def clamp(key: str, value: int) -> int:
    return max(FLOORS.get(key, 0), min(value, CEILINGS.get(key, value)))


async def get_params(
    session, tenant_id: str | None, keys: tuple[str, ...] = tuple(CONTRACT_DEFAULTS)
) -> dict[str, ParamValue]:
    """Valores efetivos de `keys` para o tenant. Falha de leitura = padrões de código.

    A leitura roda em SAVEPOINT: tabela ausente (migração atrasada) não aborta a
    transação do chamador (triagem) e o comportamento volta ao de antes.
    """
    stored: dict[tuple[int | None, str], int] = {}
    contract_id: int | None = None
    default_id: int | None = None
    try:
        async with session.begin_nested():
            t = (tenant_id or "").lower().strip()
            contract_id = next(
                (c.id for c in await vigent_contracts(session) if t and c.tenant == t),
                None,
            )
            default_id = await session.scalar(
                select(Contract.id).where(Contract.is_default)
            )
            ids = [i for i in (contract_id, default_id) if i is not None]
            if ids:
                rows = await session.execute(
                    select(
                        ContractPolicyParam.contract_id,
                        ContractPolicyParam.key,
                        ContractPolicyParam.value_int,
                    ).where(
                        ContractPolicyParam.contract_id.in_(ids),
                        ContractPolicyParam.key.in_(keys),
                    )
                )
                stored = {(cid, k): v for cid, k, v in rows}
    except Exception:
        logger.warning("policy_params: leitura falhou; usando padrões", exc_info=True)
        stored, contract_id, default_id = {}, None, None
    out = {}
    for key in keys:
        if (contract_id, key) in stored:
            out[key] = ParamValue(clamp(key, stored[contract_id, key]), True)
        elif (default_id, key) in stored:
            out[key] = ParamValue(clamp(key, stored[default_id, key]), False)
        else:
            out[key] = ParamValue(clamp(key, CONTRACT_DEFAULTS[key]), False)
    return out


async def get_param(session, tenant_id: str | None, key: str) -> ParamValue:
    return (await get_params(session, tenant_id, (key,)))[key]


async def platform_params(session) -> dict[str, int]:
    """Parâmetros globais (frescor, fila, sonda); chave ausente = padrão de código."""
    rows = await session.execute(select(PlatformParam.key, PlatformParam.value_int))
    return {**PLATFORM_DEFAULTS, **{k: v for k, v in rows if k in PLATFORM_DEFAULTS}}
