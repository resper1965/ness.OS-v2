from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import migrate


@pytest.mark.asyncio
async def test_upgrade_migration_creates_glpi_ticket_post_reservations(monkeypatch):
    connection = MagicMock()
    connection.execute = AsyncMock()

    @asynccontextmanager
    async def transaction():
        yield connection

    migration_engine = MagicMock()
    migration_engine.begin = transaction
    monkeypatch.setattr(migrate, "engine", migration_engine)

    await migrate.run_migrations()

    statements = [str(call.args[0]) for call in connection.execute.await_args_list]
    assert any(
        "CREATE TABLE IF NOT EXISTS n_infraops_glpi_ticket_post_reservations"
        in statement
        and "PRIMARY KEY (entity_id, fingerprint)" in statement
        for statement in statements
    )
