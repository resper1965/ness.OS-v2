import importlib.util
from copy import deepcopy
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('variant', Path(__file__).resolve().parents[1] / 'scripts/zabbix-snmp-variant.py')
variant = importlib.util.module_from_spec(spec)
spec.loader.exec_module(variant)


def exported():
    return {'zabbix_export': {'version': '7.0',
        'template_groups': [{'name': 'Templates/Network', 'uuid': 'a' * 32}],
        'templates': [{'template': 'FortiGate by SNMP', 'name': 'FortiGate by SNMP',
            'uuid': 'b' * 32, 'items': [
                {'uuid': 'c' * 32, 'key': 'net.if.walk', 'timeout': '', 'type': 'SNMP_AGENT'},
                {'uuid': 'd' * 32, 'key': 'system.uptime', 'timeout': '3s'}]}],
        'graphs': [{'uuid': 'e' * 32, 'graph_items': [{'item': {'host': 'FortiGate by SNMP', 'key': 'net.if.walk'}}]}]}}


def test_clone_preserves_source_and_rewrites_only_scoped_references():
    source = exported()
    before = deepcopy(source)
    clone = variant.clone_variant(source)
    root = clone['zabbix_export']
    template = root['templates'][0]
    assert source == before
    assert template['template'] == 'FortiGate by SNMP - UAT walk 5s'
    assert template['uuid'] != 'b' * 32
    assert root['template_groups'] == before['zabbix_export']['template_groups']
    assert root['graphs'][0]['graph_items'][0]['item']['host'] == 'FortiGate by SNMP - UAT walk 5s'


def test_timeout_changes_only_network_walk():
    items = variant.clone_variant(exported())['zabbix_export']['templates'][0]['items']
    assert items[0]['timeout'] == '5s'
    assert items[1]['timeout'] == '3s'


def test_refuses_export_with_hosts_or_ambiguous_master():
    source = exported()
    source['zabbix_export']['hosts'] = [{'host': 'live-host'}]
    with pytest.raises(ValueError):
        variant.clone_variant(source)


def link_export():
    source = exported()
    source['zabbix_export']['templates'][0]['discovery_rules'] = [
        {'key': 'net.if.discovery', 'lifetime_type': 'DELETE_AFTER', 'lifetime': '7d',
         'enabled_lifetime_type': 'DISABLE_IMMEDIATELY'},
        {'key': 'cpu.discovery', 'lifetime_type': 'DELETE_AFTER', 'lifetime': '7d'}]
    return source


def test_link_transition_preserves_history_without_timeout_or_other_rule_changes():
    source = link_export()
    before = deepcopy(source)
    result = variant.clone_link_transition(source)['zabbix_export']
    template = result['templates'][0]
    assert source == before
    assert template['template'] == 'FortiGate by SNMP - UAT link transition'
    assert template['items'][0]['timeout'] == ''
    assert template['discovery_rules'][0]['lifetime_type'] == 'DELETE_NEVER'
    assert template['discovery_rules'][0]['enabled_lifetime_type'] == 'DISABLE_IMMEDIATELY'
    assert template['discovery_rules'][1] == before['zabbix_export']['templates'][0]['discovery_rules'][1]
    assert result['graphs'][0]['graph_items'][0]['item']['host'] == 'FortiGate by SNMP - UAT link transition'


@pytest.mark.parametrize('rules', [[], [{'key':'net.if.discovery'}, {'key':'net.if.discovery'}]])
def test_link_transition_refuses_absent_or_duplicate_network_discovery(rules):
    source = link_export()
    source['zabbix_export']['templates'][0]['discovery_rules'] = rules
    with pytest.raises(ValueError):
        variant.clone_link_transition(source)
    source = exported()
    source['zabbix_export']['templates'][0]['items'] = []
    with pytest.raises(ValueError):
        variant.clone_variant(source)
