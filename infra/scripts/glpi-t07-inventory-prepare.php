<?php
// T07 preparation (docs/operations/glpi-agent-rollout.md). Dry-run (SELECT only) unless --apply.
// Usage: docker exec -i -u www-data [-e GLPI_INVENTORY_BASIC_LOGIN -e GLPI_INVENTORY_BASIC_PASSWORD] ninf-glpi php -- [--apply] < glpi-t07-inventory-prepare.php
// --apply, in one transaction:
//   1. import_process=0, import_registry=0
//   2. auth_required=basic_auth with the credential from the environment (enabled_inventory is NEVER touched; it must be 0)
//   3. purge the leftover July scanner agents (explicit criteria below + exact id list; any mismatch aborts)
// STDOUT (--apply only): rollback JSON (config before, full agent rows, agent log rows, restore SQL). The caller redirects it
// to /opt/n-infraops/rollback/glpi-t07/ BEFORE anything is written. STDERR: status JSON. Secrets are never printed.
$apply = in_array('--apply', $argv, true);
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
global $DB;

const EXPECTED_IDS = [1, 2, 3, 4, 5, 6, 7];
const MIN_IDLE_DAYS = 100;
const CONFIG_NAMES = ['enabled_inventory', 'auth_required', 'basic_auth_login', 'basic_auth_password', 'import_process', 'import_registry'];

function out(array $d): void { fwrite(STDERR, json_encode($d) . PHP_EOL); }
function fail(string $m): never { fwrite(STDERR, "FAIL: $m" . PHP_EOL); exit(1); }
function rows(string $table, array $where): array { global $DB; return array_values(iterator_to_array($DB->request(['FROM' => $table, 'WHERE' => $where]))); }
function sqlval(mixed $v): string { global $DB; return $v === null ? 'NULL' : $DB->quote((string)$v); }
function insert_sql(string $table, array $row): string {
    return sprintf('INSERT INTO `%s` (%s) VALUES (%s);', $table, implode(',', array_map(fn($c) => "`$c`", array_keys($row))), implode(',', array_map('sqlval', $row)));
}

// Explicit criteria: root entity, no linked asset, no version/port/tag, browser User-Agent, idle > MIN_IDLE_DAYS,
// and a hostile payload (SLEEP() in name/deviceid) or a 1-char deviceid. Real GLPI agents never match.
$cutoff = date('Y-m-d H:i:s', time() - MIN_IDLE_DAYS * 86400);
$agents = array_values(array_filter(
    rows('glpi_agents', [
        'entities_id' => 0, 'itemtype' => 'Computer', 'items_id' => 0, 'version' => null, 'port' => null, 'tag' => null,
        'useragent' => ['LIKE', 'Mozilla/%'], 'last_contact' => ['<', $cutoff],
    ]),
    fn($a) => str_contains((string)$a['name'], 'SLEEP(') || str_contains($a['deviceid'], 'SLEEP(') || strlen($a['deviceid']) <= 1
));
$ids = array_map(fn($a) => (int)$a['id'], $agents);
sort($ids);
if ($ids !== EXPECTED_IDS && $ids !== []) fail('agent selection differs from the approved list: ' . json_encode($ids));

foreach (['glpi_rulematchedlogs', 'glpi_unmanageds', 'glpi_refusedequipments'] as $t) {
    if ($ids && rows($t, ['agents_id' => $ids])) fail("$t references the agents; refusing");
}
$logs = $ids ? rows('glpi_logs', ['itemtype' => 'Agent', 'items_id' => $ids]) : [];

$config = [];
foreach (rows('glpi_configs', ['context' => 'inventory', 'name' => CONFIG_NAMES]) as $r) $config[$r['name']] = $r;
if (array_diff(CONFIG_NAMES, array_keys($config))) fail('inventory config rows missing: ' . implode(',', array_diff(CONFIG_NAMES, array_keys($config))));
if ($config['enabled_inventory']['value'] !== '0') fail('enabled_inventory is not 0; refusing');

