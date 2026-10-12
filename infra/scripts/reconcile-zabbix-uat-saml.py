#!/usr/bin/env python3
"""Reconcile only isolated UAT SAML via normal authenticated API."""
import base64
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET

if os.geteuid() != 0 or socket.gethostname() != 'zbx-prd-01':
    raise RuntimeError('Requires root on isolated UAT')
for option, expected in [('is-active', 'inactive'), ('is-enabled', 'masked')]:
    if subprocess.run(['systemctl', option, 'zabbix-server'], capture_output=True,
                      text=True).stdout.strip() != expected:
        raise RuntimeError('Isolation required')
os.umask(0o077)
metadata_url = 'https://sso.ness.com.br/application/saml/zabbix-uat/metadata/'
with urllib.request.urlopen(metadata_url, timeout=20) as response:
    if response.geturl() not in (metadata_url,
            'https://sso.ness.com.br/api/v3/providers/saml/13/metadata/?download'):
        raise RuntimeError('Unexpected metadata redirect')
    root = ET.fromstring(response.read())
ns = {'md': 'urn:oasis:names:tc:SAML:2.0:metadata',
      'ds': 'http://www.w3.org/2000/09/xmldsig#'}
sso = root.find(".//md:SingleSignOnService[@Binding='urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect']", ns)
certs = root.findall('.//md:KeyDescriptor[@use="signing"]//ds:X509Certificate', ns)
certificate_path = Path('/usr/share/zabbix/conf/certs/idp.crt')
original_certificate = certificate_path.read_text()
installed = ssl.PEM_cert_to_DER_cert(original_certificate)
if not certs:
    raise RuntimeError('No signing certificate in trusted metadata')
replacement = ssl.DER_cert_to_PEM_cert(base64.b64decode(certs[0].text))
certificate_change = ssl.PEM_cert_to_DER_cert(replacement) != installed
if sso is None or sso.get('Location') != 'https://sso.ness.com.br/application/saml/zabbix-uat/':
    raise RuntimeError('Unexpected UAT endpoint')
desired = {'userdirectoryid': '1', 'idp_entityid': root.get('entityID'),
           'sso_url': sso.get('Location'), 'sp_entityid': 'https://zabbix-uat.ness.com.br'}
if desired['idp_entityid'] != metadata_url:
    raise RuntimeError('Unexpected issuer')

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
    row = call('userdirectory.get', {'userdirectoryids': ['1'], 'output': 'extend'}, token)[0]
    before = {k: row[k] for k in desired}
    if '--apply' not in sys.argv:
        print('saml_preflight=PASS; certificate_replacement_required='+str(certificate_change)+'; mode=preview')
    elif before == desired and not certificate_change:
        print('saml_configuration=PASS; unchanged=true')
    else:
        rollback = Path('/var/lib/ness-os/restore-evidence/saml-before-20261012.json')
        with rollback.open('x') as output:
            json.dump(before, output)
        certificate_backup = Path('/var/lib/ness-os/restore-evidence/idp-before-20261012.crt')
        with certificate_backup.open('x') as output:
            output.write(original_certificate)
        try:
            if certificate_change:
                certificate_path.write_text(replacement)
            call('userdirectory.update', desired, token)
        except Exception:
            certificate_path.write_text(original_certificate)
            raise
        after = call('userdirectory.get', {'userdirectoryids': ['1'], 'output': 'extend'}, token)[0]
        if any(after[k] != v for k, v in desired.items()):
            raise RuntimeError('Configuration verification failed; rollback preserved')
        print('saml_configuration=PASS; nominal_login=NOT_TESTED')
finally:
    call('user.logout', [], token)
