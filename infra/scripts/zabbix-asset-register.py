"""Sanitized, complete asset coverage register; no health inferred from zero errors."""
from datetime import datetime
import json
from pathlib import Path
import subprocess
import os
import socket
import runpy

summarize_freshness = runpy.run_path(str(Path(__file__).with_name('zabbix-freshness.py')))['summarize_freshness']

REQUIRED_TAGS = ('tenant', 'site', 'service', 'environment', 'technology',
                 'scope', 'owner', 'role', 'criticality')


def build_register(rows, observed_at):
    stamp = datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
    if stamp.tzinfo is None or not rows:
        raise ValueError('Timestamp must identify timezone and scope must not be empty')
    assets, prototypes, seen = [], [], set()
    for row in sorted(rows, key=lambda r: int(r['hostid'])):
        hostid = str(row['hostid'])
        flags, status = int(row['flags']), int(row['status'])
        items, errors = int(row['item_count']), int(row['unsupported_count'])
        enabled = int(row['enabled_item_count'])
        if (not hostid.isdigit() or int(hostid) <= 0 or hostid in seen
                or flags not in (0, 2, 4) or status not in (0, 1)
                or items < 0 or not 0 <= errors <= enabled <= items):
            raise ValueError('Invalid or duplicate asset identity/status/counters')
        seen.add(hostid)
        tags = [dict(t) for t in row.get('tags', []) if t['tag'] in REQUIRED_TAGS]
        values = {k: {t['value'] for t in tags if t['tag'] == k and t['value']}
                  for k in REQUIRED_TAGS}
        clean = {'hostid': hostid, 'flags': flags, 'status': status,
                 'name': row['name'], 'templates': row.get('templates', []),
                 'tags': tags, 'item_count': items, 'unsupported_count': errors,
                 'enabled_item_count': enabled,
                 'freshness': summarize_freshness(row.get('essential_metrics', []), int(stamp.timestamp())),
                 'error_categories': row.get('error_categories', {}),
                 'missing_tags': [k for k, v in values.items() if not v],
                 'conflicted_tags': sorted(k for k, v in values.items() if len(v) > 1),
                 'state': ('prototype_review_required' if flags == 2 else
                           'disabled_preserved' if status == 1 else
                           'unconfigured' if items == 0 else
                           'needs_remediation' if errors else 'assessment_required')}
        if flags == 2:
            lld = row.get('lld', {})
            clean['lld'] = {k: lld.get(k) for k in ('ruleid', 'rule_flags',
                'rule_status', 'parent_hostid', 'parent_status', 'parent_flags')}
            clean['lld']['state'] = ('REFERENCES_VALID_NOT_COLLECTION_ACCEPTANCE'
                if lld.get('ruleid') and lld.get('parent_hostid')
                and lld.get('rule_flags') == 1 and lld.get('rule_status') in (0, 1)
                and lld.get('parent_status') in (0, 1, 3)
                and lld.get('parent_flags') in (0, 4) else 'UNKNOWN')
        (prototypes if flags == 2 else assets).append(clean)
    waves = [[h['hostid'] for h in assets[i:i + 5]] for i in range(0, len(assets), 5)]
    enabled_total = sum(h['enabled_item_count'] for h in assets if h['status'] == 0)
    unsupported_total = sum(h['unsupported_count'] for h in assets if h['status'] == 0)
    return {'observed_at': observed_at, 'source': 'origin_readonly_configuration_and_runtime',
            'fresh_collection': 'ESSENTIAL_PULSES_ONLY_NOT_HEALTH_ACCEPTANCE',
            'freshness_scope': ['agent.ping', 'icmpping', 'system.uptime'],
            'assets': assets, 'prototypes': prototypes,
            'waves': waves, 'totals': {'real_hosts': len(assets), 'prototypes': len(prototypes),
                'active': sum(h['status'] == 0 for h in assets),
                'disabled': sum(h['status'] == 1 for h in assets), 'accepted': 0,
                'unsupported_active': unsupported_total, 'enabled_items_active': enabled_total,
                'unsupported_rate_active': unsupported_total / enabled_total if enabled_total else None}}


