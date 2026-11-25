"""Encerra em lote o acumulado de chamados [n.infraops:...] sem ação técnica no GLPI.

Roda no contêiner da API (PYTHONPATH com app/backend e a raiz do repo), com o token em
NINF_GLPI_USER_TOKEN. Sem --apply só conta. Aborta no primeiro erro do GLPI ou do banco.
Exige GLPI com notificações desligadas e --webhook-off (o webhook do Hub precisa estar
inativo, senão cada solução vira uma tarefa no Hub). Saída: só contagens.
"""

import argparse
import asyncio
import json
import re
from datetime import UTC, datetime

CUTOFF = datetime(2026, 11, 23, 3, tzinfo=UTC)
SOLUTION = "Encerrado na limpeza de 25/11: alerta antigo sem ação técnica."
_MARKER = re.compile(r"\[n\.infraops:([0-9a-f]+)\]")


def select_candidates(rows, cutoff):
    """Chamado em status 1 sem técnico nem acompanhamento humano.

    Anterior ao corte: entra. Posterior: só se o Hub já o trata como painel/resolvido ou
    se o título é ruído.
    """
    out = []
    for r in rows:
        if r["has_tech"] or r["has_human_followup"]:
            continue
        if (
            r["date"] < cutoff
            or r["hub_state"] in ("panel", "resolved")
            or r["is_noise"]
        ):
            out.append(r["id"])
    return out


async def _tickets(glpi, entities):
    """Status 1 por entidade (a busca do GLPI só enxerga a entidade ativa), de 1000 em 1000."""
    import httpx

    out = []
    humans = set()
    for eid in entities:
        await glpi.change_active_entity(eid)
        start = 0
        async with httpx.AsyncClient(timeout=60) as c:
            while True:
                params = {
                    "criteria[0][field]": 12,
                    "criteria[0][searchtype]": "equals",
                    "criteria[0][value]": 1,
                    "range": f"{start}-{start + 999}",
                    "giveItems": "false",
                }
                params.update(
                    {f"forcedisplay[{n}]": f for n, f in enumerate((2, 1, 15, 5, 27))}
                )
                r = await c.get(
                    f"{glpi.base_url}/search/Ticket",
                    headers=glpi.headers,
                    params=params,
                )
                r.raise_for_status()
                j = r.json()
                total = int(j.get("totalcount", 0))
                page = j.get("data") or []
                out.extend({**t, "eid": eid} for t in page)
                # ponytail: 1 acompanhamento é o do próprio Hub; só 2+ são lidos um a um
                # (ler todos pela API leva ~35 min). Upgrade: filtrar por autor se o GLPI expuser.
                for t in page:
                    if t["27"] and int(t["27"]) > 1:
                        items = await glpi.list_items(f"Ticket/{t['2']}/ITILFollowup")
                        if any(
                            int(f.get("users_id", 0)) != (glpi.user_id or 0)
                            for f in items
                        ):
                            humans.add(int(t["2"]))
                start += len(page)
                if not page or start >= total:
                    break
        if start != total:
            raise RuntimeError(f"entidade {eid}: leu {start} de {total}")
    return out, humans


