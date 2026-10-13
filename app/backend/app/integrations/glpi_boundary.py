"""Isolated prototype for the GLPI maintenance object boundary."""

from hmac import compare_digest

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from app.integrations.glpi import GLPIPermanentError, GLPITransientError


class MaintenanceBoundary:
    def __init__(self, client_factory, *, entity_id: int, approved_ids: set[int]):
        if type(entity_id) is not int or entity_id <= 0:
            raise ValueError("A positive integer entity ID is required")
        if any(type(item_id) is not int or item_id <= 0 for item_id in approved_ids):
            raise ValueError("Approved Computer IDs must be positive integers")
        self.client_factory = client_factory
        self.entity_id = entity_id
        self.approved_ids = frozenset(approved_ids)

    async def read_computer(self, computer_id: int) -> dict:
        if type(computer_id) is not int or computer_id not in self.approved_ids:
            raise PermissionError("Computer is not approved for maintenance access")
        client = self.client_factory()
        try:
            await client.change_active_entity(self.entity_id)
            item = await client.get_item("Computer", computer_id)
            if not isinstance(item, dict):
                raise PermissionError("GLPI returned an invalid Computer")
            if type(item.get("id")) is not int or item["id"] != computer_id:
                raise PermissionError("GLPI returned a different Computer")
            if (
                type(item.get("entities_id")) is not int
                or item["entities_id"] != self.entity_id
            ):
                raise PermissionError("Computer belongs to another entity")
            if not isinstance(item.get("name"), str) or not item["name"].strip():
                raise PermissionError("GLPI returned an invalid Computer name")
            return {
                "id": item["id"],
                "name": item["name"],
                "entities_id": item["entities_id"],
            }
        finally:
            if await client.kill_session() is False:
                raise GLPITransientError("GLPI maintenance session cleanup failed")


def create_app(
    client_factory, *, entity_id: int, approved_ids: set[int], bearer_token: str
):
    if not isinstance(bearer_token, str) or not bearer_token.strip():
        raise ValueError("A nonempty adapter token is required")
    boundary = MaintenanceBoundary(
        client_factory, entity_id=entity_id, approved_ids=approved_ids
    )
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/v1/computers/{computer_id}")
    async def read_computer(computer_id: int, authorization: str | None = Header(None)):
        if not compare_digest(authorization or "", f"Bearer {bearer_token}"):
            raise HTTPException(status_code=401)
        try:
            item = await boundary.read_computer(computer_id)
        except GLPIPermanentError:
            raise HTTPException(status_code=502) from None
        except GLPITransientError:
            raise HTTPException(status_code=503) from None
        except PermissionError:
            raise HTTPException(status_code=404) from None
        return JSONResponse(item, headers={"Cache-Control": "no-store"})

    return app
