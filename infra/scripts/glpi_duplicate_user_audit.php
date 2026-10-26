<?php

// Read-only aggregate audit. Run inside the GLPI container; never print names or emails.
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();

global $DB;

$users = [];
$byLogin = [];
foreach ($DB->request([
    'SELECT' => ['id', 'name', 'is_active', 'is_deleted', 'authtype', 'last_login'],
    'FROM' => 'glpi_users',
]) as $row) {
    if ((int) $row['is_deleted'] !== 0) {
        continue;
    }
    $id = (int) $row['id'];
    $users[$id] = $row;
    $key = mb_strtolower(trim((string) $row['name']));
    if ($key !== '') {
        $byLogin[$key][] = $id;
    }
}

$byEmail = [];
foreach ($DB->request([
    'SELECT' => ['users_id', 'email'],
    'FROM' => 'glpi_useremails',
]) as $row) {
    $id = (int) $row['users_id'];
    if (!isset($users[$id])) {
        continue;
    }
    $key = mb_strtolower(trim((string) $row['email']));
    if ($key !== '') {
        $byEmail[$key][$id] = true;
    }
}

$groups = [];
$duplicateIds = [];
foreach ($byLogin as $ids) {
    if (count($ids) < 2) {
        continue;
    }
    sort($ids, SORT_NUMERIC);
    array_push($duplicateIds, ...$ids);
    $active = count(array_filter($ids, fn (int $id): bool => (int) $users[$id]['is_active'] === 1));
    $groups[] = [
        'ids' => $ids,
        'total' => count($ids),
        'active' => $active,
        'auth_types' => count(array_unique(array_map(fn (int $id): int => (int) $users[$id]['authtype'], $ids))),
    ];
}
usort($groups, fn (array $a, array $b): int => $b['active'] <=> $a['active'] ?: $b['total'] <=> $a['total']);
$references = [];
$profileSets = array_fill_keys($duplicateIds, []);
foreach ($DB->request([
    'SELECT' => ['users_id', 'profiles_id', 'entities_id', 'is_recursive'],
    'FROM' => 'glpi_profiles_users',
    'WHERE' => ['users_id' => $duplicateIds],
]) as $row) {
    $profileSets[(int) $row['users_id']][] = implode(':', [
        $row['profiles_id'], $row['entities_id'], $row['is_recursive'],
    ]);
}
foreach ($profileSets as &$set) {
    sort($set);
}
unset($set);
foreach (['glpi_tickets_users', 'glpi_profiles_users', 'glpi_groups_users', 'glpi_itilfollowups'] as $table) {
    $references[$table] = array_fill_keys($duplicateIds, 0);
    foreach ($DB->request([
        'SELECT' => ['users_id'],
        'FROM' => $table,
        'WHERE' => ['users_id' => $duplicateIds],
    ]) as $row) {
        $references[$table][(int) $row['users_id']]++;
    }
}
$patterns = [];
foreach ($groups as &$group) {
    $types = array_map(fn (int $id): int => (int) $users[$id]['authtype'], $group['ids']);
    sort($types, SORT_NUMERIC);
    $pattern = implode('+', $types);
    $patterns[$pattern] = ($patterns[$pattern] ?? 0) + 1;
    $group['accounts'] = array_map(fn (int $id): array => [
        'id' => $id,
        'auth_type' => (int) $users[$id]['authtype'],
        'active' => (int) $users[$id]['is_active'],
        'ever_logged_in' => !empty($users[$id]['last_login']),
        'ticket_links' => $references['glpi_tickets_users'][$id],
        'profile_links' => $references['glpi_profiles_users'][$id],
        'profile_grants' => $profileSets[$id],
        'group_links' => $references['glpi_groups_users'][$id],
        'followups' => $references['glpi_itilfollowups'][$id],
    ], $group['ids']);
    $group['same_profile_grants'] = count(array_unique(array_map(
        fn (int $id): string => implode('|', $profileSets[$id]), $group['ids']
    ))) === 1;
}
unset($group);
$result = [
    'users_total' => count($users),
    'users_active' => count(array_filter($users, fn (array $row): bool => (int) $row['is_active'] === 1)),
    'duplicate_login_groups' => count($groups),
    'duplicate_login_active_groups' => count(array_filter($groups, fn (array $group): bool => $group['active'] > 1)),
    'duplicate_email_groups' => count(array_filter($byEmail, fn (array $ids): bool => count($ids) > 1)),
    'auth_type_patterns' => $patterns,
    'login_groups' => $groups,
];
echo json_encode($result, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR), PHP_EOL;
