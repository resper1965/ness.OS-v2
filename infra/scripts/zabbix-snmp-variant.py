"""Build a scoped SNMP template variant without mutating its shared source."""
from copy import deepcopy
import uuid

ORIGINAL = 'FortiGate by SNMP'
CANDIDATE = 'FortiGate by SNMP - UAT walk 5s'
LINK_TRANSITION = 'FortiGate by SNMP - UAT link transition'


def _clone(document, candidate):
    result = deepcopy(document)
    root = result['zabbix_export']
    if set(root) - {'version', 'date', 'template_groups', 'templates', 'graphs', 'triggers'}:
        raise ValueError('Only a single-template export is allowed')
    templates = root.get('templates', [])
    if len(templates) != 1 or templates[0].get('template') != ORIGINAL:
        raise ValueError('Unexpected source template')
    masters = [i for i in templates[0].get('items', []) if i.get('key') == 'net.if.walk']
    if len(masters) != 1 or masters[0].get('type') != 'SNMP_AGENT':
        raise ValueError('Expected one SNMP network walk')

    def rewrite(value):
        if isinstance(value, dict):
            return {k: uuid.uuid4().hex if k == 'uuid' else rewrite(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        if isinstance(value, str):
            return candidate if value == ORIGINAL else value.replace('/'+ORIGINAL+'/', '/'+candidate+'/')
        return value

    for section in ['templates', 'graphs', 'triggers']:
        if section in root:
            root[section] = rewrite(root[section])
    template = root['templates'][0]
    template['name'] = candidate
    return result


def clone_variant(document):
    result = _clone(document, CANDIDATE)
    items = result['zabbix_export']['templates'][0]['items']
    next(i for i in items if i['key'] == 'net.if.walk')['timeout'] = '5s'
    return result


def clone_link_transition(document):
    result = _clone(document, LINK_TRANSITION)
    rules = result['zabbix_export']['templates'][0].get('discovery_rules', [])
    network = [r for r in rules if r.get('key') == 'net.if.discovery']
    if len(network) != 1:
        raise ValueError('Expected one network discovery rule')
    network[0]['lifetime_type'] = 'DELETE_NEVER'
    return result
