<?php
// Native, transactional migration. Never purge sources or their history.
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel(); $kernel->boot();
global $DB, $CFG_GLPI;
$mode = $argv[1] ?? '--preview';
if (!in_array($mode, ['--preview', '--rehearse', '--rehearse-rollback', '--apply', '--rollback'], true)) {
    throw new RuntimeException('Unknown mode');
}
if ((int)($CFG_GLPI['use_notifications'] ?? 1) !== 0) {
    throw new RuntimeException('Notifications must already be disabled');
}
$snapshot = json_decode(file_get_contents($argv[2]), true, flags: JSON_THROW_ON_ERROR);
if ($snapshot['blockers'] || count($snapshot['assets']) !== 3) {
    throw new RuntimeException('Preflight contains blockers');
}
$expected = [120 => '10882', 121 => '10883', 122 => '10884'];
$columns = $DB->listFields(Computer::getTable());
$result = ['mode' => $mode, 'created' => [], 'assets' => []];

function assertNoRelations(string $type, int $id): void {
    global $DB;
    $direct = $type === Computer::class ? 'computers_id' : 'networkequipments_id';
    foreach ($DB->listTables('glpi_%') as $tableRow) {
        $table = array_values($tableRow)[0];
        if ($table === 'glpi_logs') continue;
        $columns = $DB->listFields($table);
        $conditions = [];
        foreach (['', '_1', '_2'] as $suffix) {
            if (isset($columns['itemtype'.$suffix], $columns['items_id'.$suffix])) {
                $conditions[] = ['itemtype'.$suffix => $type, 'items_id'.$suffix => $id];
            }
        }
        foreach (array_keys($columns) as $column) {
            if (preg_match('/^'.$direct.'(?:_|$)/', $column)) $conditions[] = [$column => $id];
        }
        foreach ($conditions as $where) {
            if (count($DB->request(['FROM' => $table, 'WHERE' => $where]))) {
                throw new RuntimeException('Unmanaged relation on '.$type.' '.$id.': '.$table);
            }
        }
    }
}

Session::callAsSystem(function () use ($DB, $mode, $snapshot, $expected, $columns, &$result) {
    $DB->beginTransaction();
    try {
        foreach ($snapshot['assets'] as $entry) {
            $before = $entry['source']; $id = (int)$before['id']; $host = $entry['host_id'];
            if (($expected[$id] ?? null) !== $host) throw new RuntimeException('Unexpected source');
            $source = new NetworkEquipment();
            if (!$source->getFromDB($id)) throw new RuntimeException('Source missing');
            foreach ($before as $field => $value) {
                if (in_array($field, ['is_deleted', 'date_mod'], true)) continue;
                if (($source->fields[$field] ?? null) !== $value) {
                    throw new RuntimeException('Source changed: '.$id.' '.$field);
                }
            }
            assertNoRelations(NetworkEquipment::class, $id);
            $origin = 'ness-vm-migration:NetworkEquipment:'.$id;
            $targets = [];
            foreach ([Computer::class, NetworkEquipment::class] as $type) {
                foreach ($DB->request(['FROM' => $type::getTable()]) as $row) {
                    if ($type === NetworkEquipment::class && (int)$row['id'] === $id) continue;
                    if (!preg_match('/Zabbix Host ID:\s*(\d+)/', $row['comment'] ?? '', $m) || $m[1] !== $host) continue;
                    if ($type !== Computer::class || !str_contains($row['comment'], $origin)) {
                        throw new RuntimeException('Conflicting identity '.$host);
                    }
                    $targets[] = $row;
                }
            }
            if (count($targets) > 1) throw new RuntimeException('Duplicate targets');
            $target = $targets[0] ?? null;
            if ($target && ((int)$target['entities_id'] !== 8 || $target['uuid'] !== $before['uuid']
                || $target['name'] !== $before['name'])) throw new RuntimeException('Target identity changed');
            $rollingBack = in_array($mode, ['--rollback', '--rehearse-rollback'], true);
            if ($rollingBack) {
                if (!$target) throw new RuntimeException('Rollback target missing');
                assertNoRelations(Computer::class, (int)$target['id']);
                $computer = new Computer();
                if (!$computer->update(['id' => $target['id'], 'is_deleted' => 1, '_disablenotif' => true])
                    || !$source->update(['id' => $id, 'is_deleted' => 0, '_disablenotif' => true])) {
                    throw new RuntimeException('Rollback update failed');
                }
            } elseif (in_array($mode, ['--apply', '--rehearse'], true)) {
                if (!$target) {
                    if ((int)$source->fields['is_deleted'] !== 0) throw new RuntimeException('Source retired without target');
                    $input = array_intersect_key($before, $columns);
                    foreach (['id', 'date_creation', 'date_mod', 'last_inventory_update', 'is_recursive'] as $field) unset($input[$field]);
                    $input['is_deleted'] = 0;
                    $input['is_recursive'] = 0;
                    $input['computermodels_id'] = 0;
                    $input['comment'] = $before['comment']."\n".$origin."\nHistorical source: /front/networkequipment.form.php?id=".$id;
                    $input['_disablenotif'] = true;
                    $computer = new Computer(); $newId = $computer->add($input);
                    if (!$newId) throw new RuntimeException('Computer creation failed');
                    $target = ['id' => $newId, 'is_deleted' => 0];
                    $result['created'][] = $newId;
                } elseif ((int)$target['is_deleted'] !== 0) {
                    throw new RuntimeException('Target retired; review before reapplying');
                }
                if ((int)$source->fields['is_deleted'] !== 1
                    && !$source->update(['id' => $id, 'is_deleted' => 1, '_disablenotif' => true])) {
                    throw new RuntimeException('Source retirement failed');
                }
            }
            if ($mode !== '--preview') {
                $source->getFromDB($id);
                $check = new Computer();
                if (!$check->getFromDB((int)$target['id'])
                    || (int)$source->fields['is_deleted'] !== ($rollingBack ? 0 : 1)
                    || (int)$check->fields['is_deleted'] !== ($rollingBack ? 1 : 0)
                    || (int)$check->fields['entities_id'] !== 8
                    || (int)$check->fields['locations_id'] !== (int)$before['locations_id']
                    || $check->fields['uuid'] !== $before['uuid']
                    || $check->fields['name'] !== $before['name']) {
                    throw new RuntimeException('Post-write verification failed');
                }
                foreach ($snapshot['references'] as $reference) {
                    if ($reference['table'] !== 'glpi_logs') continue;
                    foreach ($reference['rows'] as $log) {
                        $current = array_values(iterator_to_array($DB->request(['FROM' => 'glpi_logs', 'WHERE' => ['id' => $log['id']]])));
                        if (count($current) !== 1 || $current[0] !== $log) throw new RuntimeException('Original history changed');
                    }
                }
            }
            $result['assets'][] = ['host_id' => $host, 'source_id' => $id, 'computer_id' => $target['id'] ?? null];
        }
        if (in_array($mode, ['--preview', '--rehearse', '--rehearse-rollback'], true)) $DB->rollback();
        else $DB->commit();
    } catch (Throwable $error) {
        $DB->rollback(); throw $error;
    }
});
echo json_encode($result, JSON_THROW_ON_ERROR).PHP_EOL;
