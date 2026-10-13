import asyncio
import logging
from ipaddress import ip_address
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class GLPIPermanentError(PermissionError):
    """GLPI denied the configured identity; retries cannot repair its grants."""


class GLPITransientError(RuntimeError):
    """A GLPI transport or capacity failure may recover on a later attempt."""


def _glpi_failure(operation: str, exc: Exception) -> Exception:
    logger.error("GLPI %s failed: %s", operation, type(exc).__name__)
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code in (401, 403):
            return GLPIPermanentError(f"GLPI {operation} sem autorização")
        if exc.response.status_code == 429 or exc.response.status_code >= 500:
            return GLPITransientError(f"GLPI {operation} temporariamente indisponível")
    if isinstance(exc, httpx.TransportError):
        return GLPITransientError(f"GLPI {operation} temporariamente indisponível")
    return RuntimeError(f"GLPI {operation} indisponível")


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
        self.user_id: int | None = None

    async def init_session(self) -> str:
        """Inicializa sessão no GLPI e armazena o token de sessão."""
        url = f"{self.base_url}/initSession"
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=False
            ) as client:
                logger.info("Inicializando sessão no GLPI em %s", url)
                res = await client.get(
                    url, headers=self.headers, params={"get_full_session": "true"}
                )
                res.raise_for_status()
                data = res.json()
                session_token = data.get("session_token")
                if not isinstance(session_token, str) or not session_token:
                    raise RuntimeError("GLPI não retornou um token de sessão válido")
                self.session_token = session_token
                user_id = data.get("session", {}).get("glpiID")
                self.user_id = int(user_id) if user_id else None
                self.headers["Session-Token"] = session_token
                logger.info("Sessão inicializada no GLPI com sucesso.")
                return session_token
        except Exception as exc:
            raise _glpi_failure("sessão", exc) from exc

    async def change_active_entity(self, entity_id: int) -> None:
        """Select exactly one authorized entity before ticket operations."""
        if not self.session_token:
            await self.init_session()
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=False
            ) as client:
                response = await client.post(
                    f"{self.base_url}/changeActiveEntities",
                    headers=self.headers,
                    json={"entities_id": entity_id, "is_recursive": False},
                )
                response.raise_for_status()
                if response.json() is not True:
                    raise GLPIPermanentError("GLPI refused the requested entity")
                current = await client.get(
                    f"{self.base_url}/getActiveEntities", headers=self.headers
                )
                current.raise_for_status()
                payload = current.json()
                active = (
                    payload.get("active_entity") if isinstance(payload, dict) else None
                )
                selected = (
                    active.get("active_entities") if isinstance(active, dict) else None
                )
                if (
                    not isinstance(active, dict)
                    or type(active.get("id")) is not int
                    or active["id"] != entity_id
                    or active.get("active_entity_recursive") is not False
                    or not isinstance(selected, list)
                    or len(selected) != 1
                    or not isinstance(selected[0], dict)
                    or type(selected[0].get("id")) is not int
                    or selected[0]["id"] != entity_id
                ):
                    raise GLPIPermanentError(
                        "GLPI effective entity differs from requested entity"
                    )
        except httpx.HTTPStatusError as exc:
            await self.kill_session()
            raise _glpi_failure("seleção de entidade", exc) from exc
        except httpx.TransportError as exc:
            await self.kill_session()
            raise _glpi_failure("seleção de entidade", exc) from exc
        except BaseException:
            await self.kill_session()
            raise

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
        except Exception as exc:
            logger.warning("GLPI session cleanup failed: %s", type(exc).__name__)
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
        except Exception as exc:
            raise _glpi_failure("leitura de entidades", exc) from exc

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
        except BaseException:
            # A readiness deadline cancels the read. Still close an acquired
            # session, without letting cleanup hide the original failure.
            try:
                async with asyncio.timeout(5):
                    await self.kill_session()
            except Exception:
                logger.warning("Readiness cleanup did not finish within its deadline")
            raise

        async with asyncio.timeout(5):
            closed = await self.kill_session()
        if not closed:
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

    async def get_item(self, itemtype: str, item_id: int) -> dict:
        if not self.session_token:
            await self.init_session()
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                response = await client.get(
                    f"{self.base_url}/{itemtype}/{int(item_id)}", headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise _glpi_failure("leitura de item", exc) from exc
        except httpx.TransportError as exc:
            raise _glpi_failure("leitura de item", exc) from exc

    async def list_items(self, path: str) -> list[dict]:
        """Read every page; callers supply a fixed item type or sub-item path."""
        if not self.session_token:
            await self.init_session()
        items = []
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                for start in range(0, 100000, 100):
                    response = await client.get(
                        f"{self.base_url}/{path}",
                        headers=self.headers,
                        params={
                            "range": f"{start}-{start + 99}",
                            "get_hateoas": "false",
                        },
                    )
                    response.raise_for_status()
                    page = response.json()
                    if not isinstance(page, list):
                        raise ValueError("GLPI returned an invalid collection")
                    items.extend(page)
                    total = response.headers.get("Content-Range", "").rsplit("/", 1)[-1]
                    if (total.isdigit() and len(items) >= int(total)) or len(
                        page
                    ) < 100:
                        return items
        except httpx.HTTPStatusError as exc:
            raise _glpi_failure("lista de itens", exc) from exc
        except httpx.TransportError as exc:
            raise _glpi_failure("lista de itens", exc) from exc
        raise RuntimeError("GLPI pagination limit exceeded")

    async def ticket_resolution(
        self, ticket_id: int, entity_id: int, fingerprint: str
    ) -> dict:
        """Validate ownership and current status before accepting a callback."""
        from html import unescape
        from html.parser import HTMLParser

        class PlainText(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts = []

            def handle_data(self, data):
                self.parts.append(data)

            def handle_endtag(self, tag):
                if tag in ("p", "div", "li"):
                    self.parts.append("\n")

            def handle_starttag(self, tag, attrs):
                if tag == "br":
                    self.parts.append("\n")

        await self.change_active_entity(entity_id)
        ticket = await self.get_item("Ticket", ticket_id)
        if (
            int(ticket["entities_id"]) != entity_id
            or f"[n.infraops:{fingerprint}]" not in ticket["name"]
        ):
            raise ValueError("GLPI ticket ownership mismatch")
        if int(ticket["status"]) not in (5, 6):
            return {"resolved": False, "solution": "", "solution_id": None}
        solutions = await self.list_items(f"Ticket/{ticket_id}/ITILSolution")
        # Status 4 is a refused solution in GLPI; do not import it as applied.
        accepted = [s for s in solutions if int(s.get("status", 0)) != 4]
        latest = max(accepted, key=lambda s: int(s["id"]), default=None)
        parser = PlainText()
        parser.feed(unescape(latest.get("content", "")) if latest else "")
        return {
            "resolved": True,
            "solution": "".join(parser.parts).strip(),
            "solution_id": str(latest["id"]) if latest else None,
        }

    async def create_ticket(
        self,
        title: str,
        content: str,
        entity_id: int = 0,
        itilcategories_id: Optional[int] = None,
        linked_item: dict | None = None,
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
        if self.user_id:
            input_data["_users_id_requester"] = self.user_id
        if linked_item:
            if linked_item["itemtype"] not in ("Computer", "NetworkEquipment"):
                raise ValueError("Unsupported GLPI asset type")
            item = await self.get_item(linked_item["itemtype"], int(linked_item["id"]))
            if int(item["entities_id"]) != entity_id:
                raise ValueError("Asset and ticket must have the same entity")
            input_data["items_id"] = {linked_item["itemtype"]: [int(linked_item["id"])]}

        payload = {"input": input_data}
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=False
            ) as client:
                res = await client.post(url, headers=self.headers, json=payload)
                res.raise_for_status()
                return res.json()
        except Exception as exc:
            raise _glpi_failure("criação de ticket", exc) from exc

    async def find_ticket_by_name_marker(
        self, marker: str, entity_id: int
    ) -> Optional[int]:
        """Find one non-deleted ticket by its deterministic title marker."""
        if not self.session_token:
            await self.init_session()
        if not marker or len(marker) > 96:
            raise ValueError("Marcador de idempotência GLPI inválido")

        url = f"{self.base_url}/Ticket/"
        matches: list[dict[str, Any]] = []
        start = 0
        try:
            async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=False
            ) as client:
                for _ in range(100):
                    res = await client.get(
                        url,
                        headers=self.headers,
                        params=[
                            ("searchText[name]", marker),
                            ("searchText[entities_id]", str(entity_id)),
                            ("range", f"{start}-{start + 99}"),
                            ("get_hateoas", "false"),
                        ],
                    )
                    res.raise_for_status()
                    page = res.json()
                    if not isinstance(page, list):
                        raise RuntimeError(
                            "GLPI retornou busca de tickets em formato inválido"
                        )
                    matches.extend(
                        item
                        for item in page
                        if isinstance(item, dict)
                        and marker in str(item.get("name", ""))
                        and int(item.get("entities_id", -1)) == entity_id
                        and isinstance(item.get("id"), int)
                    )
                    if len(matches) > 1:
                        raise RuntimeError(
                            "GLPI retornou tickets idempotentes duplicados"
                        )
                    content_range = res.headers.get("Content-Range", "")
                    total = content_range.rsplit("/", 1)[-1]
                    if content_range and not total.isdigit():
                        raise RuntimeError("GLPI retornou paginação inválida")
                    if not page and total.isdigit() and start < int(total):
                        raise RuntimeError(
                            "GLPI retornou página vazia antes do fim da busca"
                        )
                    start += len(page)
                    if (total.isdigit() and start >= int(total)) or (
                        not total.isdigit() and len(page) < 100
                    ):
                        return matches[0]["id"] if matches else None
        except RuntimeError:
            raise
        except Exception as exc:
            raise _glpi_failure("consulta de ticket", exc) from exc
        raise RuntimeError("GLPI ticket lookup exceeded pagination limit")

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
        except Exception as exc:
            raise _glpi_failure("comentário de ticket", exc) from exc

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
        except Exception as exc:
            raise _glpi_failure("leitura de categorias", exc) from exc

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
        except Exception as exc:
            raise _glpi_failure("criação de categoria", exc) from exc
