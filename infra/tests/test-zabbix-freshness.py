import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    'freshness', Path(__file__).resolve().parents[1] / 'scripts/zabbix-freshness.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
summarize = module.summarize_freshness


@pytest.mark.parametrize('delay,lastclock', [
    ('30', 199910), ('30s', 199910), ('1m', 199820),
    ('1h', 189200), ('1d', 40800),
])
def test_includes_exact_three_interval_boundary(delay, lastclock):
    observed = 300000 if delay == '1d' else 200000
    assert summarize([{'itemid': '1', 'delay': delay, 'lastclock': lastclock,
                       'state': 0}], observed) == {
        'essential_metrics': 1, 'fresh': 1, 'stale': 0, 'unknown': 0,
        'state': 'FRESH',
    }


def test_one_second_after_boundary_is_stale():
    assert summarize([{'itemid': '1', 'delay': '1m', 'lastclock': 199819,
                       'state': 0}], 200000) == {
        'essential_metrics': 1, 'fresh': 0, 'stale': 1, 'unknown': 0,
        'state': 'STALE',
    }


@pytest.mark.parametrize('changes', [
    {'lastclock': 200001}, {'lastclock': None}, {'lastclock': 0},
    {'lastclock': -1}, {'delay': '{$INTERVAL}'}, {'delay': '1m;30s/1-7,00:00-24:00'},
    {'delay': '0'}, {'delay': '0s'}, {'delay': '0m'}, {'delay': '-1m'},
    {'delay': '1.5m'}, {'delay': '1w'}, {'delay': ''}, {'delay': None},
    {'state': 1},
])
def test_ambiguous_or_unsupported_metric_is_unknown(changes):
    metric = {'itemid': '1', 'delay': '1m', 'lastclock': 200000, 'state': 0}
    metric.update(changes)
    assert summarize([metric], 200000) == {
        'essential_metrics': 1, 'fresh': 0, 'stale': 0, 'unknown': 1,
        'state': 'UNKNOWN',
    }


def test_empty_scope_is_unknown():
    assert summarize([], 200000) == {
        'essential_metrics': 0, 'fresh': 0, 'stale': 0, 'unknown': 0,
        'state': 'UNKNOWN',
    }


@pytest.mark.parametrize('extra,want', [
    ([], {'essential_metrics': 2, 'fresh': 1, 'stale': 1, 'unknown': 0,
          'state': 'STALE'}),
    ([{'itemid': '3', 'delay': '0', 'lastclock': 200000, 'state': 0}],
     {'essential_metrics': 3, 'fresh': 1, 'stale': 1, 'unknown': 1,
      'state': 'UNKNOWN'}),
])
def test_unknown_takes_precedence_over_stale_and_fresh(extra, want):
    metrics = [
        {'itemid': '1', 'delay': '1m', 'lastclock': 200000, 'state': 0},
        {'itemid': '2', 'delay': '1m', 'lastclock': 199819, 'state': 0},
    ]
    assert summarize(metrics + extra, 200000) == want


def test_summary_does_not_propagate_metric_values_or_secrets():
    metric = {'itemid': 'private-identifier', 'delay': '1m',
              'lastclock': 200000, 'state': 0, 'value': 'sensitive value',
              'error': 'sensitive raw error', 'credentials': 'sensitive token'}
    before = dict(metric)
    assert summarize([metric], 200000) == {
        'essential_metrics': 1, 'fresh': 1, 'stale': 0, 'unknown': 0,
        'state': 'FRESH',
    }
    assert metric == before
