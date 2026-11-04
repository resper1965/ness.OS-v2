"""O bootstrap SQL de banco novo precisa ter as colunas e índices que migrate.py cria."""

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
SQL = (ROOT / "sql" / "001_schema.sql").read_text()
MIGRATE = (ROOT / "app" / "migrate.py").read_text()
TABLE = "n_secops_soc_decisions"


def _norm(s):
    return re.sub(r"\s+", " ", s.replace('"\n', " ").replace('"', "")).strip()


def test_soc_decisions_columns_from_migrate_exist_in_bootstrap():
    body = re.search(rf"CREATE TABLE {TABLE} \((.*?)\n\);", SQL, re.S).group(1)
    cols = re.findall(rf"ADD COLUMN IF NOT EXISTS (\w+) ([\w()]+);", MIGRATE)
    soc = {"dedup_key", "freq_key", "incident_id"}
    assert soc <= {c for c, _ in cols}
    for name, typ in cols:
        if name in soc:
            assert re.search(rf"\b{name}\s+{re.escape(typ)},", body), name


def test_soc_decisions_indexes_from_migrate_exist_in_bootstrap():
    for name in (
        "ix_soc_decisions_freq",
        "ix_soc_decisions_action_created",
        "ix_soc_decisions_incident",
        "ix_soc_decisions_created",
        "uq_soc_decisions_dedup",
    ):
        m = re.search(rf"INDEX IF NOT EXISTS {name} ([^;]*);", _norm(MIGRATE))
        assert m, name
        ddl = m.group(1)
        b = re.search(rf"INDEX (?:IF NOT EXISTS )?{name} ([^;]*);", SQL)
        assert b and _norm(b.group(1)) == ddl, name


def test_tenant_mappings_modality_from_migrate_exist_in_bootstrap():
    body = re.search(
        r"CREATE TABLE IF NOT EXISTS n_infraops_tenant_mappings \((.*?)\n\);", SQL, re.S
    ).group(1)
    cols = dict(
        re.findall(
            r"ALTER TABLE n_infraops_tenant_mappings "
            r"ADD COLUMN IF NOT EXISTS (\w+) ([\w()]+);",
            _norm(MIGRATE),
        )
    )
    assert cols == {"modality": "VARCHAR(32)", "operator": "VARCHAR(128)"}
    for name, typ in cols.items():
        assert re.search(rf"\b{name}\s+{re.escape(typ)},", body), name
    check = r"CHECK \(\s*modality IS NULL OR modality IN\s*\(([^)]*)\)\s*\)"
    values = [
        re.findall(r"'(\w+)'", re.search(check, t).group(1)) for t in (MIGRATE, body)
    ]
    assert (
        values[0]
        == values[1]
        == ["central_ness", "sonda_no_cliente", "cliente_gerenciado"]
    )
    assert (
        "ck_tenant_mappings_modality" in MIGRATE
        and "ck_tenant_mappings_modality" in body
    )