async def _load(glpi):
    from app.database import SessionLocal
    from app.services.ticket_policy import _hit, load_rules
    from sqlalchemy import text

    async with SessionLocal() as s:
        entities = sorted(
            {0}
            | {
                int(e)
                for (e,) in (
                    await s.execute(
                        text(
                            "SELECT glpi_entity_id FROM n_infraops_customers WHERE glpi_entity_id IS NOT NULL"
                        )
                    )
                ).all()
            }
        )
    raw, humans = await _tickets(glpi, entities)
    tickets = [
        {
            "id": t["2"],
            "name": t["1"],
            "date": t["15"],
            "tech": t["5"],
            "fups": t["27"],
            "eid": t["eid"],
        }
        for t in raw
    ]
    async with SessionLocal() as s:
        rules = await load_rules(s)
        states = {
            fp: ("resolved" if st == "resolved" and tag != "opened" else tag)
            for fp, st, tag in (
                await s.execute(
                    text(
                        "SELECT fingerprint, status, tags->>'ninf_ticket_state' "
                        "FROM n_infraops_incidents"
                    )
                )
            ).all()
        }
        live = {
            int(i)
            for (i,) in (
                await s.execute(
                    text(
                        "SELECT ticket_id FROM n_infraops_ticket_links WHERE state='open'"
                    )
                )
            ).all()
        }
    rows = []
    for t in tickets:
        m = _MARKER.search(t["name"])
        if not m:
            continue  # chamado que não é do Hub nunca é tocado
        tid = int(t["id"])
        rows.append(
            {
                "id": tid,
                "eid": t["eid"],
                "date": datetime.fromisoformat(t["date"]).replace(tzinfo=UTC),
                "has_tech": bool(t["tech"]) or tid in live,
                "has_human_followup": tid in humans,
                "hub_state": states.get(m.group(1)),
                "is_noise": _hit(rules.noise, t["name"]),
            }
        )
    return rows


async def _solve(glpi, client, tid):
    """Grava a solução; o GLPI já passa o chamado a status 5, então o PUT só entra se faltar."""
    base = f"{glpi.base_url}/Ticket/{tid}"
    r = await client.post(
        f"{glpi.base_url}/ITILSolution",
        headers=glpi.headers,
        json={"input": {"itemtype": "Ticket", "items_id": tid, "content": SOLUTION}},
    )
    r.raise_for_status()
    r = await client.get(base, headers=glpi.headers, params={"get_hateoas": "false"})
    r.raise_for_status()
    if int(r.json()["status"]) != 5:
        r = await client.put(
            base, headers=glpi.headers, json={"input": {"id": tid, "status": 5}}
        )
        r.raise_for_status()


async def main(apply, webhook_off, workers):
    import httpx
    from app.integrations.glpi import GLPIClient

    glpi = GLPIClient()
    await glpi.init_session()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{glpi.base_url}/getGlpiConfig", headers=glpi.headers)
            r.raise_for_status()
            cfg = r.json().get("cfg_glpi", {})
        if str(cfg.get("use_notifications")) != "0":
            raise SystemExit("abortado: notificações do GLPI ligadas")
        rows = await _load(glpi)
        ids = select_candidates(rows, CUTOFF)
        print(
            json.dumps(
                {"status1_hub": len(rows), "candidatos": len(ids), "apply": apply}
            )
        )
        if not apply:
            return
        if not webhook_off:
            raise SystemExit(
                "abortado: confirme o webhook do Hub desligado com --webhook-off"
            )
        by_entity = {}
        chosen = set(ids)
        for r in rows:
            if r["id"] in chosen:
                by_entity.setdefault(r["eid"], []).append(r["id"])
        done = 0

        async def worker(queue, client):
            nonlocal done
            while not queue.empty():
                await _solve(glpi, client, queue.get_nowait())
                done += 1
                if done % 1000 == 0:
                    print(json.dumps({"resolvidos": done}), flush=True)

        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            # a sessão só age na entidade ativa: um grupo por vez, trabalhadores dentro dele
            for eid, group in sorted(by_entity.items()):
                await glpi.change_active_entity(eid)
                queue = asyncio.Queue()
                for i in group:
                    queue.put_nowait(i)
                # gather sem return_exceptions: o primeiro erro aborta a rodada
                await asyncio.gather(*(worker(queue, client) for _ in range(workers)))
        print(json.dumps({"resolvidos": done, "fim": True}))
    finally:
        await glpi.kill_session()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--webhook-off", action="store_true")
    p.add_argument("--workers", type=int, default=4)
    a = p.parse_args()
    asyncio.run(main(a.apply, a.webhook_off, a.workers))
