"""Execute the actual similarity SQL against transaction-local synthetic tables."""

import ast
import asyncio
import json
from pathlib import Path
import sys

from sqlalchemy import text

from app.database import SessionLocal


async def main():
    tree = ast.parse(Path(sys.argv[1]).read_text())
    query = next(
        node.value.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "similar_query"
            for target in node.targets
        )
    )
    async with SessionLocal() as session:
        try:
            await session.execute(
                text(
                    "CREATE TEMP TABLE n_infraops_assets (id bigint, customer_name text) ON COMMIT DROP"
                )
            )
            await session.execute(
                text(
                    "CREATE TEMP TABLE n_infraops_incidents (fingerprint text, tags jsonb, asset_id bigint) ON COMMIT DROP"
                )
            )
            await session.execute(
                text(
                    "CREATE TEMP TABLE n_infraops_incident_reports (incident_fingerprint text, summary text, root_cause text, embedding vector(3)) ON COMMIT DROP"
                )
            )
            await session.execute(
                text("INSERT INTO n_infraops_assets VALUES (1, 'Cavan'), (2, 'Alupar')")
            )
            await session.execute(
                text(
                    "INSERT INTO n_infraops_incidents VALUES (:fp, CAST(:tags AS jsonb), :asset)"
                ),
                [
                    {"fp": fp, "tags": json.dumps(tags), "asset": asset}
                    for fp, tags, asset in [
                        ("current", {"ninf_customer_name": "Cavan"}, 1),
                        ("same", {"ninf_customer_name": "Cavan"}, 1),
                        ("other", {"ninf_customer_name": "Alupar"}, 2),
                        ("unknown", {}, 1),
                        ("conflict", {"ninf_customer_name": "Cavan"}, 2),
                    ]
                ],
            )
            await session.execute(
                text(
                    "INSERT INTO n_infraops_incident_reports VALUES (:fp, 'synthetic', 'synthetic', CAST(:vector AS vector))"
                ),
                [
                    {"fp": fp, "vector": "[0.9,0.1,0]" if fp == "same" else "[1,0,0]"}
                    for fp in ["same", "other", "unknown", "conflict"]
                ],
            )
            rows = (
                await session.execute(
                    text(query),
                    {"fingerprint": "current", "embedding": "[1,0,0]", "limit": 5},
                )
            ).all()
            assert [row.incident_fingerprint for row in rows] == ["same"], rows
            unknown = (
                await session.execute(
                    text(query),
                    {"fingerprint": "unknown", "embedding": "[1,0,0]", "limit": 5},
                )
            ).all()
            assert unknown == []
            print(
                json.dumps(
                    {
                        "same_tenant_only": True,
                        "other_tenant_excluded": True,
                        "conflicting_asset_excluded": True,
                        "unknown_tenant_excluded": True,
                    }
                )
            )
        finally:
            await session.rollback()
        for table in (
            "n_infraops_assets",
            "n_infraops_incidents",
            "n_infraops_incident_reports",
        ):
            assert (
                await session.scalar(
                    text("SELECT to_regclass(:table)"), {"table": f"pg_temp.{table}"}
                )
                is None
            )
        print(json.dumps({"temporary_tables_removed": True}))


asyncio.run(main())
