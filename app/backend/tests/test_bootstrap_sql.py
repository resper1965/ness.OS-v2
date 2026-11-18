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
    cols = re.findall(r"ADD COLUMN IF NOT EXISTS (\w+) ([\w()]+);", MIGRATE)
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
    assert values[0] == values[1] == ["managed", "onsite", "shared"]
    assert (
        "ck_tenant_mappings_modality" in MIGRATE
        and "ck_tenant_mappings_modality" in body
    )


def test_notifications_table_matches_between_migrate_and_bootstrap():
    pat = r"CREATE TABLE IF NOT EXISTS n_infraops_notifications \((.*?)\n\s*\);"
    bodies = [
        {
            m.group(1)
            for m in re.finditer(
                r"(\w+) [A-Z]", _norm(re.search(pat, t, re.S).group(1))
            )
        }
        for t in (MIGRATE, SQL)
    ]
    assert bodies[0] == bodies[1]
    assert {"provider_result", "acknowledged_at", "ack_type", "resolved_at"} <= bodies[
        0
    ]


def test_identities_table_matches_between_migrate_and_bootstrap():
    pat = r"CREATE TABLE IF NOT EXISTS n_infraops_identities \((.*?)\n\s*\)"
    bodies = [_norm(re.search(pat, t, re.S).group(1)) for t in (MIGRATE, SQL)]
    assert bodies[0] == bodies[1]
    assert "UNIQUE (issuer, subject)" in bodies[0]
    for t in (MIGRATE, SQL):
        assert "ix_n_infraops_identities_user_id" in t


def test_customers_ddl_and_seed_match_between_migrate_and_bootstrap():
    for name in ("n_infraops_customers", "n_infraops_customer_aliases"):
        pat = rf"CREATE TABLE IF NOT EXISTS {name} \((.*?)\n\s*\)"
        bodies = [_norm(re.search(pat, t, re.S).group(1)) for t in (MIGRATE, SQL)]
        assert bodies[0] == bodies[1], name
    seed = r"WITH seeded AS (.*?)ON CONFLICT DO NOTHING"
    seeds = [_norm(re.search(seed, t, re.S).group(1)) for t in (MIGRATE, SQL)]
    assert seeds[0] == seeds[1]


def test_sla_block_matches_between_migrate_and_bootstrap():
    sql = re.search(r"-- sla:begin\n(.*?)-- sla:end", SQL, re.S).group(1)
    mig = re.search(r'SLA_SQL = """\n(.*?)"""', MIGRATE, re.S).group(1)
    assert sql.strip() == mig.strip()
    for t in (
        "sla_calendars", "sla_calendar_hours", "sla_holidays", "contracts",
        "sla_policies", "escalation_steps", "contract_changes",
    ):  # fmt: skip
        assert f"CREATE TABLE IF NOT EXISTS n_infraops_{t} " in sql
    assert "ON CONFLICT" in sql


def test_hostgroup_rules_and_contacts_match_between_migrate_and_bootstrap():
    for name in ("n_infraops_hostgroup_rules", "n_infraops_customer_contacts"):
        pat = rf"CREATE TABLE IF NOT EXISTS {name} \((.*?)\n\s*\)"
        bodies = [_norm(re.search(pat, t, re.S).group(1)) for t in (MIGRATE, SQL)]
        assert bodies[0] == bodies[1], name
    pat = r"INSERT INTO n_infraops_hostgroup_rules (.*?)ON CONFLICT DO NOTHING"
    seeds = [_norm(re.search(pat, t, re.S).group(1)) for t in (MIGRATE, SQL)]
    assert seeds[0] == seeds[1] and "Zabbix servers" in seeds[0]
    for idx in ("uq_hostgroup_rules", "ix_n_infraops_customer_contacts_customer_id"):
        assert idx in MIGRATE and idx in SQL


def test_params_block_matches_between_migrate_and_bootstrap():
    sql = re.search(r"-- params:begin\n(.*?)-- params:end", SQL, re.S).group(1)
    mig = re.search(r'PARAMS_SQL = """\n(.*?)"""', MIGRATE, re.S).group(1)
    assert sql.strip() == mig.strip()
    for t in ("contract_policy_params", "platform_params"):
        assert f"CREATE TABLE IF NOT EXISTS n_infraops_{t} " in sql
    assert sql.count("ON CONFLICT") == 2  # seeds idempotentes
    assert "value_int <= 12" in sql  # piso do SOC só pode baixar


def test_ai_decisions_table_and_customer_flag_in_bootstrap():
    sql = re.search(r"-- ai:begin\n(.*?)-- ai:end", SQL, re.S).group(1)
    mig = re.search(r'AI_SQL = """\n(.*?)"""', MIGRATE, re.S).group(1)
    assert sql.strip() == mig.strip()
    assert "CREATE TABLE IF NOT EXISTS n_ai_decisions " in SQL
    for idx in (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_decisions_ref ON n_ai_decisions (kind, source_ref)",
        "CREATE INDEX IF NOT EXISTS ix_ai_decisions_customer_created ON n_ai_decisions (customer_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS ix_ai_decisions_incident ON n_ai_decisions (incident_id) WHERE incident_id IS NOT NULL",
    ):
        assert idx in _norm(SQL) and idx in _norm(MIGRATE)
    flag = "ai_external_allowed BOOLEAN NOT NULL DEFAULT true"
    assert flag in _norm(SQL) and flag in _norm(MIGRATE)
