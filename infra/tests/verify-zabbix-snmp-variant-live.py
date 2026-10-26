#!/usr/bin/env python3
"""Explicit one-host UAT integration test; always return to the original template."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import urllib.request

if os.geteuid() != 0 or socket.gethostname() != 'zbx-prd-01':
    raise RuntimeError('Isolated UAT only')
for option, expected in [('is-active', 'inactive'), ('is-enabled', 'masked')]:
    if subprocess.run(['systemctl', option, 'zabbix-server'], capture_output=True,
                      text=True).stdout.strip() != expected:
        raise RuntimeError('Isolation required')
os.umask(0o077)

def call(method, params, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request('http://127.0.0.1:8080/zabbix/api_jsonrpc.php',
        data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode(),
        headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if 'error' in result:
        raise RuntimeError('API rejected ' + method)
    return result['result']

token = call('user.login', {'username': 'ness_uat_breakglass', 'password':
    Path('/etc/ness-os/zabbix-uat-recovery.password').read_text().strip()})

def snapshot():
    host = call('host.get', {'hostids': ['10768'], 'output': ['hostid', 'status'],
        'selectParentTemplates': ['templateid'], 'selectItems': ['itemid', 'key_']}, token)[0]
    triggers = call('trigger.get', {'hostids': ['10768'], 'output': ['triggerid']}, token)
    return {'templates': sorted(t['templateid'] for t in host['parentTemplates']),
        'status': host['status'], 'items': sorted((i['key_'], i['itemid']) for i in host['items']),
        'triggers': sorted(t['triggerid'] for t in triggers)}

changed = False
try:
    before = snapshot()
    if before['templates'] != ['10604']:
        raise RuntimeError('Unexpected starting template')
    if '--apply' not in sys.argv:
        print('variant_link_preflight=PASS; mode=preview')
    else:
        report = Path('/var/lib/ness-os/restore-evidence/snmp-variant-link-test-20261012.json')
        if report.exists():
            raise RuntimeError('Existing test evidence; do not repeat blindly')
        with report.open('x') as output:
            json.dump({'before': before, 'result': 'STARTED'}, output)
        changed = True  # Restore even if a write succeeds but its response is lost.
        call('host.update', {'hostid': '10768', 'templates': [{'templateid': '10988'}]}, token)
        after = snapshot()
        if after['templates'] != ['10988'] or any(after[k] != before[k] for k in ['items', 'triggers', 'status']):
            raise RuntimeError('IDs or host state changed; restore original linkage')
        master = call('item.get', {'itemids': ['85756'], 'output': ['itemid', 'timeout']}, token)
        if len(master) != 1 or master[0]['timeout'] != '5s':
            raise RuntimeError('Inherited walk timeout mismatch')
        call('host.update', {'hostid': '10768', 'templates': [{'templateid': '10604'}]}, token)
        restored = snapshot()
        if restored != before:
            raise RuntimeError('Rollback did not preserve configuration IDs')
        changed = False
        with report.open('w') as output:
            json.dump({'before': before, 'after': after, 'restored': restored,
                       'result': 'PASS', 'collection_tested': False}, output)
        print('variant_link=PASS; ids_preserved=true; rollback=PASS; collection=NOT_TESTED')
finally:
    try:
        if changed:
            call('host.update', {'hostid': '10768', 'templates': [{'templateid': '10604'}]}, token)
    finally:
        call('user.logout', [], token)
