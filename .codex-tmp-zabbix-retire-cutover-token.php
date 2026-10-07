<?php

declare(strict_types=1);

chdir('/usr/share/zabbix');
require_once 'include/func.inc.php';
require_once 'include/classes/core/APP.php';

APP::getInstance()->run(APP::EXEC_MODE_API);
API::setWrapper();

$admin = DBfetch(DBselect(
    'SELECT u.userid,u.username,u.roleid,r.type'.
    ' FROM users u JOIN role r ON r.roleid=u.roleid'.
    ' WHERE u.userid=4'
));
if (!$admin || (int) $admin['type'] !== USER_TYPE_SUPER_ADMIN) {
    throw new RuntimeException('Bootstrap super administrator was not found.');
}

CApiService::$userData = [
    'userid' => (string) $admin['userid'],
    'username' => (string) $admin['username'],
    'roleid' => (string) $admin['roleid'],
    'type' => (int) $admin['type'],
    'userip' => '127.0.0.1',
];

$tokens = (new CToken())->get([
    'output' => ['tokenid', 'name', 'userid', 'status', 'expires_at'],
    'tokenids' => ['4', '5'],
    'preservekeys' => true,
]);
$old = $tokens['4'] ?? null;
$current = $tokens['5'] ?? null;
if (
    !$old || $old['name'] !== 'ness-os-cutover-20260829'
    || (int) $old['status'] !== ZBX_AUTH_TOKEN_ENABLED
) {
    throw new RuntimeException('Enabled cutover token did not match the expected state.');
}
if (
    !$current || $current['name'] !== 'n.infraops-readonly-20260902'
    || (string) $current['userid'] !== '35'
    || (int) $current['status'] !== ZBX_AUTH_TOKEN_ENABLED
) {
    throw new RuntimeException('Replacement read-only token is not enabled as expected.');
}

$apply = in_array('--apply', $argv, true);
if (!$apply) {
    echo json_encode([
        'status' => 'ready',
        'mode' => 'dry-run',
        'retire_token_id' => '4',
        'replacement_token_id' => '5',
        'write_operations' => 0,
    ], JSON_THROW_ON_ERROR).PHP_EOL;
    exit(0);
}

DBstart();
try {
    (new CToken())->update([[
        'tokenid' => '4',
        'status' => ZBX_AUTH_TOKEN_DISABLED,
    ]]);
    if (!DBend(true)) {
        throw new RuntimeException('Token retirement transaction commit failed.');
    }
} catch (Throwable $error) {
    DBend(false);
    throw $error;
}

$verified = (new CToken())->get([
    'output' => ['tokenid', 'status'],
    'tokenids' => ['4'],
]);
if (count($verified) !== 1 || (int) $verified[0]['status'] !== ZBX_AUTH_TOKEN_DISABLED) {
    throw new RuntimeException('Cutover token retirement verification failed.');
}

echo json_encode([
    'status' => 'retired',
    'token_id' => '4',
    'replacement_token_id' => '5',
], JSON_THROW_ON_ERROR).PHP_EOL;
