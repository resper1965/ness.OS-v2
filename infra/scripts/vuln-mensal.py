"""Planilha mensal de vulnerabilidades a partir do indexador Wazuh.

Uso (no host do indexador): sudo python3 vuln-mensal.py <saida_dir>
Carga no Hub: infra/scripts/vuln-carga.sh (usa hub.csv).
Gera vulnerabilidades.xlsx (layout da planilha do time, sem limite), detalhe.csv
(uma linha por CVE x máquina, Windows sem suporte agrupado) e resumo.csv (cliente x severidade).
CSV com ';' e BOM: abre direto no Excel em português.
"""
import base64, csv, json, os, sqlite3, ssl, sys, tarfile, urllib.request
from collections import Counter

ES = os.environ.get("WAZUH_INDEXER", "https://127.0.0.1:9200")
IDX = "wazuh-states-vulnerabilities-*"
SEV = ["Critical", "High", "Medium", "Low"]
ROTULO = {"Critical": "1 - Crítica", "High": "2 - Alta", "Medium": "3 - Média", "Low": "4 - Baixa"}
# Layout da planilha que o time já usa (Vulnerabilidades-31-10-26.xlsx): mesmas 35 colunas, mesma ordem.
BRUTO = ("agent.name agent.id agent.type agent.version host.os.full host.os.kernel host.os.name host.os.platform "
         "host.os.type host.os.version package.architecture package.description package.name package.path "
         "package.size package.type package.version vulnerability.category vulnerability.classification "
         "vulnerability.description vulnerability.detected_at vulnerability.enumeration vulnerability.id "
         "vulnerability.published_at vulnerability.reference vulnerability.scanner.condition "
         "vulnerability.scanner.reference vulnerability.scanner.source vulnerability.scanner.vendor "
         "vulnerability.score.base vulnerability.score.version vulnerability.severity "
         "vulnerability.under_evaluation wazuh.cluster.name wazuh.schema.version").split()
LARG = [16.7, 10.6, 12.9, 15.6, 56.6, 16.1, 41.9, 18.1, 14.3, 17, 22, 44.6, 60.4, 126, 14.4, 15, 19, 23, 27, 120,
        26.3, 27.1, 17, 27.1, 120, 41.6, 56.3, 29.9, 29.4, 25, 27.4, 22.6, 31.4, 21.4, 23.9]
NUM = {"agent.id", "package.size", "vulnerability.score.base"}


