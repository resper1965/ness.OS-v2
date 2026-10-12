"""Build a scoped SNMP template variant without mutating its shared source."""
from copy import deepcopy
import uuid

ORIGINAL = 'FortiGate by SNMP'
CANDIDATE = 'FortiGate by SNMP - UAT walk 5s'


def clone_variant(document):
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
            return CANDIDATE if value == ORIGINAL else value.replace('/'+ORIGINAL+'/', '/'+CANDIDATE+'/')
        return value

    for section in ['templates', 'graphs', 'triggers']:
        if section in root:
            root[section] = rewrite(root[section])
    template = root['templates'][0]
    template['name'] = CANDIDATE
    next(i for i in template['items'] if i['key'] == 'net.if.walk')['timeout'] = '5s'
    return result
