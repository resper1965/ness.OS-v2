import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('register', Path(__file__).resolve().parents[1] / 'scripts/zabbix-asset-register.py')
register = importlib.util.module_from_spec(spec)
spec.loader.exec_module(register)


def row(hostid, flags=0, status=0, items=3, unsupported=0):
    return {'hostid': str(hostid), 'flags': flags, 'status': status, 'name': 'Asset',
            'templates': ['Linux'], 'tags': [], 'item_count': items,
            'enabled_item_count': items,
            'unsupported_count': unsupported, 'error_categories': {}}


def test_all_assets_once_and_prototypes_separate():
    result = register.build_register([row(1), row(2, flags=4), row(3, flags=2)], '2026-10-12T20:00:00Z')
    assert result['totals']['real_hosts'] == 2
    assert result['totals']['prototypes'] == 1
    assert [h['hostid'] for h in result['assets']] == ['1', '2']
    assert result['waves'] == [['1', '2']]


def test_disabled_and_unconfigured_are_not_healthy():
    result = register.build_register([row(1, status=1), row(2, items=0), row(3)], '2026-10-12T20:00:00Z')
    assert [h['state'] for h in result['assets']] == ['disabled_preserved', 'unconfigured', 'assessment_required']
    assert result['totals']['accepted'] == 0


def test_waves_cover_every_real_host_and_never_exceed_five():
    result = register.build_register([row(i) for i in range(1, 263)], '2026-10-12T20:00:00Z')
    assert len(result['waves']) == 53
    assert all(1 <= len(w) <= 5 for w in result['waves'])
    ids = [h for wave in result['waves'] for h in wave]
    assert len(ids) == len(set(ids)) == 262


def test_errors_and_ambiguous_metadata_remain_visible_without_secret_fields():
    host = row(1, unsupported=1)
    host.update({'macros': 'secret', 'ip': 'secret', 'error': 'secret',
                 'tags': [{'tag': 'tenant', 'value': 'A'}, {'tag': 'tenant', 'value': 'B'}]})
    asset = register.build_register([host], '2026-10-12T20:00:00Z')['assets'][0]
    assert asset['state'] == 'needs_remediation'
    assert asset['conflicted_tags'] == ['tenant']
    assert 'owner' in asset['missing_tags']
    assert not {'macros', 'ip', 'error'} & set(asset)


@pytest.mark.parametrize('rows', [[], [row(1), row(1)], [row(1, flags=8)],
                                 [row(1, status=3)], [row(1, items=-1)],
                                 [row(1, unsupported=4)]])
def test_refuses_invalid_or_ambiguous_scope(rows):
    with pytest.raises(ValueError):
        register.build_register(rows, '2026-10-12T20:00:00Z')


def test_unsupported_rate_uses_enabled_real_items_not_disabled_or_prototypes():
    active = row(1, items=100, unsupported=1)
    active['enabled_item_count'] = 10
    result = register.build_register([active, row(2, status=1, items=1000),
                                     row(3, flags=2, items=1000)], '2026-10-12T20:00:00Z')
    assert result['totals']['enabled_items_active'] == 10
    assert result['totals']['unsupported_rate_active'] == 0.1
