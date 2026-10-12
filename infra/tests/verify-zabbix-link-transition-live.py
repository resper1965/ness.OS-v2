#!/usr/bin/env python3
"""Explicit isolated UAT rehearsal; original linkage/macros restored on every path."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import urllib.request
import importlib.util

spec = importlib.util.spec_from_file_location('recovery', Path(__file__).with_name('link-transition-recovery.py'))
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)

if os.geteuid() != 0 or socket.gethostname() != 'zbx-prd-01':
    raise RuntimeError('Isolated UAT only')
for option, expected in [('is-active', 'inactive'), ('is-enabled', 'masked')]:
    if subprocess.run(['systemctl', option, 'zabbix-server'], capture_output=True,
                      text=True).stdout.strip() != expected:
        raise RuntimeError('Isolation required')
if subprocess.run(['ss', '-H', '-ltn', 'sport = :10051'], capture_output=True,
                  text=True, check=True).stdout.strip():
    raise RuntimeError('Collection listener must be absent')
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
MACRO = '{$NET.IF.IFNAME.MATCHES}'


def snapshot(hostid):
    host = call('host.get', {'hostids': [hostid], 'output': ['hostid', 'status'],
        'selectParentTemplates': ['templateid'],
        'selectItems': ['itemid', 'key_', 'status']}, token)[0]
    triggers = call('trigger.get', {'hostids': [hostid], 'output': ['triggerid']}, token)
    macros = call('usermacro.get', {'hostids': [hostid], 'filter': {'macro': MACRO},
                                  'output': ['hostmacroid', 'macro', 'value']}, token)
    return {'templates': sorted(t['templateid'] for t in host['parentTemplates']),
        'status': host['status'], 'items': sorted((i['key_'], i['itemid'], i['status']) for i in host['items']),
        'triggers': sorted(t['triggerid'] for t in triggers), 'macros': macros}


try:
    variants = call('template.get', {'filter': {'host': 'FortiGate by SNMP - UAT link transition'},
                                    'output': ['templateid']}, token)
    if len(variants) != 1:
        raise RuntimeError('Expected one isolated transition template')
    templateid = variants[0]['templateid']
    for hostid, expression in [('10873', '^wan$'), ('10874', '^lan3$')]:
        before = snapshot(hostid)
        if before['templates'] != ['10604'] or before['macros'] or before['status'] != '0':
            raise RuntimeError('Unexpected starting linkage, macro or status')
        if '--apply' not in sys.argv:
            print('link_transition_preflight=PASS; hostid=' + hostid)
            continue
        report = Path('/var/lib/ness-os/restore-evidence/link-transition-test-' + hostid + '-20261012.json')
        if report.exists():
            raise RuntimeError('Existing evidence; do not repeat without change')
        with report.open('x') as output:
            json.dump({'before': before, 'result': 'STARTED'}, output)
        changed = False
        after, failure, restored = None, None, None
        try:
            changed = True  # Return even if a successful write loses its response.
            call('host.update', {'hostid': hostid, 'templates': [{'templateid': templateid}]}, token)
            rule = call('discoveryrule.get', {'hostids': [hostid],
                'filter': {'key_': 'net.if.discovery'}, 'output': ['itemid', 'lifetime_type']}, token)
            if len(rule) != 1 or rule[0]['lifetime_type'] != '1':
                raise RuntimeError('Lost resources are not protected; no filter write')
            call('usermacro.create', {'hostid': hostid, 'macro': MACRO, 'value': expression}, token)
            after = snapshot(hostid)
            if (after['templates'] != [templateid] or len(after['macros']) != 1
                    or after['macros'][0]['value'] != expression
                    or any(after[k] != before[k] for k in ['items', 'triggers', 'status'])):
                raise RuntimeError('Link transition changed IDs/status or filter mismatch')
        except Exception as error:
            failure = type(error).__name__
        finally:
            if changed:
                compensation = recovery.recover_link(call, hostid, '10604', token)
                try:
                    restored = snapshot(hostid)
                except Exception:
                    failure = failure or 'ReadbackUnavailable'
                passed = failure is None and compensation['restored'] and restored == before
                with report.open('w') as output:
                    json.dump({'before': before, 'after': after, 'restored': restored,
                        'result': 'PASS' if passed else 'FAIL', 'failure': failure,
                        'compensation': compensation, 'collection_tested': False}, output)
        if not passed:
            raise RuntimeError('Rehearsal/rollback incomplete; keep collection off and inspect protected evidence')
        print('link_transition=PASS; hostid=' + hostid + '; items=' + str(len(before['items']))
              + '; triggers=' + str(len(before['triggers'])) + '; ids_preserved=true; rollback=PASS')
finally:
    call('user.logout', [], token)
