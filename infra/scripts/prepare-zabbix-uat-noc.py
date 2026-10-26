#!/usr/bin/env python3
"""Preserve dashboard 405 and create an explicitly historical private UAT copy."""
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
    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.load(response)
    if 'error' in result:
        raise RuntimeError('API rejected ' + method)
    return result['result']

token = call('user.login', {'username': 'ness_uat_breakglass', 'password':
    Path('/etc/ness-os/zabbix-uat-recovery.password').read_text().strip()})
try:
    query = {'dashboardids': ['405'], 'output': 'extend', 'selectPages': 'extend'}
    source = call('dashboard.get', query, token)[0]
    pages = []
    for page in source['pages']:
        widgets = []
        for widget in page['widgets']:
            clean = {k: widget[k] for k in ['type', 'name', 'x', 'y', 'width', 'height', 'view_mode']}
            clean['fields'] = [{k: f[k] for k in ['type', 'name', 'value']} for f in widget['fields']]
            if int(clean['width']) <= 0 or int(clean['height']) <= 0:
                raise RuntimeError('Invalid widget dimensions')
            widgets.append(clean)
        pages.append({'name': page['name'], 'display_period': page['display_period'], 'widgets': widgets})
    candidate = {'name': 'UAT — NOC (snapshot 11/10/2026; sem coleta)',
                 'userid': source['userid'], 'private': 1, 'pages': pages}
    existing = call('dashboard.get', {'filter': {'name': candidate['name']}, 'output': ['dashboardid']}, token)
    if '--apply' not in sys.argv:
        print('noc_preflight=PASS; pages='+str(len(pages))+'; widgets='+str(sum(len(p['widgets']) for p in pages)))
    elif existing:
        print('noc_candidate=EXISTS; dashboardid='+existing[0]['dashboardid'])
    else:
        backup = Path('/var/lib/ness-os/restore-evidence/noc-405-before-20261012.json')
        with backup.open('x') as output:
            json.dump(source, output)
        created = call('dashboard.create', candidate, token)
        if call('dashboard.get', query, token)[0] != source:
            raise RuntimeError('Original dashboard drift; investigate')
        result = call('dashboard.get', {'dashboardids': created['dashboardids'],
            'output': ['dashboardid', 'private'], 'selectPages': 'extend'}, token)[0]
        if str(result['private']) != '1' or sum(len(p['widgets']) for p in result['pages']) != 32:
            raise RuntimeError('Candidate verification failed')
        print('noc_candidate=PASS; private=true; original_unchanged=true; dashboardid='+result['dashboardid'])
finally:
    call('user.logout', [], token)
