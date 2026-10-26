<?php
// Read-only preflight. Run inside GLPI; the output file contains full rollback evidence.
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
global $DB;
$destination = $argv[1] ?? '/tmp/cavan-vm-migration-audit.json';
if (file_exists($destination)) {
    throw new RuntimeException('Refusing to overwrite previous evidence');
}
$expected = [120 => '10882', 121 => '10883', 122 => '10884'];
$report = ['generated_at' => gmdate('c'), 'mode' => 'read-only', 'assets' => [], 'references' => [], 'blockers' => []];
$computerColumns = $DB->listFields(Computer::getTable());
foreach ($expected as $id => $host) {
    $asset = new NetworkEquipment();
    if (!$asset->getFromDB($id)) {
        throw new RuntimeException('Missing source '.$id);
    }
    $row = $asset->fields;
    if ((int)$row['entities_id'] !== 8 || (int)$row['is_deleted'] !== 0
        || !preg_match('/Zabbix Host ID:\s*(\d+)/', $row['comment'] ?? '', $match)
        || $match[1] !== $host) {
        $report['blockers'][] = 'Source identity or lifecycle changed: '.$id;
    }
    $model = new NetworkEquipmentModel();
    $modelName = $model->getFromDB((int)$row['networkequipmentmodels_id']) ? $model->fields['name'] : null;
    $targetModels = $modelName === null ? [] : array_values(iterator_to_array($DB->request([
        'FROM' => ComputerModel::getTable(), 'WHERE' => ['name' => $modelName],
    ])));
    $report['assets'][] = [
        'host_id' => $host, 'source' => $row,
        'source_model_name' => $modelName,
        'computer_model_candidates' => $targetModels,
        'fields_without_computer_column' => array_diff_key($row, $computerColumns),
    ];
    foreach ([Computer::class, NetworkEquipment::class] as $type) {
        foreach ($DB->request(['FROM' => $type::getTable()]) as $candidate) {
            if ($type === NetworkEquipment::class && (int)$candidate['id'] === $id) {
                continue;
            }
            if (preg_match('/Zabbix Host ID:\s*(\d+)/', $candidate['comment'] ?? '', $m) && $m[1] === $host) {
                $report['blockers'][] = 'Duplicate identity '.$host.' on '.$type.' '.$candidate['id'];
            }
        }
    }
}
foreach ($DB->listTables('glpi_%') as $tableRow) {
    $table = array_values($tableRow)[0];
    $columns = $DB->listFields($table);
    $conditions = [];
    foreach (['', '_1', '_2'] as $suffix) {
        $type = 'itemtype'.$suffix;
        $item = 'items_id'.$suffix;
        if (isset($columns[$type], $columns[$item])) {
            $conditions[$type] = [$type => NetworkEquipment::class, $item => array_keys($expected)];
        }
    }
    foreach (array_keys($columns) as $column) {
        if (preg_match('/^networkequipments_id(?:_|$)/', $column)) {
            $conditions[$column] = [$column => array_keys($expected)];
        }
    }
    foreach ($conditions as $via => $where) {
        $rows = array_values(iterator_to_array($DB->request(['FROM' => $table, 'WHERE' => $where])));
        if (!$rows) {
            continue;
        }
        $report['references'][] = ['table' => $table, 'via' => $via, 'rows' => $rows];
        if ($table !== 'glpi_logs') {
            $report['blockers'][] = 'Relation needs an explicit migration handler: '.$table.' via '.$via;
        }
    }
}
$report['blockers'] = array_values(array_unique($report['blockers']));
umask(0077);
$handle = fopen($destination, 'x');
if (!$handle) {
    throw new RuntimeException('Cannot create evidence file');
}
fwrite($handle, json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR).PHP_EOL);
fclose($handle);
echo json_encode([
    'mode' => 'read-only', 'assets' => count($report['assets']),
    'reference_sets' => count($report['references']), 'blockers' => $report['blockers'],
    'models' => array_map(fn($a) => ['host_id' => $a['host_id'], 'source_model' => $a['source_model_name'],
        'computer_model_ids' => array_column($a['computer_model_candidates'], 'id')], $report['assets']),
    'evidence' => $destination,
], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR).PHP_EOL;
exit($report['blockers'] ? 2 : 0);
