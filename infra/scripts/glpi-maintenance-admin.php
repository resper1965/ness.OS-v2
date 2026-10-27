<?php
// Usage: docker exec -i ninf-glpi php -- <cmd> [flags] < glpi-maintenance-admin.php
//   apiclient [--apply] [--reset-token]   create/update the gateway API client (IP-pinned)
//   profile   [--apply]                   reduce the maintenance profile to computer=READ
//   rotate    [--apply]                   regenerate the maintenance user's api_token
//   user --activate|--deactivate          flip is_active
//   client --id=N --activate|--deactivate flip is_active of an existing API client (readback of the full row)
// Secrets go to STDOUT only (caller redirects to a 0600 file); status/readback JSON goes to STDERR.
// Defaults are production; override with --user= --user-name= --profile= --profile-name= --client-name= --ip= --entity= --recursive= (the only profile binding `user --activate` accepts).
// Dry-run unless --apply (user: the flag itself is the intent).
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
global $DB;

$cmd = $argv[1] ?? '';
$opt = ['user' => '106', 'user-name' => 'svc_ness_maintenance', 'profile' => '13', 'profile-name' => 'ness-maintenance-alupar',
    'client-name' => 'ness-os-maintenance-gateway', 'ip' => '172.30.250.3', 'entity' => '1', 'recursive' => '0'];
$flags = [];
foreach (array_slice($argv, 2) as $a) {
    if (preg_match('/^--([a-z-]+)=(.*)$/', $a, $m)) $opt[$m[1]] = $m[2];
    else $flags[] = $a;
}
$apply = in_array('--apply', $flags, true);

function out(array $d): void { fwrite(STDERR, json_encode($d) . PHP_EOL); }
function fail(string $m): never { fwrite(STDERR, "FAIL: $m" . PHP_EOL); exit(1); }
function one(string $table, array $where): ?array {
    global $DB;
    $rows = iterator_to_array($DB->request(['FROM' => $table, 'WHERE' => $where]));
    return $rows ? reset($rows) : null;
}
function user(array $opt): array {
    $u = one('glpi_users', ['id' => (int)$opt['user']]);
    if (!$u || $u['name'] !== $opt['user-name']) fail('user id/name mismatch');
    return $u;
}
function new_updater(string $class, array $input) {
    $o = new $class();
    return $o->update($input) ? true : fail("$class update refused");
}

