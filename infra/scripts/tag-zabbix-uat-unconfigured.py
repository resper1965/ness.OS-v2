#!/usr/bin/env python3
"""Apply or roll back one five-host factual collection-quality wave in UAT."""
import importlib.util
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
spec = importlib.util.spec_from_file_location('wave', Path(__file__).with_name('zabbix-quality-wave.py'))
wave = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wave)
hostids = ['10740', '10741', '10742', '10743', '10744']
plan_file = Path('/var/lib/ness-os/restore-evidence/unconfigured-wave-1-20261012.json')

class Api:
    def call(self, method, params, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request('http://127.0.0.1:8080/zabbix/api_jsonrpc.php',
            data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode(),
            headers=headers)
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
        if 'error' in data:
            raise RuntimeError('API rejected ' + method)
        return data['result']

    def get(self, ids):
        hosts = self.call('host.get', {'hostids': ids, 'output': ['hostid', 'flags'],
            'selectTags': ['tag', 'value'], 'selectParentTemplates': ['templateid'],
            'selectItems': 'count'}, self.token)
        if len(hosts) != len(ids) or any(int(h['items']) != 0 or int(h['flags']) != 0
                                       or h['parentTemplates'] for h in hosts):
            raise RuntimeError('Host collection configuration changed; no further writes')
        return hosts

    def update(self, payload):
        # These hosts have no linked template; apply tags only, never template fields.
        self.call('host.update', {'hostid': payload['hostid'], 'tags': payload['tags']}, self.token)

api = Api()
api.token = api.call('user.login', {'username': 'ness_uat_breakglass', 'password':
    Path('/etc/ness-os/zabbix-uat-recovery.password').read_text().strip()})
try:
    hosts = api.get(hostids)
    if plan_file.exists():
        plan = json.loads(plan_file.read_text())
        if [row['before']['hostid'] for row in plan] != hostids:
            raise RuntimeError('Wrong wave identity')
    else:
        plan = wave.make_plan(hosts, [{'hostid': h, 'tags': {'collection_state': 'unconfigured'}} for h in hostids])
    if '--apply' not in sys.argv:
        print('wave_preflight=PASS; hosts=5; zero_items=true; mode=preview')
    else:
        if not plan_file.exists():
            with plan_file.open('x') as output:
                json.dump(plan, output)
        wave.apply_plan(api, plan, rollback='--rollback' in sys.argv)
        print('quality_wave=PASS; hosts=5; rollback='+str('--rollback' in sys.argv))
finally:
    api.call('user.logout', [], api.token)
