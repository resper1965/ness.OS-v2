import logging
import httpx
from typing import Any, Dict, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)


class GLPIClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        app_token: Optional[str] = None,
        user_token: Optional[str] = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.glpi_url).rstrip("/")
        self.app_token = app_token or settings.glpi_app_token
        self.user_token = user_token or settings.glpi_user_token

        self.headers = {
            "Content-Type": "application/json",
        }
        if self.app_token:
            self.headers["App-Token"] = self.app_token
        if self.user_token:
            self.headers["Authorization"] = f"user_token {self.user_token}"

        self.session_token = None

    async def init_session(self) -> str:
        """Inicializa sessão no GLPI e armazena o token de sessão."""
        url = f"{self.base_url}/initSession"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                logger.info("Inicializando sessão no GLPI em %s", url)
                res = await client.get(url, headers=self.headers)
                res.raise_for_status()
                data = res.json()
                self.session_token = data["session_token"]
                self.headers["Session-Token"] = self.session_token
                logger.info("Sessão inicializada no GLPI com sucesso.")
                return self.session_token
        except Exception as e:
            logger.error("Erro ao inicializar sessão no GLPI: %s", str(e))
            raise RuntimeError(f"Erro ao conectar ao GLPI: {e}") from e

    async def kill_session(self) -> None:
        """Encerra a sessão ativa no GLPI."""
        if not self.session_token:
            return
        url = f"{self.base_url}/killSession"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=self.headers)
                res.raise_for_status()
                logger.info("Sessão do GLPI encerrada.")
                self.session_token = None
                self.headers.pop("Session-Token", None)
        except Exception as e:
            logger.warning("Falha ao encerrar sessão no GLPI: %s", str(e))

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
            async with httpx.AsyncClient(timeout=10.0) as client:
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
            async with httpx.AsyncClient(timeout=10.0) as client:
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
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    url,
                    headers=self.headers,
                    params={"range": "0-999", "get_hateoas": "false"},
                )
                res.raise_for_status()
                return res.json()
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
            async with httpx.AsyncClient(timeout=10.0) as client:
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
