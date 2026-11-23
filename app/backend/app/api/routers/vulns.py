"""Vulnerabilidades por máquina (carga mensal do inventário de segurança): consulta e planilha."""

from __future__ import annotations

import asyncio
import os
import tempfile
import zipfile
from collections.abc import Sequence
from typing import Any
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.core.dependencies import require_authenticated, resolve_tenant_scope
from app.database import get_db
from app.models.models import Vulnerability
from app.models.users import User

router = APIRouter(
    prefix="/api/secops/vulnerabilities",
    tags=["secops"],
    dependencies=[Depends(require_authenticated)],
)

SEVERITIES = ("Critical", "High", "Medium", "Low")
# Layout da planilha do time (Vulnerabilidades-31-10-26.xlsx): 35 colunas, mesma ordem de infra/scripts/vuln-mensal.py.
COLUMNS = (
    "agent.name agent.id agent.type agent.version host.os.full host.os.kernel host.os.name host.os.platform "
    "host.os.type host.os.version package.architecture package.description package.name package.path "
    "package.size package.type package.version vulnerability.category vulnerability.classification "
    "vulnerability.description vulnerability.detected_at vulnerability.enumeration vulnerability.id "
    "vulnerability.published_at vulnerability.reference vulnerability.scanner.condition "
    "vulnerability.scanner.reference vulnerability.scanner.source vulnerability.scanner.vendor "
    "vulnerability.score.base vulnerability.score.version vulnerability.severity "
    "vulnerability.under_evaluation wazuh.cluster.name wazuh.schema.version"
).split()
WIDTHS = [
    16.7,
    10.6,
    12.9,
    15.6,
    56.6,
    16.1,
    41.9,
    18.1,
    14.3,
    17,
    22,
    44.6,
    60.4,
    126,
    14.4,
    15,
    19,
    23,
    27,
    120,
    26.3,
    27.1,
    17,
    27.1,
    120,
    41.6,
    56.3,
    29.9,
    29.4,
    25,
    27.4,
    22.6,
    31.4,
    21.4,
    23.9,
]


def _like(v: str) -> str:
    return "%" + v.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _filters(
    scope: str | None,
    severity: str | None,
    agent: str | None,
    cve: str | None,
    package: str | None,
    os_name: str | None,
    eol: bool | None,
) -> list:
    v = Vulnerability
    w = []
    if scope:
        w.append(v.customer_id == scope.lower())
    if severity:
        w.append(v.severity == severity)
    if agent:
        w.append(v.agent.ilike(_like(agent), escape="\\"))
    if cve:
        w.append(v.cve == cve.strip().upper())
    if package:
        w.append(v.package.ilike(_like(package), escape="\\"))
    if os_name:
        w.append(v.os.ilike(_like(os_name), escape="\\"))
    if eol is not None:
        w.append(v.eol.is_(eol))
    return w


def _scoped_filters(
    user: User = Depends(require_authenticated),
    customer_id: str | None = Query(None, max_length=128),
    severity: str | None = Query(None, pattern="^(Critical|High|Medium|Low)$"),
    agent: str | None = Query(None, max_length=255),
    cve: str | None = Query(None, max_length=64),
    package: str | None = Query(None, max_length=255),
    os: str | None = Query(None, max_length=255),
    eol: bool | None = Query(None),
) -> list:
    return _filters(
        resolve_tenant_scope(user, customer_id), severity, agent, cve, package, os, eol
    )


async def _top(db: AsyncSession, col, where: list) -> list[dict[str, Any]]:
    rows = await db.execute(
        select(col, func.count())
        .where(*where)
        .group_by(col)
        .order_by(func.count().desc(), col)
        .limit(10)
    )
    return [{"key": k, "count": n} for k, n in rows.all()]


