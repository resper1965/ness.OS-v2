import logging
from ipaddress import ip_address
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def is_private_glpi_api_url(url: str) -> bool:
    """Accept only explicit GLPI API paths on private/internal hosts."""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.path.rstrip("/") != "/apirest.php"
    ):
        return False
    if hostname == "localhost" or "." not in hostname:
        return True
    try:
        address = ip_address(hostname)
    except ValueError:
        return hostname.endswith((".internal", ".local"))
    return address.is_private or address.is_loopback or address.is_link_local


class GLPIClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        app_token: Optional[str] = None,
        user_token: Optional[str] = None,
    ):
        settings = get_settings()
        self.base_url = (settings.glpi_url if base_url is None else base_url).rstrip(
            "/"
        )
        self.app_token = settings.glpi_app_token if app_token is None else app_token
        self.user_token = settings.glpi_user_token if user_token is None else user_token

        self.headers = {
            "Content-Type": "application/json",
        }
        if self.app_token:
            self.headers["App-Token"] = self.app_token
        if self.user_token:
            self.headers["Authorization"] = f"user_token {self.user_token}"

        self.session_token: str | None = None

    async def init_session(self) -> str:
        """Inicializa sessão no GLPI e armazena o token de sessão."""
        url = f"{self.base_url}/initSession"
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=False
            ) as client:
                logger.info("Inicializando sessão no GLPI em %s", url)
                res = await client.get(url, headers=self.headers)
                res.raise_for_status()
                data = res.json()
                session_token = data.get("session_token")
                if not isinstance(session_token, str) or not session_token:
                    raise RuntimeError("GLPI não retornou um token de sessão válido")
                self.session_token = session_token
                self.headers["Session-Token"] = session_token
                logger.info("Sessão inicializada no GLPI com sucesso.")
                return session_token
        except Exception as e:
            logger.error("Erro ao inicializar sessão no GLPI: %s", str(e))
            raise RuntimeError(f"Erro ao conectar ao GLPI: {e}") from e

    async def kill_session(self) -> bool:
        """Encerra a sessão ativa no GLPI."""
        if not self.session_token:
            return True
        url = f"{self.base_url}/killSession"
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=False
            ) as client:
                res = await client.get(url, headers=self.headers)
                res.raise_for_status()
                logger.info("Sessão do GLPI encerrada.")
                self.session_token = None
                self.headers.pop("Session-Token", None)
                return True
        except Exception as e:
            logger.warning("Falha ao encerrar sessão no GLPI: %s", str(e))
            return False

    async def get_my_entities(self) -> list[Dict[str, Any]]:
        """Lista somente as entidades visíveis para a sessão técnica atual."""
        if not self.session_token:
            await self.init_session()

        url = f"{self.base_url}/getMyEntities"
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=False
            ) as client:
                res = await client.get(url, headers=self.headers)
                res.raise_for_status()
                data = res.json()
                entities = data.get("myentities") if isinstance(data, dict) else None
                if not isinstance(entities, list):
                    raise RuntimeError("GLPI retornou entidades em formato inválido")
                return entities
        except Exception as e:
            logger.error("Erro ao listar entidades acessíveis no GLPI: %s", str(e))
            raise RuntimeError(f"Erro ao listar entidades no GLPI: {e}") from e

    async def readiness_probe(self) -> Dict[str, Any]:
        """Prova sessão e leituras mínimas por rota privada, sem escrita."""
        if not is_private_glpi_api_url(self.base_url):
            raise RuntimeError(
                "Probe recusado: NINF_GLPI_URL deve apontar para /apirest.php "
                "em host privado"
            )
        if not self.app_token or not self.user_token:
            raise RuntimeError("Probe recusado: tokens GLPI não configurados")

        try:
            await self.init_session()
            entities = await self.get_my_entities()
            categories = await self.list_knowbase_item_categories()
        except Exception:
            await self.kill_session()
            raise

        if not await self.kill_session():
            raise RuntimeError("Probe falhou: sessão GLPI não foi encerrada")

        return {
            "status": "ready",
            "mode": "dry-run",
            "transport": "private",
            "entity_count": len(entities),
            "category_count": len(categories),
            "write_operations": 0,
            "session_closed": True,
        }

    async def create_ticket(
        self,
        title: str,
        content: str,
        entity_id: int = 0,
        itilcategories_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Cria um novo ticket no GLPI."""
        if not self.session_token:
            await self.init_session()

        url = f"{self.base_url}/Ticket"
        input_data = {
            "name": title,
            "content": content,
            "entities_id": entity_id,
            "status": 1,  # Novo
            "urgency": 3,  # Média
        }
        if itilcategories_id is not None:
            input_data["itilcategories_id"] = itilcategories_id

        payload = {"input": input_data}
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=False
            ) as client:
                res = await client.post(url, headers=self.headers, json=payload)
                res.raise_for_status()
                return res.json()
        except Exception as e:
            logger.error("Erro ao criar ticket no GLPI: %s", str(e))
            raise RuntimeError(f"Erro ao criar ticket no GLPI: {e}") from e

    async def add_comment(
        self, ticket_id: int, content: str, private: bool = False
    ) -> Dict[str, Any]:
        """Adiciona um comentário (ITILFollowup) a um ticket existente no GLPI."""
        if not self.session_token:
            await self.init_session()

        url = f"{self.base_url}/ITILFollowup"
        payload = {
            "input": {
                "itemtype": "Ticket",
                "items_id": ticket_id,
                "content": content,
                "is_private": 1 if private else 0,
            }
        }
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=False
            ) as client:
                res = await client.post(url, headers=self.headers, json=payload)
                res.raise_for_status()
                return res.json()
        except Exception as e:
            logger.error(
                "Erro ao adicionar comentário no ticket %d do GLPI: %s",
                ticket_id,
                str(e),
            )
            raise RuntimeError(f"Erro ao adicionar comentário no GLPI: {e}") from e

    async def list_knowbase_item_categories(self) -> list[Dict[str, Any]]:
        """Lista categorias da base de conhecimento pela API suportada."""
        if not self.session_token:
            await self.init_session()

        url = f"{self.base_url}/KnowbaseItemCategory/"
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=False
            ) as client:
                res = await client.get(
                    url,
                    headers=self.headers,
                    params={"range": "0-999", "get_hateoas": "false"},
                )
                res.raise_for_status()
                data = res.json()
                if not isinstance(data, list):
                    raise RuntimeError("GLPI retornou categorias em formato inválido")
                return data
        except Exception as e:
            logger.error(
                "Erro ao listar categorias da base de conhecimento do GLPI: %s", str(e)
            )
            raise RuntimeError(
                f"Erro ao listar categorias da base de conhecimento do GLPI: {e}"
            ) from e

    async def create_knowbase_item_category(self, name: str) -> Dict[str, Any]:
        """Cria uma categoria da base de conhecimento pela API suportada."""
        if not self.session_token:
            await self.init_session()

        url = f"{self.base_url}/KnowbaseItemCategory/"
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=False
            ) as client:
                res = await client.post(
                    url,
                    headers=self.headers,
                    json={"input": {"name": name}},
                )
                res.raise_for_status()
                return res.json()
        except Exception as e:
            logger.error(
                "Erro ao criar categoria da base de conhecimento do GLPI: %s", str(e)
            )
            raise RuntimeError(
                f"Erro ao criar categoria da base de conhecimento do GLPI: {e}"
            ) from e