def collect_rows():
    """Read configuration/rtdata only; never select credentials or raw errors."""
    if os.geteuid() != 0 or socket.gethostname() != 'zabbix-srv01':
        raise RuntimeError('Collector requires protected origin configuration')
    config = {}
    for line in Path('/etc/zabbix/zabbix_server.conf').read_text().splitlines():
        if line.startswith(('DBUser=', 'DBName=', 'DBPassword=')):
            key, value = line.split('=', 1)
            config[key] = value
    category = """CASE
      WHEN LOWER(rt.error) REGEXP 'auth|unauthorized|credential|password' THEN 'authentication'
      WHEN LOWER(rt.error) REGEXP 'timeout|timed out' THEN 'timeout'
      WHEN LOWER(rt.error) REGEXP 'preprocess|jsonpath|xpath|javascript' THEN 'preprocessing'
      WHEN LOWER(rt.error) REGEXP 'dns|resolve|network|connect|unreachable|no route' THEN 'connectivity'
      WHEN LOWER(rt.error) REGEXP 'calculated|formula|expression|division by zero' THEN 'calculation'
      WHEN LOWER(rt.error) REGEXP 'unknown metric|unsupported key|invalid key|oid|snmp' THEN 'key_metric_oid'
      ELSE 'other' END"""
    sql = """START TRANSACTION READ ONLY;
      SELECT JSON_OBJECT('kind','host','hostid',h.hostid,'flags',h.flags,'status',h.status,'name',h.name,
        'templates',COALESCE((SELECT JSON_ARRAYAGG(t.host) FROM hosts_templates ht JOIN hosts t ON t.hostid=ht.templateid WHERE ht.hostid=h.hostid),JSON_ARRAY()),
        'tags',COALESCE((SELECT JSON_ARRAYAGG(JSON_OBJECT('tag',tag,'value',value)) FROM host_tag WHERE hostid=h.hostid AND tag IN ('tenant','site','service','environment','technology','scope','owner','role','criticality')),JSON_ARRAY()))
        FROM hosts h WHERE h.status IN (0,1) ORDER BY h.hostid;
      SELECT JSON_OBJECT('kind','metrics','hostid',i.hostid,'item_count',COUNT(*),
        'enabled_item_count',SUM(i.status=0),
        'unsupported_count',SUM(i.status=0 AND COALESCE(rt.state,0)=1))
        FROM items i LEFT JOIN item_rtdata rt ON rt.itemid=i.itemid
        JOIN hosts h ON h.hostid=i.hostid WHERE h.status IN (0,1) AND i.flags IN (0,4) GROUP BY i.hostid;
      SELECT JSON_OBJECT('kind','category','hostid',i.hostid,'category',CATEGORY,'count',COUNT(*))
        FROM items i JOIN item_rtdata rt ON rt.itemid=i.itemid JOIN hosts h ON h.hostid=i.hostid
        WHERE h.status IN (0,1) AND i.flags IN (0,4) AND i.status=0 AND rt.state=1
        GROUP BY i.hostid,CATEGORY;
      SELECT JSON_OBJECT('kind','pulse','hostid',i.hostid,'itemid',i.itemid,
        'delay',CASE WHEN i.type=18 THEN master.delay ELSE i.delay END,
        'state',COALESCE(rt.state,0),'lastclock',CASE i.value_type
          WHEN 3 THEN (SELECT MAX(clock) FROM history_uint WHERE itemid=i.itemid)
          WHEN 0 THEN (SELECT MAX(clock) FROM history WHERE itemid=i.itemid)
          ELSE NULL END)
        FROM items i JOIN hosts h ON h.hostid=i.hostid
        LEFT JOIN items master ON master.itemid=i.master_itemid
        LEFT JOIN item_rtdata rt ON rt.itemid=i.itemid
        WHERE h.status IN (0,1) AND i.flags IN (0,4) AND i.status=0
          AND i.key_ IN ('agent.ping','icmpping','system.uptime');
      SELECT JSON_OBJECT('kind','lld','hostid',h.hostid,'ruleid',i.itemid,
        'rule_flags',i.flags,'rule_status',i.status,'parent_hostid',p.hostid,
        'parent_status',p.status,'parent_flags',p.flags)
        FROM hosts h LEFT JOIN host_discovery hd ON hd.hostid=h.hostid
        LEFT JOIN items i ON i.itemid=hd.parent_itemid
        LEFT JOIN hosts p ON p.hostid=i.hostid
        WHERE h.flags=2 AND h.status IN (0,1);
      COMMIT;""".replace('CATEGORY', category)
    env = dict(os.environ, MYSQL_PWD=config['DBPassword'])
    result = subprocess.run(['mariadb', '--batch', '--raw', '--skip-column-names',
        '--user=' + config['DBUser'], config['DBName'], '-e', sql], env=env,
        capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Read-only inventory query failed; inspect protected DB diagnostics')
    hosts = {}
    for line in result.stdout.splitlines():
        row = json.loads(line)
        hostid = str(row['hostid'])
        if row['kind'] == 'host':
            row.update(item_count=0, enabled_item_count=0, unsupported_count=0, error_categories={})
            hosts[hostid] = row
        elif row['kind'] == 'metrics':
            hosts[hostid].update(item_count=row['item_count'], enabled_item_count=row['enabled_item_count'],
                                 unsupported_count=row['unsupported_count'])
        elif row['kind'] == 'pulse':
            hosts[hostid].setdefault('essential_metrics', []).append({
                'itemid': str(row['itemid']), 'delay': row['delay'],
                'state': int(row['state']),
                'lastclock': int(row['lastclock']) if row['lastclock'] is not None else None})
        elif row['kind'] == 'lld':
            hosts[hostid]['lld'] = {k: row[k] for k in ('ruleid', 'rule_flags',
                'rule_status', 'parent_hostid', 'parent_status', 'parent_flags')}
        else:
            hosts[hostid]['error_categories'][row['category']] = row['count']
    return list(hosts.values())


if __name__ == '__main__':
    from datetime import timezone
    try:
        report = build_register(collect_rows(), datetime.now(timezone.utc).isoformat())
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception as error:
        raise SystemExit('Asset register failed: ' + type(error).__name__)
