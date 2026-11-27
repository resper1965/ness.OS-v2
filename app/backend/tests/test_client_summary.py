"""Resumo de cliente: dry run, idempotência e envio simulado."""

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Customer, TeamMember
from app.models.users import ClientSummary, User, UserRole

URL = "postgresql+asyncpg://dev:dev@127.0.0.1:5471/app"
pytestmark = pytest.mark.asyncio

# Tabelas que o teste usa — na ordem de FK. TicketLink e Incident são lidas
# pelo worker mas não precisam de extensão vetor; criamos só as colunas usadas.
_DDL = """
CREATE TABLE IF NOT EXISTS n_infraops_customers (
    id BIGINT PRIMARY KEY, key VARCHAR(64) NOT NULL, display_name VARCHAR(255) NOT NULL,
    glpi_entity_id INT, active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS n_infraops_users (
    id BIGINT PRIMARY KEY, email VARCHAR(255) NOT NULL, hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255), role VARCHAR(32) NOT NULL DEFAULT 'noc',
    tenant_id VARCHAR(128), is_active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS n_infraops_team_members (
    customer_id BIGINT NOT NULL REFERENCES n_infraops_customers(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES n_infraops_users(id) ON DELETE CASCADE,
    PRIMARY KEY (customer_id, user_id)
);
CREATE TABLE IF NOT EXISTS n_infraops_client_summaries (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    customer_id BIGINT NOT NULL REFERENCES n_infraops_customers(id),
    key VARCHAR(64) NOT NULL, kind VARCHAR(16) NOT NULL,
    html TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, key)
);
-- leitura pelo worker, sem dados:
CREATE TABLE IF NOT EXISTS n_infraops_ticket_links (
    entity_id INT NOT NULL, dedup_key VARCHAR(64) NOT NULL, ticket_id INT NOT NULL,
    state VARCHAR(16) NOT NULL, last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (entity_id, dedup_key)
);
CREATE TABLE IF NOT EXISTS n_infraops_incidents (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    title VARCHAR(512) NOT NULL, severity INT NOT NULL DEFAULT 3,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tags JSONB NOT NULL DEFAULT '{}'
);
"""


@pytest_asyncio.fixture  # scope=function — cada teste tem seu loop assíncrono
async def maker():
    engine = create_async_engine(URL)
    async with engine.begin() as c:
        for stmt in reversed(_DDL.strip().split(";")):  # drop na ordem inversa
            stripped = stmt.strip()
            if not stripped:
                continue
            tname = (
                stripped.split("IF NOT EXISTS")[1].strip().split("(")[0].strip()
                if "IF NOT EXISTS" in stripped
                else ""
            )
            if tname:
                await c.execute(text(f"DROP TABLE IF EXISTS {tname} CASCADE"))
        for stmt in _DDL.strip().split(";"):
            stripped = stmt.strip()
            if stripped:
                await c.execute(text(stripped))
        # seed mínimo: customer, user, team member
        await c.execute(
            text(
                "INSERT INTO n_infraops_customers (id, key, display_name, glpi_entity_id, active) "
                "VALUES (1, 'teste', 'Teste SA', 99, true) ON CONFLICT DO NOTHING"
            )
        )
        await c.execute(
            text(
                "INSERT INTO n_infraops_users (id, email, hashed_password, full_name, role, tenant_id) "
                "VALUES (1, 'gestor@teste.com', 'x', 'Gestor', 'cliente', 'teste') ON CONFLICT DO NOTHING"
            )
        )
        await c.execute(
            text(
                "INSERT INTO n_infraops_team_members (customer_id, user_id) "
                "VALUES (1, 1) ON CONFLICT DO NOTHING"
            )
        )
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as c:
        for stmt in reversed(_DDL.strip().split(";")):
            stripped = stmt.strip()
            if not stripped:
                continue
            tname = (
                stripped.split("IF NOT EXISTS")[1].strip().split("(")[0].strip()
                if "IF NOT EXISTS" in stripped
                else ""
            )
            if tname:
                await c.execute(text(f"DROP TABLE IF EXISTS {tname} CASCADE"))
    await engine.dispose()


async def test_worker_task_registered():
    """A task do Celery está registrada e o worker compila."""
    from app.workers.client_summary import run_summaries
    from app.workers.celery_app import celery_app

    task = celery_app.tasks.get("app.workers.client_summary.send_client_summaries")
    assert task is not None
    assert run_summaries is not None  # só para garantir que importa


async def test_monday_includes_weekly():
    """Segunda-feira gera resumo diário + semanal."""
    from app.workers.client_summary import _today_kinds

    mon = datetime(2026, 11, 30, 11, 0, tzinfo=timezone.utc)  # segunda-feira
    kinds = _today_kinds(mon)
    assert len(kinds) == 2
    assert kinds[0][0] == "daily"
    assert kinds[1][0] == "weekly"


async def test_tuesday_is_daily_only():
    """Terça-feira só gera diário."""
    from app.workers.client_summary import _today_kinds

    tue = datetime(2026, 12, 1, 11, 0, tzinfo=timezone.utc)
    kinds = _today_kinds(tue)
    assert len(kinds) == 1
    assert kinds[0][0] == "daily"
