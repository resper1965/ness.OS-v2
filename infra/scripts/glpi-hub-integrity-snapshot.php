<?php
// Read-only snapshot, without ticket descriptions, credentials or user data.
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
global $DB;
$tickets = [];
foreach ($DB->request(['FROM' => 'glpi_tickets', 'SELECT' => ['id', 'name', 'entities_id', 'status', 'is_deleted']]) as $row) {
    if (!preg_match('/\[n\.infraops:([a-f0-9]{64})\]/', $row['name'], $match)) continue;
    $tickets[(int)$row['id']] = [
        'id' => (int)$row['id'], 'fingerprint' => $match[1],
        'entity' => (int)$row['entities_id'], 'status' => (int)$row['status'],
        'deleted' => (bool)$row['is_deleted'], 'followups' => 0, 'assets' => [],
    ];
}
foreach ($DB->request(['FROM' => 'glpi_itilfollowups', 'SELECT' => ['items_id'], 'WHERE' => ['itemtype' => 'Ticket']]) as $row) {
    if (isset($tickets[(int)$row['items_id']])) $tickets[(int)$row['items_id']]['followups']++;
}
foreach ($DB->request(['FROM' => 'glpi_items_tickets', 'SELECT' => ['tickets_id', 'itemtype', 'items_id']]) as $row) {
    if (isset($tickets[(int)$row['tickets_id']])) $tickets[(int)$row['tickets_id']]['assets'][] = [
        'itemtype' => $row['itemtype'], 'id' => (int)$row['items_id'],
    ];
}
echo json_encode(['tickets' => array_values($tickets)], JSON_THROW_ON_ERROR) . "\n";
