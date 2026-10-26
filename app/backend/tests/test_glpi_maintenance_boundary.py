import pytest

from app.integrations.glpi import GLPIPermanentError, GLPITransientError
from app.integrations.glpi_boundary import MaintenanceBoundary


@pytest.mark.asyncio
async def test_unapproved_computer_id_is_denied_before_glpi_session():
    opened = 0

    def client_factory():
        nonlocal opened
        opened += 1
        raise AssertionError("GLPI must not be contacted")

    boundary = MaintenanceBoundary(client_factory, entity_id=1, approved_ids={41})

    with pytest.raises(PermissionError):
        await boundary.read_computer(42)

    assert opened == 0


@pytest.mark.asyncio
async def test_public_glpi_url_is_denied_and_client_is_closed():
    closed = False

    class Client:
        base_url = "https://n-ticket.ness.com.br/apirest.php"

        async def change_active_entity(self, entity_id):
            raise AssertionError("Public GLPI must not be contacted")

        async def kill_session(self):
            nonlocal closed
            closed = True
            return True

    boundary = MaintenanceBoundary(Client, entity_id=1, approved_ids={41})

    with pytest.raises(GLPIPermanentError):
        await boundary.read_computer(41)

    assert closed


@pytest.mark.asyncio
async def test_approved_computer_uses_fixed_entity_and_returns_only_safe_fields():
    calls = []

    class Client:
        base_url = "http://ninf-glpi/apirest.php"

        async def change_active_entity(self, entity_id):
            calls.append(("entity", entity_id))

        async def get_item(self, itemtype, item_id):
            calls.append(("get", itemtype, item_id))
            return {
                "id": 41,
                "entities_id": 1,
                "name": "approved-host",
                "serial": "private-data",
                "links": [{"href": "http://glpi/apirest.php/User/7"}],
            }

        async def kill_session(self):
            calls.append(("logout",))
            return True

    boundary = MaintenanceBoundary(Client, entity_id=1, approved_ids={41})

    result = await boundary.read_computer(41)

    assert result == {"id": 41, "name": "approved-host", "entities_id": 1}
    assert calls == [
        ("entity", 1),
        ("get", "Computer", 41),
        ("logout",),
    ]


@pytest.mark.asyncio
async def test_child_entity_computer_is_never_returned_even_if_glpi_exposes_it():
    closed = False

    class Client:
        base_url = "http://ninf-glpi/apirest.php"

        async def change_active_entity(self, entity_id):
            assert entity_id == 1

        async def get_item(self, itemtype, item_id):
            return {"id": 41, "entities_id": 5, "name": "child-secret"}

        async def kill_session(self):
            nonlocal closed
            closed = True
            return True

    boundary = MaintenanceBoundary(Client, entity_id=1, approved_ids={41})

    with pytest.raises(PermissionError):
        await boundary.read_computer(41)

    assert closed


@pytest.mark.asyncio
async def test_response_with_different_computer_id_is_denied():
    class Client:
        base_url = "http://ninf-glpi/apirest.php"

        async def change_active_entity(self, entity_id):
            pass

        async def get_item(self, itemtype, item_id):
            return {"id": 42, "entities_id": 1, "name": "other-computer"}

        async def kill_session(self):
            return True

    boundary = MaintenanceBoundary(Client, entity_id=1, approved_ids={41})

    with pytest.raises(PermissionError):
        await boundary.read_computer(41)


@pytest.mark.asyncio
async def test_boolean_id_does_not_match_approved_integer_id():
    opened = False

    def client_factory():
        nonlocal opened
        opened = True
        raise AssertionError("GLPI must not be contacted")

    boundary = MaintenanceBoundary(client_factory, entity_id=1, approved_ids={1})

    with pytest.raises(PermissionError):
        await boundary.read_computer(True)

    assert not opened


