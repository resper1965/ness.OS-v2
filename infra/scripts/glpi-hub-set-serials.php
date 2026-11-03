<?php
// Grava serial só em NetworkEquipment sem serial e com o marcador "Zabbix Host ID" esperado.
// Plano fixo e revisado (fonte: item system.hw.serialnumber do Zabbix, lido em 03/11).
$plan = [157 => ['host' => '10988', 'serial' => 'FG200E4Q17909933'], 158 => ['host' => '10997', 'serial' => 'FGT60FTK2109B0AR']];
if (!in_array('--apply', $argv, true)) { echo json_encode(['mode' => 'preview', 'plan' => $plan]) . PHP_EOL; exit; }
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel(); $kernel->boot();
Session::callAsSystem(function () use ($plan) {
    foreach ($plan as $id => $p) {
        $ne = new NetworkEquipment();
        if (!$ne->getFromDB($id)) throw new RuntimeException("Missing $id");
        if (!preg_match('/Zabbix Host ID:\s*(\d+)/', $ne->fields['comment'] ?? '', $m) || $m[1] !== $p['host']) throw new RuntimeException("Marker mismatch $id");
        if (($ne->fields['serial'] ?? '') !== '') { echo json_encode(['id' => $id, 'skipped' => 'serial already set']) . PHP_EOL; continue; }
        if (!$ne->update(['id' => $id, 'serial' => $p['serial']])) throw new RuntimeException("Update failed $id");
        echo json_encode(['id' => $id, 'serial' => $p['serial']]) . PHP_EOL;
    }
});
