from pathlib import Path

import httpx
import pytest

from app.integrations.glpi import GLPIClient
from app.integrations.glpi_runbook_categories import import_runbook_categories

CATEGORIES = [
    "Operação interna ness.",
    "Operação padrão MSP",
    "Operação específica do cliente",
    "Backup e continuidade",
    "Identidade e acesso",
    "Monitoramento e observabilidade",
    "Segurança e resposta a incidentes",
    "Mudança, deploy e rollback",
]


def write_manifest(tmp_path: Path, governance_status: str | None) -> Path:
    status = (
        f"governance_status: {governance_status}\n"
        if governance_status
        else "status: draft_for_governance_review\n"
    )
    path = tmp_path / "manifest.yaml"
    path.write_text(
        status
        + "runbook_categories:\n"
        + "".join(f"  - {name}\n" for name in CATEGORIES),
        encoding="utf-8",
    )
    return path


def make_client(handler) -> GLPIClient:
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda **kwargs: original(transport=transport, **kwargs)
    return GLPIClient(
        base_url="https://glpi.test/apirest.php", app_token="app", user_token="user"
    )


@pytest.fixture(autouse=True)
def restore_async_client():
    original = httpx.AsyncClient
    yield
    httpx.AsyncClient = original


@pytest.mark.asyncio
async def test_dry_run_never_posts(tmp_path):
    methods = []

    def handler(request):
        methods.append(request.method)
        if request.url.path.endswith("/initSession"):
            return httpx.Response(200, json={"session_token": "session"})
        return httpx.Response(200, json=[])

    result = await import_runbook_categories(
        make_client(handler), write_manifest(tmp_path, None)
    )

    assert result["missing"] == CATEGORIES
    assert result["created"] == []
    assert "POST" not in methods


@pytest.mark.asyncio
async def test_idempotent_when_all_categories_exist(tmp_path):
    def handler(request):
        if request.url.path.endswith("/initSession"):
            return httpx.Response(200, json={"session_token": "session"})
        if request.method == "POST":
            raise AssertionError("categorias existentes não devem ser recriadas")
        return httpx.Response(
            200,
            json=[
                {"id": index, "name": name} for index, name in enumerate(CATEGORIES, 1)
            ],
        )

    result = await import_runbook_categories(
        make_client(handler), write_manifest(tmp_path, "approved"), apply=True
    )

    assert result == {"missing": [], "unchanged": CATEGORIES, "created": []}


@pytest.mark.asyncio
async def test_apply_refuses_draft_before_http(tmp_path):
    def handler(request):
        raise AssertionError("draft recusado não deve acessar HTTP")

    with pytest.raises(RuntimeError, match="governance_status"):
        await import_runbook_categories(
            make_client(handler), write_manifest(tmp_path, None), apply=True
        )


@pytest.mark.asyncio
async def test_approved_apply_creates_sequentially(tmp_path):
    posted = []

    def handler(request):
        if request.url.path.endswith("/initSession"):
            return httpx.Response(200, json={"session_token": "session"})
        if request.method == "GET":
            return httpx.Response(200, json=[])
        body = __import__("json").loads(request.content)
        posted.append(body["input"]["name"])
        return httpx.Response(201, json={"id": len(posted)})

    result = await import_runbook_categories(
        make_client(handler), write_manifest(tmp_path, "approved"), apply=True
    )

    assert posted == CATEGORIES
    assert result["created"] == [{"id": index} for index in range(1, 9)]


@pytest.mark.asyncio
async def test_ambiguous_existing_category_is_rejected(tmp_path):
    def handler(request):
        if request.url.path.endswith("/initSession"):
            return httpx.Response(200, json={"session_token": "session"})
        return httpx.Response(
            200,
            json=[
                {"id": 1, "name": CATEGORIES[0]},
                {"id": 2, "name": CATEGORIES[0].upper()},
            ],
        )

    with pytest.raises(RuntimeError, match="ambíguas"):
        await import_runbook_categories(
            make_client(handler), write_manifest(tmp_path, "approved"), apply=True
        )
