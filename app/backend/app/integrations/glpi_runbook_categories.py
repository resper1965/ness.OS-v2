"""Importa somente a taxonomia inicial de runbooks para o GLPI."""

import argparse
import asyncio
from pathlib import Path
from typing import Any

from app.integrations.glpi import GLPIClient

EXPECTED_CATEGORY_COUNT = 8


def read_manifest(path: Path) -> tuple[str | None, list[str]]:
    """Lê apenas governance_status e runbook_categories do manifesto simples."""
    governance_status = None
    categories: list[str] = []
    in_categories = False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("governance_status:"):
            governance_status = raw_line.split(":", 1)[1].strip()
            continue
        if raw_line == "runbook_categories:":
            in_categories = True
            continue
        if in_categories and raw_line.startswith("  - "):
            categories.append(raw_line[4:].strip())
            continue
        if in_categories and raw_line and not raw_line.startswith(" "):
            break

    if len(categories) != EXPECTED_CATEGORY_COUNT:
        raise ValueError(
            f"Esperadas {EXPECTED_CATEGORY_COUNT} categorias de runbook; encontradas {len(categories)}"
        )
    normalized = [_normalize(name) for name in categories]
    if any(not name for name in normalized) or len(set(normalized)) != len(normalized):
        raise ValueError(
            "As categorias de runbook devem ter nomes preenchidos e únicos"
        )
    return governance_status, categories


def _normalize(name: str) -> str:
    return " ".join(name.split()).casefold()


async def import_runbook_categories(
    client: GLPIClient,
    manifest_path: Path,
    *,
    apply: bool = False,
) -> dict[str, list[Any]]:
    governance_status, desired = read_manifest(manifest_path)
    if apply and governance_status != "approved":
        raise RuntimeError("Apply recusado: governance_status deve ser 'approved'")

    existing = await client.list_knowbase_item_categories()
    by_name: dict[str, list[dict[str, Any]]] = {}
    for item in existing:
        by_name.setdefault(_normalize(str(item.get("name", ""))), []).append(item)

    ambiguous = [name for name in desired if len(by_name.get(_normalize(name), [])) > 1]
    if ambiguous:
        raise RuntimeError(f"Categorias ambíguas no GLPI: {', '.join(ambiguous)}")

    missing = [name for name in desired if not by_name.get(_normalize(name))]
    unchanged = [name for name in desired if by_name.get(_normalize(name))]
    created: list[dict[str, Any]] = []
    if apply:
        for name in missing:
            created.append(await client.create_knowbase_item_category(name))

    return {"missing": missing, "unchanged": unchanged, "created": created}


async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--apply", action="store_true", help="Cria categorias; o padrão é dry-run"
    )
    args = parser.parse_args()

    client = GLPIClient()
    try:
        result = await import_runbook_categories(
            client, args.manifest, apply=args.apply
        )
        print(
            f"missing={len(result['missing'])} "
            f"unchanged={len(result['unchanged'])} created={len(result['created'])}"
        )
    finally:
        await client.kill_session()


if __name__ == "__main__":
    asyncio.run(_main())
