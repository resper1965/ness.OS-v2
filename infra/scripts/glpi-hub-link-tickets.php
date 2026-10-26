<?php
if (!in_array('--apply', $argv, true)) {
    echo json_encode(['mode' => 'preview', 'write_required' => '--apply']) . PHP_EOL;
    exit;
}
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel(); $kernel->boot(); global $DB;
$plan = json_decode(file_get_contents('/tmp/hub-cmdb-links-plan.json'), true, flags: JSON_THROW_ON_ERROR);
Session::callAsSystem(function () use ($plan, $DB) {
    foreach ($plan['tickets'] as $row) {
        $ticket = new Ticket();
        $type = $row['itemtype'];
        if (!in_array($type, [Computer::class, NetworkEquipment::class], true)) throw new RuntimeException('Unsupported asset');
        $asset = new $type();
        if (!$ticket->getFromDB($row['ticket_id']) || !$asset->getFromDB($row['item_id'])) throw new RuntimeException('Missing record');
        if ((int)$ticket->fields['entities_id'] !== (int)$row['entity'] || (int)$asset->fields['entities_id'] !== (int)$row['entity']) throw new RuntimeException('Entity mismatch');
        if (!str_contains($ticket->fields['name'], '[n.infraops:'.$row['fingerprint'].']')) throw new RuntimeException('Marker mismatch');
        $existing = iterator_to_array($DB->request(['FROM'=>'glpi_items_tickets','WHERE'=>['tickets_id'=>$row['ticket_id']]]));
        if ($existing) continue;
        if ((int)$ticket->fields['status'] === 6) continue;
        $link = new Item_Ticket();
        $id = $link->add(['tickets_id'=>$row['ticket_id'],'itemtype'=>$type,'items_id'=>$row['item_id']]);
        if (!$id) throw new RuntimeException('Ticket asset link failed');
        echo json_encode(['ticket'=>$row['ticket_id'],'link'=>$id,'itemtype'=>$type,'item_id'=>$row['item_id']]).PHP_EOL;
    }
});
