"""Modalidade por vínculo contra Postgres real. Pulado sem NINF_TEST_PG_URL.

Ex.: NINF_TEST_PG_URL=postgresql+asyncpg://dev:dev@127.0.0.1:5439/app pytest tests/test_modality_postgres.py
"""

import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.integrations import pipeline_health as health
from app.models.models import (
    Asset,
    Incident,
    IncidentAction,
    SocDecision,
    TenantMapping,
)

URL = os.environ.get("NINF_TEST_PG_URL")
pytestmark = [
    pytest.mark.skipif(not URL, reason="NINF_TEST_PG_URL não definido"),
    pytest.mark.asyncio,
]


@pytest_asyncio.fixture
async def maker(monkeypatch):
    engine = create_async_engine(URL)
    tabs = [
        Asset.__table__,
        Incident.__table__,
        IncidentAction.__table__,
        SocDecision.__table__,
        TenantMapping.__table__,
    ]
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=tabs))
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(health, "SessionLocal", maker)
    yield maker
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
    await engine.dispose()


async def _add(maker, *rows):
    async with maker() as s:
        for platform, modality in rows:
            s.add(
                TenantMapping(
                    internal_customer_id="c",
                    external_platform=platform,
                    external_customer_id=f"g{id(modality)}{len(platform)}",
                    modality=modality,
                )
            )
        await s.commit()


async def _wazuh():
    return (await health.source_coverage(datetime.now(timezone.utc)))["wazuh"]


async def test_sem_vinculo_e_pendente(maker):
    w = await _wazuh()
    assert w["modality"] == "pendente_de_modalidade"
    assert (w["mappings_total"], w["mappings_with_modality"]) == (0, 0)
    assert w["coverage_declared"] is False


async def test_vinculo_sem_modalidade_e_pendente(maker):
    await _add(maker, ("wazuh", None))
    w = await _wazuh()
    assert w["modality"] == "pendente_de_modalidade"
    assert (w["mappings_total"], w["mappings_with_modality"]) == (1, 0)
    assert w["coverage_declared"] is False


async def test_um_sem_modalidade_entre_varios_mantem_pendente(maker):
    await _add(maker, ("wazuh", "managed"), ("wazuh", None))
    w = await _wazuh()
    assert w["modality"] == "pendente_de_modalidade"
    assert w["coverage_declared"] is False


async def test_mesma_modalidade_declara_cobertura(maker):
    await _add(maker, ("wazuh", "onsite"), ("wazuh", "onsite"))
    w = await _wazuh()
    assert w["modality"] == "onsite"
    assert (w["mappings_total"], w["mappings_with_modality"]) == (2, 2)
    assert w["coverage_declared"] is True


async def test_modalidades_diferentes_e_mista(maker):
    await _add(maker, ("wazuh", "managed"), ("wazuh", "shared"))
    w = await _wazuh()
    assert w["modality"] == "mista" and w["coverage_declared"] is True


async def test_plataformas_nao_se_misturam(maker):
    await _add(maker, ("wazuh", "managed"), ("zabbix", None), ("atera", None))
    src = await health.source_coverage(datetime.now(timezone.utc))
    assert src["wazuh"]["coverage_declared"] is True
    assert src["zabbix"]["modality"] == "pendente_de_modalidade"
    assert src["zabbix"]["mappings_total"] == 1


async def test_campos_antigos_intactos(maker):
    w = await _wazuh()
    assert {"last_data_at", "age_seconds", "stale", "reason"} <= set(w)


async def test_check_rejeita_valor_invalido(maker):
    with pytest.raises(IntegrityError):
        await _add(maker, ("wazuh", "invalida"))


async def test_check_rejeita_nome_antigo_e_aceita_novo(maker):
    for old in ("central_ness", "sonda_no_cliente", "cliente_gerenciado"):
        with pytest.raises(IntegrityError):
            await _add(maker, ("wazuh", old))
    await _add(maker, ("wazuh", "managed"), ("wazuh", "onsite"), ("wazuh", "shared"))


async def test_migracao_converte_nomes_antigos_e_e_idempotente(monkeypatch):
    from sqlalchemy import text

    from app import migrate

    engine = create_async_engine(URL)
    monkeypatch.setattr(migrate, "engine", engine)
    # sem pgvector no Postgres de teste: pula tabelas com coluna VECTOR
    tabs = [
        t
        for t in Base.metadata.sorted_tables
        if not any(type(c.type).__name__.lower() == "vector" for c in t.columns)
    ]
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=tabs))
        await c.execute(
            text(
                "ALTER TABLE n_infraops_tenant_mappings "
                "DROP CONSTRAINT ck_tenant_mappings_modality"
            )
        )
        await c.execute(
            text(
                "ALTER TABLE n_infraops_tenant_mappings "
                "ADD CONSTRAINT ck_tenant_mappings_modality CHECK (modality IS NULL "
                "OR modality IN ('central_ness','sonda_no_cliente','cliente_gerenciado'))"
            )
        )
        await c.execute(
            text(
                "INSERT INTO n_infraops_tenant_mappings "
                "(internal_customer_id, external_platform, external_customer_id, modality) "
                "VALUES ('c','wazuh','a','central_ness'),('c','wazuh','b','sonda_no_cliente'),"
                "('c','wazuh','d','cliente_gerenciado'),('c','wazuh','e',NULL)"
            )
        )
    try:
        for _ in range(2):
            await migrate.run_migrations()
            async with engine.connect() as c:
                rows = (
                    await c.execute(
                        text(
                            "SELECT external_customer_id, modality "
                            "FROM n_infraops_tenant_mappings ORDER BY 1"
                        )
                    )
                ).all()
                ddl = (
                    await c.execute(
                        text(
                            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                            "WHERE conname='ck_tenant_mappings_modality'"
                        )
                    )
                ).scalar_one()
            assert rows == [
                ("a", "managed"),
                ("b", "onsite"),
                ("d", "shared"),
                ("e", None),
            ]
            assert "managed" in ddl and "central_ness" not in ddl
    finally:
        async with engine.begin() as c:
            await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
        await engine.dispose()