@pytest.mark.asyncio
async def test_boolean_entity_in_glpi_response_is_denied():
    class Client:
        base_url = "http://ninf-glpi/apirest.php"

        async def change_active_entity(self, entity_id):
            pass

        async def get_item(self, itemtype, item_id):
            return {"id": 41, "entities_id": True, "name": "ambiguous"}

        async def kill_session(self):
            return True

    boundary = MaintenanceBoundary(Client, entity_id=1, approved_ids={41})

    with pytest.raises(PermissionError):
        await boundary.read_computer(41)


@pytest.mark.asyncio
async def test_mutating_source_approval_set_cannot_grant_new_computer():
    ids = {41}
    opened = False

    def client_factory():
        nonlocal opened
        opened = True
        raise AssertionError("GLPI must not be contacted")

    boundary = MaintenanceBoundary(client_factory, entity_id=1, approved_ids=ids)
    ids.add(42)

    with pytest.raises(PermissionError):
        await boundary.read_computer(42)

    assert not opened


@pytest.mark.asyncio
async def test_missing_entity_in_glpi_response_fails_closed_and_logs_out():
    closed = False

    class Client:
        base_url = "http://ninf-glpi/apirest.php"

        async def change_active_entity(self, entity_id):
            pass

        async def get_item(self, itemtype, item_id):
            return {"id": 41, "name": "unscoped"}

        async def kill_session(self):
            nonlocal closed
            closed = True
            return True

    boundary = MaintenanceBoundary(Client, entity_id=1, approved_ids={41})

    with pytest.raises(PermissionError):
        await boundary.read_computer(41)

    assert closed


@pytest.mark.asyncio
async def test_non_object_glpi_response_is_denied():
    class Client:
        base_url = "http://ninf-glpi/apirest.php"

        async def change_active_entity(self, entity_id):
            pass

        async def get_item(self, itemtype, item_id):
            return [{"id": 41, "entities_id": 1}]

        async def kill_session(self):
            return True

    boundary = MaintenanceBoundary(Client, entity_id=1, approved_ids={41})

    with pytest.raises(PermissionError):
        await boundary.read_computer(41)


@pytest.mark.asyncio
async def test_missing_name_in_glpi_response_is_denied():
    class Client:
        base_url = "http://ninf-glpi/apirest.php"

        async def change_active_entity(self, entity_id):
            pass

        async def get_item(self, itemtype, item_id):
            return {"id": 41, "entities_id": 1}

        async def kill_session(self):
            return True

    boundary = MaintenanceBoundary(Client, entity_id=1, approved_ids={41})

    with pytest.raises(PermissionError):
        await boundary.read_computer(41)


def test_boolean_entity_configuration_is_rejected():
    with pytest.raises(ValueError):
        MaintenanceBoundary(lambda: None, entity_id=True, approved_ids={41})


def test_boolean_approved_id_configuration_is_rejected():
    with pytest.raises(ValueError):
        MaintenanceBoundary(lambda: None, entity_id=1, approved_ids={True})


@pytest.mark.asyncio
async def test_failed_session_cleanup_does_not_return_computer_data():
    class Client:
        base_url = "http://ninf-glpi/apirest.php"

        async def change_active_entity(self, entity_id):
            assert entity_id == 1

        async def get_item(self, itemtype, item_id):
            return {"id": 41, "entities_id": 1, "name": "approved-host"}

        async def kill_session(self):
            return False

    boundary = MaintenanceBoundary(Client, entity_id=1, approved_ids={41})

    with pytest.raises(GLPITransientError):
        await boundary.read_computer(41)


@pytest.mark.asyncio
async def test_unconfirmed_session_cleanup_does_not_return_computer_data():
    class Client:
        base_url = "http://ninf-glpi/apirest.php"

        async def change_active_entity(self, entity_id):
            assert entity_id == 1

        async def get_item(self, itemtype, item_id):
            return {"id": 41, "entities_id": 1, "name": "approved-host"}

        async def kill_session(self):
            return None

    boundary = MaintenanceBoundary(Client, entity_id=1, approved_ids={41})

    with pytest.raises(GLPITransientError):
        await boundary.read_computer(41)
