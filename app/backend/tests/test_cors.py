from fastapi.testclient import TestClient

from app.main import app


def test_vite_dev_origin_allows_credentialed_api_requests() -> None:
    response = TestClient(app).options(
        "/api/auth/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
