"""O bootstrap SQL de banco novo precisa ter as colunas que o código lê."""

import re
from pathlib import Path

SQL = (Path(__file__).parents[1] / "sql" / "001_schema.sql").read_text()


def test_soc_decisions_has_incident_id_and_partial_index():
    table = re.search(r"CREATE TABLE n_secops_soc_decisions \((.*?)\n\);", SQL, re.S)
    assert table and re.search(r"\bincident_id\s+BIGINT,", table.group(1))
    assert re.search(
        r"CREATE INDEX IF NOT EXISTS ix_soc_decisions_incident ON "
        r"n_secops_soc_decisions \(incident_id\) WHERE incident_id IS NOT NULL;",
        SQL,
    )