def xlsx(path, linhas):
    """Planilha .xlsx só com stdlib (streaming): cabeçalho, filtro, larguras, sem grade."""
    import zipfile
    from xml.sax.saxutils import escape
    col = lambda i: (chr(64 + i // 26) if i >= 26 else "") + chr(65 + i % 26)
    limpa = lambda v: escape("".join(ch for ch in str(v) if ch in "\t\n" or ord(ch) >= 32))[:32000]

    def celula(i, v, c):
        if v is None or v == "": return ""
        if isinstance(v, bool): return f'<c r="{col(i)}{c}" t="b"><v>{int(v)}</v></c>'
        if isinstance(v, (int, float)): return f'<c r="{col(i)}{c}"><v>{v}</v></c>'
        return f'<c r="{col(i)}{c}" t="inlineStr"><is><t xml:space="preserve">{limpa(v)}</t></is></c>'
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    n = 1
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        with z.open("xl/worksheets/sheet1.xml", "w", force_zip64=True) as w:
            put = lambda t: w.write(t.encode())
            cols = "".join(f'<col min="{i+1}" max="{i+1}" width="{x}" customWidth="1"/>' for i, x in enumerate(LARG))
            put(f'<?xml version="1.0" encoding="UTF-8"?><worksheet {ns} {rel}><sheetViews><sheetView showGridLines="0" workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>{cols}</cols><sheetData>')
            put('<row r="1">' + "".join(celula(i, h, 1) for i, h in enumerate(BRUTO)) + "</row>")
            for linha in linhas:
                n += 1
                put(f'<row r="{n}">' + "".join(celula(i, v, n) for i, v in enumerate(linha)) + "</row>")
            put(f'</sheetData><autoFilter ref="A1:{col(len(BRUTO) - 1)}{n}"/></worksheet>')
        z.writestr("xl/workbook.xml", f'<?xml version="1.0" encoding="UTF-8"?><workbook {ns} {rel}><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets><definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">Sheet1!$A$1:${col(len(BRUTO) - 1)}${n}</definedName></definedNames></workbook>')
    return n - 1


def bruto(s):
    out = []
    for c in BRUTO:
        v = campo(s, c)
        if c == "vulnerability.severity": v = ROTULO.get(v, v)
        elif c == "vulnerability.under_evaluation": v = bool(v) if v is not None else None
        elif c in NUM and v not in (None, ""):
            try: v = int(v) if c != "vulnerability.score.base" else float(v)
            except (TypeError, ValueError): pass
        out.append(v)
    return out


def campo(s, caminho):
    for k in caminho.split("."):
        s = s.get(k) if isinstance(s, dict) else None
    return s


EOL = ("Microsoft Windows 10", "Microsoft Windows 8", "Microsoft Windows 7", "Microsoft Windows Server 2012")


def password():
    if os.environ.get("WAZUH_INDEXER_PASSWORD"):
        return os.environ["WAZUH_INDEXER_PASSWORD"]
    with tarfile.open("/root/wazuh/wazuh-install-files.tar") as t:
        txt = t.extractfile("wazuh-install-files/wazuh-passwords.txt").read().decode()
    lines = txt.splitlines()
    i = next(n for n, l in enumerate(lines) if "username: 'admin'" in l)
    return lines[i + 1].split("'")[1]


# o índice de vulnerabilidades não traz o grupo do agente; vem do banco do manager
GRUPOS = {f"{i:03d}": (g or "").split(",") for i, g in sqlite3.connect(
    "file:/var/ossec/queue/db/global.db?mode=ro", uri=True).execute("select id, `group` from agent")}
AUTH = "Basic " + base64.b64encode(f"admin:{password()}".encode()).decode()
CTX = ssl._create_unverified_context()  # ponytail: cert autoassinado local; upgrade: usar root-ca.pem


def post(path, body):
    r = urllib.request.Request(ES + path, json.dumps(body).encode(), method="POST",
                               headers={"Authorization": AUTH, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, context=CTX))


def rows():
    d = post(f"/{IDX}/_search?scroll=2m", {"size": 5000, "sort": ["_doc"]})
    while d["hits"]["hits"]:
        for h in d["hits"]["hits"]:
            yield h["_source"]
        d = post("/_search/scroll", {"scroll": "2m", "scroll_id": d["_scroll_id"]})


def client_of(groups):
    # Grupos seguem CLIENTE-SUBEMPRESA-TIPO (ex.: RZK-AGRO-ESTACOES); cliente = tudo menos o tipo.
    g = next((x for x in groups or [] if x != "default"), "SEM-GRUPO")
    return g.rsplit("-", 1)[0] if g.endswith(("-ESTACOES", "-SERVIDORES")) else g


def main(out):
    os.makedirs(out, exist_ok=True)
    cols = ["cliente", "grupo", "maquina", "so", "pacote", "versao", "cve", "severidade",
            "cvss", "publicada_em", "detectada_em", "referencia"]
    resumo, maquinas, eol = Counter(), {}, set()
    linhas_xlsx = []
    # hub.csv: carga do Hub (infra/scripts/vuln-carga.sh). Grupo, campos de filtro e as 35 colunas em JSON.
    with open(f"{out}/detalhe.csv", "w", newline="", encoding="utf-8-sig") as f, \
            open(f"{out}/hub.csv", "w", newline="", encoding="utf-8") as fh:
        w, hub = csv.writer(f, delimiter=";"), csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        for s in rows():
            raw = bruto(s)
            linhas_xlsx.append(raw)
            a, v, p = s.get("agent", {}), s.get("vulnerability", {}), s.get("package", {})
            os_ = s.get("host", {}).get("os", {})
            groups = a.get("groups") or GRUPOS.get(a.get("id"))
            groups = groups if isinstance(groups, list) else [groups] if groups else []
            cli = client_of(groups)
            grupo = next((g for g in groups if g != "default"), "")
            so = f'{os_.get("name", "")} {os_.get("version", "")}'.strip()
            sev = v.get("severity", "-")
            maquinas.setdefault(cli, set()).add(a.get("name"))
            if (p.get("name") or "").startswith(EOL):  # SO sem suporte: um achado por máquina, não um por CVE
                if (cli, a.get("name")) not in eol:
                    eol.add((cli, a.get("name")))
                    so_raw = list(raw)
                    so_raw[BRUTO.index("vulnerability.id")] = "SO-SEM-SUPORTE"
                    so_raw[BRUTO.index("vulnerability.severity")] = ROTULO["Critical"]
                    hub.writerow([grupo, a.get("name"), so, p.get("name"), p.get("version"), "SO-SEM-SUPORTE",
                                  "Critical", "", "t", v.get("detected_at"), json.dumps(so_raw, ensure_ascii=False)])
                    resumo[cli, "Critical"] += 1
                    w.writerow([cli, "", a.get("name"), p.get("name"), p.get("name"), p.get("version"),
                                "SO-SEM-SUPORTE", "Critical", "", "2025-10-14", "", "https://learn.microsoft.com/lifecycle/products/windows-10-home-and-pro"])
                continue
            resumo[cli, sev] += 1
            score = v.get("score", {}).get("base")
            hub.writerow([grupo, a.get("name"), so, p.get("name"), p.get("version"), v.get("id"), sev,
                          "" if score is None else score, "f", v.get("detected_at"), json.dumps(raw, ensure_ascii=False)])
            w.writerow([cli, ",".join(groups),
                        a.get("name"), so,
                        p.get("name"), p.get("version"), v.get("id"), sev,
                        v.get("score", {}).get("base"), v.get("published_at"),
                        v.get("detected_at"), v.get("reference")])
    with open(f"{out}/resumo.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["cliente", "maquinas_com_vuln", *SEV, "total"])
        for cli in sorted(maquinas):
            n = [resumo[cli, s] for s in SEV]
            w.writerow([cli, len(maquinas[cli]), *n, sum(resumo[cli, s] for s in {k[1] for k in resumo if k[0] == cli})])
    linhas_xlsx.sort(key=lambda l: (l[0] or "", l[31] or ""))
    xlsx(f"{out}/vulnerabilidades.xlsx", linhas_xlsx)
    print(f"{sum(resumo.values())} linhas, {len(maquinas)} clientes -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "vuln-mensal")
