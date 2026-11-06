import os
import re
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.models import (
    Customer,
    CustomerAlias,
    CustomerContact,
    HostgroupRule,
)

URL = os.environ.get("NINF_TEST_PG_URL")
SEED = re.search(
    r"WITH seeded AS .*?ON CONFLICT DO NOTHING;",
    (Path(__file__).parents[1] / "sql" / "001_schema.sql").read_text(),
    re.S,
).group(0)


SEED_RULES = re.search(
    r"INSERT INTO n_infraops_hostgroup_rules .*?ON CONFLICT DO NOTHING;",
    (Path(__file__).parents[1] / "sql" / "001_schema.sql").read_text(),
    re.S,
).group(0)


@pytest_asyncio.fixture
async def customers_maker():
    """Postgres real com o cadastro de clientes semeado como na migração."""
    if not URL:
        pytest.skip("NINF_TEST_PG_URL não definido")
    engine = create_async_engine(URL)
    tabs = [
        CustomerContact.__table__,
        HostgroupRule.__table__,
        CustomerAlias.__table__,
        Customer.__table__,
    ]
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
        await c.run_sync(lambda sc: Base.metadata.create_all(sc, tables=tabs))
        await c.execute(text(SEED))
        await c.execute(text(SEED_RULES))
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as c:
        await c.run_sync(lambda sc: Base.metadata.drop_all(sc, tables=tabs))
    await engine.dispose()
