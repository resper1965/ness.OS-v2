<?php

declare(strict_types=1);

chdir('/usr/share/zabbix');
require_once 'include/func.inc.php';
require_once 'include/classes/core/APP.php';

APP::getInstance()->run(APP::EXEC_MODE_API);
API::setWrapper();

$maxRow = DBfetch(DBselect('SELECT MAX(id) AS max_id FROM users_groups'));
$counterRow = DBfetch(DBselect(
    "SELECT nextid FROM ids WHERE table_name='users_groups' AND field_name='id'"
));
$maximum = (int) $maxRow['max_id'];
$before = (int) $counterRow['nextid'];

if ($before > $maximum) {
    throw new RuntimeException('Counter is ahead of the table; refusing to lower it.');
}

if ($before < $maximum) {
    DBstart();
    try {
        DB::update('ids', [[
            'values' => ['nextid' => $maximum],
            'where' => ['table_name' => 'users_groups', 'field_name' => 'id'],
        ]]);
        if (!DBend(true)) {
            throw new RuntimeException('Counter transaction commit failed.');
        }
    } catch (Throwable $error) {
        DBend(false);
        throw $error;
    }
}

$verified = DBfetch(DBselect(
    "SELECT nextid FROM ids WHERE table_name='users_groups' AND field_name='id'"
));
$after = (int) $verified['nextid'];
if ($after !== $maximum) {
    throw new RuntimeException('Counter verification failed.');
}

echo json_encode([
    'status' => $before === $after ? 'unchanged' : 'reconciled',
    'table' => 'users_groups',
    'field' => 'id',
    'maximum' => $maximum,
    'counter_before' => $before,
    'counter_after' => $after,
], JSON_THROW_ON_ERROR) . PHP_EOL;
