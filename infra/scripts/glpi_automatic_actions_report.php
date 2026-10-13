<?php

// Read-only inventory of scheduled automatic actions; never execute tasks.
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
global $DB;

$actions = [];
foreach ($DB->request([
    'SELECT' => ['name', 'itemtype', 'mode', 'state', 'lastrun'],
    'FROM' => 'glpi_crontasks',
    'ORDER' => ['name ASC'],
]) as $row) {
    $actions[] = [
        'name' => (string) $row['name'],
        'itemtype' => (string) $row['itemtype'],
        'mode' => (int) $row['mode'],
        'state' => (int) $row['state'],
        'lastrun' => $row['lastrun'],
    ];
}

echo json_encode($actions, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR), PHP_EOL;
