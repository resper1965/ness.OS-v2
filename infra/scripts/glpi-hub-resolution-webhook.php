<?php
if (!in_array('--apply', $argv, true)) {
    echo json_encode(['mode' => 'preview', 'write_required' => '--apply']) . PHP_EOL;
    exit;
}
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
global $DB;
$key = getenv('HUB_WEBHOOK_KEY');
if (!$key || strlen($key) < 48) { throw new RuntimeException('Webhook key unavailable'); }
$name = 'ness.OS Hub - ticket status';
$existing = iterator_to_array($DB->request([
    'FROM' => 'glpi_webhooks', 'WHERE' => ['name' => $name],
]));
if ($existing) { throw new RuntimeException('Webhook already exists; inspect before updating'); }
$webhook = new Webhook();
$id = $webhook->add([
    'name' => $name, 'entities_id' => 0, 'is_recursive' => 1,
    'itemtype' => 'Ticket', 'event' => 'update', 'is_active' => 1,
    'url' => 'https://hub.ness.com.br/webhook/glpi', 'http_method' => 'POST',
    'use_default_payload' => 0,
    'payload' => '{"ticket_id":"{{ item.id }}","status":"{{ item.status.id }}","solution":""}',
    'custom_headers' => ['Content-Type' => 'application/json', 'X-Api-Key' => $key],
    'use_cra_challenge' => 0, 'save_response_body' => 0,
    'sent_try' => 3, 'comment' => 'Authenticated internal callback; hub accepts only solved/closed statuses.',
]);
if (!$id) { throw new RuntimeException('Webhook creation failed'); }
echo json_encode(['webhook_id' => (int) $id, 'event' => 'update', 'authenticated' => true]) . PHP_EOL;
