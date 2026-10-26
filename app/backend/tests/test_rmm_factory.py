# -------------------------------------------------------
# n.infraops — Testes unitários do RMMFactory
# -------------------------------------------------------
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.remediators.factory import RMMFactory
from app.models import CustomerCredentials


@pytest.mark.asyncio
async def test_async_get_db_credentials_specific_success():
    """Valida que busca credenciais específicas de um customer no banco."""
    mock_session = AsyncMock()
    mock_result = MagicMock()

    mock_creds = CustomerCredentials(
        customer_id="customer_a",
        provider="datto",
        api_key="key_a",
        api_secret="secret_a",
        api_url="url_a",
    )

    mock_result.scalar_one_or_none.return_value = mock_creds
    mock_session.execute.return_value = mock_result

    with patch("app.database.SessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = mock_session

        creds = await RMMFactory._async_get_db_credentials("customer_a", "datto")

        assert creds["api_key"] == "key_a"
        assert creds["api_secret"] == "secret_a"
        assert creds["api_url"] == "url_a"


@pytest.mark.asyncio
async def test_async_get_db_credentials_fallback_to_default():
    """Valida que busca credenciais 'default' se o customer específico não tiver cadastro."""
    mock_session = AsyncMock()
    mock_result = MagicMock()

    # Primeira execução (específico) retorna None, segunda execução (default) retorna o mock_creds
    mock_creds = CustomerCredentials(
        customer_id="default",
        provider="datto",
        api_key="key_default",
        api_secret="secret_default",
        api_url="url_default",
    )

    mock_result.scalar_one_or_none.side_effect = [None, mock_creds]
    mock_session.execute.return_value = mock_result

    with patch("app.database.SessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = mock_session

        creds = await RMMFactory._async_get_db_credentials("customer_a", "datto")

        assert creds["api_key"] == "key_default"
        assert creds["api_secret"] == "secret_default"
        assert creds["api_url"] == "url_default"


@pytest.mark.asyncio
async def test_async_get_db_credentials_not_found():
    """Valida retorno de dict vazio quando não há nenhuma credencial no banco."""
    mock_session = AsyncMock()
    mock_result = MagicMock()

    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with patch("app.database.SessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = mock_session

        creds = await RMMFactory._async_get_db_credentials("customer_a", "datto")
        assert creds == {}


def test_get_credentials_fallback_to_memory_registry():
    """Valida que _get_credentials faz fallback para o registry em memória se o banco falhar/retornar vazio."""
    # Registra em memória para o teste
    RMMFactory.register_credentials(
        customer_id="memory_cust",
        provider="atera",
        credentials={"api_key": "mem_key", "api_url": "mem_url"},
    )

    # Patcheamos a busca assíncrona no banco para retornar vazio
    with patch.object(RMMFactory, "_async_get_db_credentials", return_value={}):
        creds = RMMFactory._get_credentials("memory_cust", "atera")
        assert creds["api_key"] == "mem_key"
        assert creds.get("api_url") == "mem_url"


def test_get_credentials_db_success():
    """Valida que _get_credentials retorna diretamente a credencial obtida do banco."""
    db_creds = {"api_key": "db_key", "api_secret": "db_secret", "api_url": "db_url"}

    with patch.object(RMMFactory, "_async_get_db_credentials", return_value=db_creds):
        creds = RMMFactory._get_credentials("any_cust", "datto")
        assert creds["api_key"] == "db_key"
        assert creds["api_secret"] == "db_secret"
        assert creds["api_url"] == "db_url"
