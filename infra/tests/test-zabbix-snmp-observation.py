import runpy
from pathlib import Path
import pytest


def evaluate(*args):
    path = Path(__file__).resolve().parents[1] / 'scripts/zabbix-snmp-observation.py'
    assert path.exists(), 'Observation evaluator must exist'
    return runpy.run_path(str(path))['evaluate'](*args)


def test_lld_additions_are_allowed_but_existing_items_must_survive():
    assert evaluate({'1'}, {'1', '2'}, [], 100, 5) == 'PENDING'
    with pytest.raises(ValueError):
        evaluate({'1'}, {'2'}, [], 100, 5)


def test_three_distinct_recent_successful_cycles_pass():
    rows = [{'clock': c, 'master_state': 0, 'unsupported': 2} for c in (100, 160, 220)]
    assert evaluate({'1'}, {'1'}, rows, 100, 5) == 'PASS'


def test_duplicate_old_missing_or_failed_clocks_do_not_pass():
    rows = [{'clock': c, 'master_state': 0, 'unsupported': 2} for c in (0, 99, 100, 100)]
    assert evaluate({'1'}, {'1'}, rows, 100, 5) == 'PENDING'
    rows += [{'clock': 160, 'master_state': 1, 'unsupported': 2},
             {'clock': 220, 'master_state': 0, 'unsupported': 6}]
    assert evaluate({'1'}, {'1'}, rows, 100, 5) == 'PENDING'
