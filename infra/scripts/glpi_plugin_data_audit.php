<?php

// Read-only inventory of plugin records and residual tables. No plugin lifecycle calls.
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
global $DB;

$plugins = [];
foreach ($DB->request([
    'SELECT' => ['id', 'directory', 'state', 'version'],
    'FROM' => 'glpi_plugins',
]) as $row) {
    $plugins[] = [
        'id' => (int) $row['id'],
        'directory' => (string) $row['directory'],
        'state' => (int) $row['state'],
        'version' => (string) $row['version'],
    ];
}

$tables = [];
foreach ($DB->listTables('glpi_plugin_%') as $row) {
    $table = (string) array_values($row)[0];
    if ($table === 'glpi_plugins') {
        continue;
    }
    $count = 0;
    foreach ($DB->request(['COUNT' => 'n', 'FROM' => $table]) as $countRow) {
        $count = (int) $countRow['n'];
    }
    $tables[$table] = $count;
}
ksort($tables);

echo json_encode([
    'plugin_records' => $plugins,
    'plugin_tables' => $tables,
], JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR), PHP_EOL;