Session::callAsSystem(function () use ($cmd, $opt, $flags, $apply, $DB) {
    $_SESSION['glpi_currenttime'] ??= date('Y-m-d H:i:s');
    $key = new GLPIKey();
    switch ($cmd) {
    case 'apiclient':
        if (!filter_var($opt['ip'], FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) fail('invalid ip');
        $c = one('glpi_apiclients', ['name' => $opt['client-name']]);
        $reset = in_array('--reset-token', $flags, true);
        $want = ['is_active' => 1, 'ipv4_range_start' => ip2long($opt['ip']), 'ipv4_range_end' => ip2long($opt['ip'])];
        $plan = !$c ? 'create' : ($reset || array_diff_assoc(array_map('intval', $want), array_map('intval', array_intersect_key($c, $want))) ? 'update' : 'none');
        if (!$apply) { out(['mode' => 'dry-run', 'action' => $plan]); return; }
        if ($plan !== 'none') {
            $token = (!$c || $reset) ? APIClient::getUniqueAppToken() : null;
            $in = ['name' => $opt['client-name'], 'is_active' => 1, 'ipv4_range_start' => $opt['ip'], 'ipv4_range_end' => $opt['ip'],
                'entities_id' => 0, 'dolog_method' => 0, 'comment' => 'ness.OS maintenance gateway only (ADR 0020)'];
            if ($token) $in['app_token'] = $token;
            $o = new APIClient();
            if ($c) { $in['id'] = $c['id']; $o->update($in) or fail('apiclient update refused'); }
            else { $in['id'] = $o->add($in) ?: fail('apiclient add refused'); }
            if ($token) {
                if ($key->decrypt(one('glpi_apiclients', ['id' => $in['id']])['app_token']) !== $token) fail('app_token readback mismatch');
                fwrite(STDOUT, $token);
            }
        }
        $c = one('glpi_apiclients', ['name' => $opt['client-name']]) ?: fail('apiclient missing after apply');
        if ((int)$c['is_active'] !== 1 || (int)$c['ipv4_range_start'] !== $want['ipv4_range_start'] || (int)$c['ipv4_range_end'] !== $want['ipv4_range_end'] || $c['ipv6'] !== null) fail('apiclient readback mismatch');
        out(['action' => $plan, 'id' => (int)$c['id'], 'ipv4' => long2ip((int)$c['ipv4_range_start']) . '-' . long2ip((int)$c['ipv4_range_end']), 'token_written' => $plan === 'create' || $reset]);
        return;

    case 'profile':
        $p = one('glpi_profiles', ['id' => (int)$opt['profile']]);
        if (!$p || $p['name'] !== $opt['profile-name']) fail('profile id/name mismatch');
        $rights = function () use ($DB, $opt) {
            $r = [];
            foreach ($DB->request(['FROM' => 'glpi_profilerights', 'WHERE' => ['profiles_id' => (int)$opt['profile'], 'rights' => ['>', 0]]]) as $x) $r[$x['name']] = (int)$x['rights'];
            ksort($r);
            return $r;
        };
        $before = $rights();
        if (!$apply) { out(['mode' => 'dry-run', 'rights' => $before, 'target' => ['computer' => 1]]); return; }
        $DB->update('glpi_profilerights', ['rights' => 0], ['profiles_id' => (int)$opt['profile'], 'rights' => ['>', 0], 'NOT' => ['name' => 'computer']]);
        $DB->update('glpi_profilerights', ['rights' => 1], ['profiles_id' => (int)$opt['profile'], 'name' => 'computer']);
        $after = $rights();
        if ($after !== ['computer' => 1]) fail('profile readback mismatch: ' . json_encode($after));
        out(['before' => $before, 'after' => $after]);
        return;

    case 'rotate':
        $u = user($opt);
        if (!$apply) { out(['mode' => 'dry-run', 'api_token_date' => $u['api_token_date']]); return; }
        new_updater(User::class, ['id' => $u['id'], '_reset_api_token' => 1]);
        $n = one('glpi_users', ['id' => $u['id']]);
        $token = $key->decrypt($n['api_token'] ?? '');
        if (strlen($token) !== 40 || $n['api_token_date'] === $u['api_token_date'] && $n['api_token'] === $u['api_token']) fail('rotation readback mismatch');
        fwrite(STDOUT, $token);
        out(['rotated' => true, 'api_token_date' => $n['api_token_date']]);
        return;

    case 'user':
        $u = user($opt);
        $want = in_array('--activate', $flags, true) ? 1 : (in_array('--deactivate', $flags, true) ? 0 : fail('need --activate or --deactivate'));
        $links = iterator_to_array($DB->request(['FROM' => 'glpi_profiles_users', 'WHERE' => ['users_id' => (int)$u['id']]]));
        $l = reset($links);
        if ($want === 1 && (count($links) !== 1 || (int)$l['profiles_id'] !== (int)$opt['profile'] || (int)$l['entities_id'] !== (int)$opt['entity'] || (int)$l['is_recursive'] !== (int)$opt['recursive']))
            fail('profile bindings are not exactly [profile, entity, recursive]; refusing to activate');
        if ((int)$u['is_active'] !== $want) new_updater(User::class, ['id' => $u['id'], 'is_active' => $want]);
        $n = one('glpi_users', ['id' => $u['id']]);
        if ((int)$n['is_active'] !== $want) fail('user readback mismatch');
        out(['user' => (int)$u['id'], 'is_active' => $want, 'profiles' => array_map(fn($l) => [(int)$l['profiles_id'], (int)$l['entities_id'], (int)$l['is_recursive']], array_values($links))]);
        return;

    case 'client':
        $c = one('glpi_apiclients', ['id' => (int)($opt['id'] ?? 0)]) ?: fail('client not found');
        $want = in_array('--activate', $flags, true) ? 1 : (in_array('--deactivate', $flags, true) ? 0 : fail('need --activate or --deactivate'));
        if ((int)$c['is_active'] !== $want) (new APIClient())->update(['id' => $c['id'], 'is_active' => $want]) or fail('client update refused');
        $n = one('glpi_apiclients', ['id' => $c['id']]);
        if ((int)$n['is_active'] !== $want) fail('client readback mismatch');
        out(['client' => (int)$n['id'], 'name' => $n['name'], 'is_active' => $want, 'ipv4' => $n['ipv4_range_start'] === null ? null : long2ip((int)$n['ipv4_range_start']) . '-' . long2ip((int)$n['ipv4_range_end'])]);
        return;

    default:
        fail('usage: apiclient|profile|rotate|user|client');
    }
});
