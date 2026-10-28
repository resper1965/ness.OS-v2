<?php
// Usage: docker exec -i -u www-data ninf-glpi php -- "<name>" [--apply] < glpi-entity-create.php
// Creates a customer entity under root (0) plus the Hub bindings every customer entity has:
// svc_ness_os (94) with profile 12, non-recursive, and the infraops/NOC technical group.
// Idempotent; dry-run by default; prints the resulting ids.
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
global $DB;
$name = $argv[1] ?? '';
$apply = in_array('--apply', $argv, true);
if ($name === '' || $name[0] === '-') {
    fwrite(STDERR, "entity name required\n");
    exit(1);
}
Session::callAsSystem(function () use ($DB, $name, $apply) {
    $found = iterator_to_array($DB->request(['FROM' => 'glpi_entities', 'WHERE' => ['name' => $name, 'entities_id' => 0]]));
    $entity = $found ? (int) reset($found)['id'] : null;
    if ($entity === null && $apply) {
        $entity = (int) (new Entity())->add(['name' => $name, 'entities_id' => 0]);
        if (!$entity) throw new RuntimeException('Entity create failed');
    }
    $binding = $group = null;
    if ($entity !== null) {
        $b = iterator_to_array($DB->request(['FROM' => 'glpi_profiles_users',
            'WHERE' => ['users_id' => 94, 'profiles_id' => 12, 'entities_id' => $entity]]));
        $binding = $b ? (int) reset($b)['id'] : null;
        if ($binding === null && $apply) {
            $binding = (int) (new Profile_User())->add(['users_id' => 94, 'profiles_id' => 12,
                'entities_id' => $entity, 'is_recursive' => 0, 'is_dynamic' => 0]);
            if (!$binding) throw new RuntimeException('Profile binding failed');
        }
        $g = iterator_to_array($DB->request(['FROM' => 'glpi_groups',
            'WHERE' => ['name' => 'infraops/NOC', 'entities_id' => $entity, 'is_recursive' => 0]]));
        $group = $g ? (int) reset($g)['id'] : null;
        if ($group === null && $apply) {
            $group = (int) (new Group())->add(['name' => 'infraops/NOC', 'entities_id' => $entity,
                'is_recursive' => 0, 'is_itemgroup' => 1, 'is_assign' => 1, 'is_notify' => 0,
                'comment' => 'Responsável operacional padrão ness.OS. Sem alteração de membros ou permissões de usuários.']);
            if (!$group) throw new RuntimeException('Group create failed');
        }
    }
    echo json_encode(['mode' => $apply ? 'apply' : 'check', 'name' => $name,
        'entity' => $entity, 'binding_94' => $binding, 'noc_group' => $group]) . PHP_EOL;
});
