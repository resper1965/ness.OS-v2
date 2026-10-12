"""Compensation helper for the explicit live integration rehearsal only."""


def recover_link(call, hostid, original_template, token):
    errors, filter_absent, template_restored = [], False, False
    query = {'hostids': [hostid], 'filter': {'macro': '{$NET.IF.IFNAME.MATCHES}'},
             'output': ['hostmacroid']}
    for attempt in range(2):
        try:
            macros = call('usermacro.get', query, token)
            if not macros:
                filter_absent = True
                break
        except Exception:
            errors.append('usermacro.get')
            continue
        try:
            call('usermacro.delete', [m['hostmacroid'] for m in macros], token)
        except Exception:
            errors.append('usermacro.delete')
        try:
            if not call('usermacro.get', query, token):
                filter_absent = True
                break
        except Exception:
            errors.append('usermacro.get')
    if filter_absent:
        for attempt in range(2):
            try:
                call('host.update', {'hostid': hostid,
                    'templates': [{'templateid': original_template}]}, token)
            except Exception:
                errors.append('host.update')
            try:
                hosts = call('host.get', {'hostids': [hostid], 'output': ['hostid'],
                                         'selectParentTemplates': ['templateid']}, token)
                if len(hosts) == 1 and [t['templateid'] for t in hosts[0]['parentTemplates']] == [original_template]:
                    template_restored = True
                    break
            except Exception:
                errors.append('host.get')
    return {'restored': filter_absent and template_restored, 'filter_absent': filter_absent,
            'template_restored': template_restored, 'errors': errors}
