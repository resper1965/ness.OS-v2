import pytest
from fastapi.testclient import TestClient

from app.integrations.glpi import GLPIPermanentError, GLPITransientError
from app.integrations.glpi_boundary import create_app


def test_gateway_rejects_missing_token_before_opening_glpi_session():
    def client_factory():
        raise AssertionError("GLPI must not be contacted")

    app = create_app(
        client_factory,
        entity_id=1,
        approved_ids={41},
        bearer_token="local-adapter-token",
    )

    response = TestClient(app).get("/v1/computers/41")

    assert response.status_code == 401


def test_gateway_returns_only_approved_computer_fields():
    class Client:
        async def change_active_entity(self, entity_id):
            assert entity_id == 1

        async def get_item(self, itemtype, item_id):
            assert (itemtype, item_id) == ("Computer", 41)
            return {
                "id": 41,
                "entities_id": 1,
                "name": "approved-host",
                "session_token": "must-not-escape",
                "links": [{"href": "http://glpi/apirest.php/User/7"}],
            }

        async def kill_session(self):
            pass

    app = create_app(
        Client,
        entity_id=1,
        approved_ids={41},
        bearer_token="local-adapter-token",
    )

    response = TestClient(app).get(
        "/v1/computers/41",
        headers={"Authorization": "Bearer local-adapter-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"id": 41, "name": "approved-host", "entities_id": 1}
    assert response.headers["cache-control"] == "no-store"


def test_gateway_hides_unapproved_id_without_contacting_glpi():
    def client_factory():
        raise AssertionError("GLPI must not be contacted")

    app = create_app(
        client_factory,
        entity_id=1,
        approved_ids={41},
        bearer_token="local-adapter-token",
    )

    response = TestClient(app).get(
        "/v1/computers/42",
        headers={"Authorization": "Bearer local-adapter-token"},
    )

    assert response.status_code == 404
    assert "42" not in response.text


@pytest.mark.parametrize("token", ["", " ", "\n"])
def test_gateway_refuses_blank_server_token(token):
    with pytest.raises(ValueError):
        create_app(lambda: None, entity_id=1, approved_ids={41}, bearer_token=token)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/initSession"),
        ("POST", "/changeActiveEntities"),
        ("GET", "/search/Computer"),
        ("GET", "/Computer/41"),
        ("GET", "/v1/computers/41/../42"),
        ("POST", "/v1/computers/41"),
        ("DELETE", "/v1/computers/41"),
    ],
)
def test_gateway_has_no_native_api_proxy_or_write_route(method, path):
    def client_factory():
        raise AssertionError("GLPI must not be contacted")

    app = create_app(
        client_factory,
        entity_id=1,
        approved_ids={41},
        bearer_token="local-adapter-token",
    )
    response = TestClient(app).request(
        method, path, headers={"Authorization": "Bearer local-adapter-token"}
    )
    assert response.status_code in {404, 405}


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (GLPIPermanentError("upstream auth detail"), 502),
        (GLPITransientError("upstream transport detail"), 503),
    ],
)
def test_gateway_hides_upstream_failure_details_and_closes_session(error, status):
    closed = []

    class Client:
        async def change_active_entity(self, entity_id):
            raise error

        async def kill_session(self):
            closed.append(True)

    app = create_app(
        Client, entity_id=1, approved_ids={41}, bearer_token="local-adapter-token"
    )
    response = TestClient(app).get(
        "/v1/computers/41",
        headers={"Authorization": "Bearer local-adapter-token"},
    )
    assert response.status_code == status
    assert "upstream" not in response.text
    assert closed == [True]
