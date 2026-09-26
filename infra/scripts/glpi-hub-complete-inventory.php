<?php
// Execute with the reviewed JSON reconciliation report mounted at /tmp/hub-cmdb-plan.json.
if (!in_array('--apply', $argv, true)) {
    echo json_encode(['mode' => 'preview', 'write_required' => '--apply']) . PHP_EOL;
    exit;
}
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel(); $kernel->boot(); global $DB;
$plan = json_decode(file_get_contents('/tmp/hub-cmdb-plan.json'), true, flags: JSON_THROW_ON_ERROR);
Session::callAsSystem(function () use ($plan, $DB) {
    foreach ($plan['gaps'] as $gap) {
        if (($gap['reason'] ?? '') !== 'missing_glpi') continue;
        $hostid = $gap['host_id'];
        $name = $gap['name'];
        $role = $gap['tags']['role'] ?? '';
        if ($role === 'firewall') $type = NetworkEquipment::class;
        elseif ($role === 'virtual-server' || str_contains($name, '[ Servidor ') || $hostid === '10972') $type = Computer::class;
        else { echo json_encode(['skipped' => $hostid, 'reason' => 'unclassified']).PHP_EOL; continue; }
        $marker = 'Zabbix Host ID: '.$hostid;
        $found = false;
        foreach ([Computer::class, NetworkEquipment::class] as $candidate) {
            foreach ($DB->request(['FROM' => $candidate::getTable()]) as $row) {
                if (preg_match('/Zabbix Host ID:\s*(\d+)/', $row['comment'] ?? '', $m) && $m[1] === $hostid) $found = true;
            }
        }
        if ($found) continue;
        $item = new $type();
        $input = ['name' => $name, 'entities_id' => (int)$gap['entity'], 'is_recursive' => 0,
                  'comment' => $marker."\nSource: Zabbix monitored identity, reconciled 2026-09-08. Hardware inventory pending."];
        $id = $item->add($input);
        if (!$id) throw new RuntimeException('GLPI create failed for '.$hostid);
        echo json_encode(['host_id' => $hostid, 'itemtype' => $type, 'id' => $id, 'entity' => $gap['entity']]).PHP_EOL;
    }
});