@router.get("")
async def list_vulnerabilities(
    where: list = Depends(_scoped_filters),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    v = Vulnerability
    by_sev: dict[str, int] = dict(
        (
            await db.execute(
                select(v.severity, func.count()).where(*where).group_by(v.severity)
            )
        )
        .tuples()
        .all()
    )
    agents, eol_agents, loaded_at = (
        await db.execute(
            select(
                func.count(v.agent.distinct()),
                func.count(v.agent.distinct()).filter(v.eol),
                func.max(v.loaded_at),
            ).where(*where)
        )
    ).one()
    rows = (
        await db.execute(
            select(
                v.customer_id,
                v.agent,
                v.os,
                v.package,
                v.version,
                v.cve,
                v.severity,
                v.cvss,
                v.eol,
                v.detected_at,
            )
            .where(*where)
            .order_by(v.cvss.desc().nulls_last(), v.agent, v.cve)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return {
        "total": sum(by_sev.values()),
        "by_severity": {s: by_sev.get(s, 0) for s in SEVERITIES},
        "agents": agents,
        "eol_agents": eol_agents,
        "loaded_at": loaded_at.isoformat() if loaded_at else None,
        "top_agents": await _top(db, v.agent, where),
        "top_packages": await _top(db, v.package, where),
        "rows": [
            {
                "customer_id": r.customer_id,
                "agent": r.agent,
                "os": r.os,
                "package": r.package,
                "version": r.version,
                "cve": r.cve,
                "severity": r.severity,
                "cvss": None if r.cvss is None else float(r.cvss),
                "eol": r.eol,
                "detected_at": r.detected_at.isoformat() if r.detected_at else None,
            }
            for r in rows
        ],
    }


def _col(i: int) -> str:
    return (chr(64 + i // 26) if i >= 26 else "") + chr(65 + i % 26)


def _cell(i: int, v: Any, r: int) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, bool):
        return f'<c r="{_col(i)}{r}" t="b"><v>{int(v)}</v></c>'
    if isinstance(v, (int, float)):
        return f'<c r="{_col(i)}{r}"><v>{v}</v></c>'
    s = escape("".join(ch for ch in str(v) if ch in "\t\n" or ord(ch) >= 32))[:32000]
    return f'<c r="{_col(i)}{r}" t="inlineStr"><is><t xml:space="preserve">{s}</t></is></c>'


_NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml"


async def write_xlsx(path: str, rows) -> int:
    """Planilha só com stdlib, em streaming: cabeçalho fixo, filtro e larguras do layout do time."""
    n = 1
    last = _col(len(COLUMNS) - 1)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            f'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="{_CT}.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="{_CT}.worksheet+xml"/></Types>',
        )
        z.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        with z.open("xl/worksheets/sheet1.xml", "w", force_zip64=True) as w:
            cols = "".join(
                f'<col min="{i + 1}" max="{i + 1}" width="{x}" customWidth="1"/>'
                for i, x in enumerate(WIDTHS)
            )
            w.write(
                f'<?xml version="1.0" encoding="UTF-8"?><worksheet {_NS}><sheetViews><sheetView showGridLines="0" workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>{cols}</cols><sheetData>'.encode()
            )
            w.write(
                (
                    '<row r="1">'
                    + "".join(_cell(i, h, 1) for i, h in enumerate(COLUMNS))
                    + "</row>"
                ).encode()
            )

            def batch(part: Sequence[Any], start: int) -> None:
                w.write(
                    "".join(
                        f'<row r="{r}">'
                        + "".join(_cell(i, x, r) for i, x in enumerate(raw))
                        + "</row>"
                        for r, raw in enumerate(part, start)
                    ).encode()
                )

            # Compressão fora do loop de eventos: a API segue atendendo durante a exportação.
            async for part in rows.partitions(2000):
                await asyncio.to_thread(batch, part, n + 1)
                n += len(part)
            w.write(
                f'</sheetData><autoFilter ref="A1:{last}{n}"/></worksheet>'.encode()
            )
        z.writestr(
            "xl/workbook.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><workbook {_NS}><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets><definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">Sheet1!$A$1:${last}${n}</definedName></definedNames></workbook>',
        )
    return n - 1


@router.get("/export")
async def export_vulnerabilities(
    where: list = Depends(_scoped_filters),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    v = Vulnerability
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        stream = await db.stream_scalars(
            select(v.raw)
            .where(*where)
            .order_by(v.customer_id, v.agent, v.cvss.desc().nulls_last())
            .execution_options(yield_per=2000)
        )
        await write_xlsx(path, stream)
    except BaseException:
        os.unlink(path)
        raise
    return FileResponse(
        path,
        media_type=f"{_CT}.sheet",
        filename="vulnerabilidades.xlsx",
        background=BackgroundTask(os.unlink, path),
    )
