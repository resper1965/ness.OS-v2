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

$roleName = 'n.infraops API Read Only';
$groupName = 'n.infraops API Read Only';
$username = 'svc_ninfraops_api';
$tokenName = 'n.infraops-readonly-20260902';
$apply = in_array('--apply', $argv, true);

$roles = (new CRole())->get([
    'output' => ['roleid', 'name', 'type'],
    'filter' => ['name' => $roleName],
]);
$groups = (new CUserGroup())->get([
    'output' => ['usrgrpid', 'name', 'gui_access', 'users_status'],
    'filter' => ['name' => $groupName],
]);
$users = (new CUser())->get([
    'output' => ['userid', 'username', 'roleid'],
    'filter' => ['username' => $username],
]);
$hostGroups = (new CHostGroup())->get([
    'output' => ['groupid', 'name'],
]);

if (!$hostGroups) {
    throw new RuntimeException('No host groups are available for read-only access.');
}
if (count($roles) > 1 || count($groups) > 1 || count($users) > 1) {
    throw new RuntimeException('Existing service identity state is ambiguous.');
}

if (!$apply) {
    echo json_encode([
        'status' => 'ready',
        'mode' => 'dry-run',
        'host_group_count' => count($hostGroups),
        'existing_role_count' => count($roles),
        'existing_group_count' => count($groups),
        'existing_user_count' => count($users),
        'write_operations' => 0,
    ], JSON_THROW_ON_ERROR) . PHP_EOL;
    exit(0);
}

if ($roles || $groups || $users) {
    throw new RuntimeException('Partial service identity already exists; refusing apply.');
}

$apiMethods = [
    'event.get',
    'history.get',
    'host.get',
    'item.get',
    'problem.get',
    'proxy.get',
    'trend.get',
    'trigger.get',
];
$rights = array_map(
    static fn (array $group): array => [
        'id' => (string) $group['groupid'],
        'permission' => PERM_READ,
    ],
    $hostGroups,
);

DBstart();
try {
    $roleResult = (new CRole())->create([[
        'name' => $roleName,
        'type' => USER_TYPE_ZABBIX_USER,
        'rules' => [
            'ui.default_access' => ZBX_ROLE_RULE_DISABLED,
            'modules.default_access' => ZBX_ROLE_RULE_DISABLED,
            'api.access' => ZBX_ROLE_RULE_ENABLED,
            'api.mode' => ZBX_ROLE_RULE_API_MODE_ALLOW,
            'api' => $apiMethods,
            'actions.default_access' => ZBX_ROLE_RULE_DISABLED,
        ],
    ]]);
    $roleId = (string) $roleResult['roleids'][0];

    $groupResult = (new CUserGroup())->create([[
        'name' => $groupName,
        'gui_access' => GROUP_GUI_ACCESS_DISABLED,
        'users_status' => GROUP_STATUS_ENABLED,
        'hostgroup_rights' => $rights,
    ]]);
    $groupId = (string) $groupResult['usrgrpids'][0];

    $password = 'N!'.bin2hex(random_bytes(32)).'aA1';
    $userResult = (new CUser())->create([[
        'username' => $username,
        'name' => 'n.infraops',
        'surname' => 'API',
        'passwd' => $password,
        'roleid' => $roleId,
        'usrgrps' => [['usrgrpid' => $groupId]],
    ]]);
    unset($password);
    $userId = (string) $userResult['userids'][0];

    $tokenResult = (new CToken())->create([[
        'name' => $tokenName,
        'description' => 'Hub read-only integration',
        'userid' => $userId,
        'status' => ZBX_AUTH_TOKEN_ENABLED,
        'expires_at' => strtotime('2026-12-01T03:00:00Z'),
    ]]);
    $tokenId = (string) $tokenResult['tokenids'][0];
    $generated = (new CToken())->generate([$tokenId]);
    $rawToken = (string) $generated[0]['token'];
    if (strlen($rawToken) !== 64) {
        throw new RuntimeException('Generated token has an unexpected format.');
    }

    if (!DBend(true)) {
        throw new RuntimeException('Zabbix transaction commit failed.');
    }
} catch (Throwable $error) {
    DBend(false);
    throw $error;
}

$tokenPath = '/run/ness-zabbix-hub-readonly/token';
if (!is_dir(dirname($tokenPath)) && !mkdir(dirname($tokenPath), 0700, true)) {
    throw new RuntimeException('Token staging directory could not be created.');
}
file_put_contents($tokenPath, $rawToken);
chmod($tokenPath, 0600);
unset($rawToken);

echo json_encode([
    'status' => 'created',
    'role_id' => $roleId,
    'group_id' => $groupId,
    'user_id' => $userId,
    'token_id' => $tokenId,
    'host_group_rights' => count($rights),
    'api_method_count' => count($apiMethods),
    'token_expires_at' => '2026-12-01T03:00:00Z',
], JSON_THROW_ON_ERROR) . PHP_EOL;
