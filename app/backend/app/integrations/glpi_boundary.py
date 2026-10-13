"""Isolated prototype for the GLPI maintenance object boundary."""


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
            await client.kill_session()
