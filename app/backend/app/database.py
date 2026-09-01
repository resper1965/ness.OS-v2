# -------------------------------------------------------
# n.infraops — Configuração do Banco de Dados (SQLAlchemy Async)
# -------------------------------------------------------
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    poolclass=NullPool,
    connect_args={"ssl": False},  # Postgres em Docker sem SSL
)

SessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection para sessões do banco de dados na API."""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
