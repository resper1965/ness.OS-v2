<?php
// Run within GLPI 11. No privileges are added to the existing service profile.
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
global $DB;
$users = iterator_to_array($DB->request([
    'SELECT' => ['id', 'name', 'is_active'], 'FROM' => 'glpi_users',
    'WHERE' => ['name' => 'svc_ness_os'],
]));
if (count($users) !== 1 || (int) reset($users)['id'] !== 94 || !(int) reset($users)['is_active']) {
    throw new RuntimeException('Unexpected service identity');
}
$entities = [1,2,3,4,5,6,7,8,9,10,11];
$apply = in_array('--apply', $argv, true);
$created = [];
$DB->beginTransaction();
try {
    foreach ($entities as $entity) {
        $object = new Entity();
        if (!$object->getFromDB($entity)) {
            throw new RuntimeException('Missing entity');
        }
        $existing = iterator_to_array($DB->request([
            'FROM' => 'glpi_profiles_users',
            'WHERE' => ['users_id' => 94, 'profiles_id' => 12, 'entities_id' => $entity],
        ]));
        if (!$existing && $apply) {
            $binding = new Profile_User();
            $id = $binding->add([
                'users_id' => 94, 'profiles_id' => 12,
                'entities_id' => $entity, 'is_recursive' => 0, 'is_dynamic' => 0,
            ]);
            if (!$id) { throw new RuntimeException('Profile binding failed'); }
            $created[] = (int) $id;
        }
    }
    $DB->commit();
    echo json_encode(['mode' => $apply ? 'apply' : 'check', 'entities' => $entities,
        'created_binding_ids' => $created, 'profile_unchanged' => 12]) . PHP_EOL;
} catch (Throwable $error) {
    $DB->rollBack();
    throw $error;
}