$login = getenv('GLPI_INVENTORY_BASIC_LOGIN') ?: '';
$password = getenv('GLPI_INVENTORY_BASIC_PASSWORD') ?: '';
$credential = ($login === '' && $password === '') ? 'missing'
    : (preg_match('/^[a-z0-9_-]{3,64}$/', $login) && preg_match('/^[A-Za-z0-9._~-]{32,128}$/', $password) ? 'valid' : 'invalid');

$plan = [
    'agents_to_purge' => $ids, 'agent_log_rows' => count($logs), 'idle_cutoff' => $cutoff,
    'config_now' => ['enabled_inventory' => $config['enabled_inventory']['value'], 'auth_required' => $config['auth_required']['value'],
        'basic_auth_login_set' => $config['basic_auth_login']['value'] !== '', 'basic_auth_password_set' => (string)$config['basic_auth_password']['value'] !== '',
        'import_process' => $config['import_process']['value'], 'import_registry' => $config['import_registry']['value']],
    'config_target' => ['enabled_inventory' => '0 (untouched)', 'auth_required' => 'basic_auth', 'import_process' => '0', 'import_registry' => '0'],
    'credential_env' => $credential,
];
if (!$apply) { out(['mode' => 'dry-run'] + $plan); return; }
if ($credential !== 'valid') fail("--apply needs GLPI_INVENTORY_BASIC_LOGIN [a-z0-9_-]{3,64} and GLPI_INVENTORY_BASIC_PASSWORD [A-Za-z0-9._~-]{32,128} ($credential)");

$restore = [];
foreach (CONFIG_NAMES as $n) {
    if ($n !== 'enabled_inventory') $restore[] = sprintf('UPDATE `glpi_configs` SET `value`=%s WHERE `id`=%d AND `context`=\'inventory\' AND `name`=%s;', sqlval($config[$n]['value']), $config[$n]['id'], sqlval($n));
}
foreach ($agents as $a) $restore[] = insert_sql('glpi_agents', $a);
foreach ($logs as $l) $restore[] = insert_sql('glpi_logs', $l);
fwrite(STDOUT, json_encode([
    'schema' => 'glpi-t07-rollback-v1', 'taken_at' => date('c'), 'criteria' => $plan['idle_cutoff'],
    'config_before' => array_map(fn($r) => ['id' => (int)$r['id'], 'value' => $r['value']], $config),
    'agents' => $agents, 'agent_logs' => $logs, 'restore_sql' => $restore,
], JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR) . PHP_EOL);
fflush(STDOUT);

$DB->beginTransaction();
try {
    Config::setConfigurationValues('inventory', [
        'import_process' => 0, 'import_registry' => 0, 'auth_required' => Glpi\Inventory\Conf::BASIC_AUTH,
        'basic_auth_login' => $login, 'basic_auth_password' => (new GLPIKey())->encrypt($password),
    ]);
    foreach ($ids as $id) {
        if (!(new Agent())->delete(['id' => $id], true)) throw new RuntimeException("agent $id purge refused");
    }
    $DB->commit();
} catch (Throwable $e) {
    $DB->rollBack();
    fail('rolled back: ' . $e->getMessage());
}

$now = [];
foreach (rows('glpi_configs', ['context' => 'inventory', 'name' => CONFIG_NAMES]) as $r) $now[$r['name']] = $r['value'];
if ($now['enabled_inventory'] !== '0' || $now['auth_required'] !== 'basic_auth' || $now['basic_auth_login'] !== $login
    || (new GLPIKey())->decrypt($now['basic_auth_password']) !== $password || $now['import_process'] !== '0' || $now['import_registry'] !== '0') fail('config readback mismatch');
if ($ids && (rows('glpi_agents', ['id' => $ids]) || rows('glpi_logs', ['itemtype' => 'Agent', 'items_id' => $ids]))) fail('agent readback mismatch');
out(['applied' => true, 'purged' => $ids, 'auth_required' => 'basic_auth', 'enabled_inventory' => $now['enabled_inventory'], 'credential_written' => true]);
