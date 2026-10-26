<?php
if (!in_array('--apply', $argv, true)) {
    echo json_encode(['mode' => 'preview', 'write_required' => '--apply']) . PHP_EOL;
    exit;
}
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel(); $kernel->boot(); global $DB;
$plan = json_decode(file_get_contents('/tmp/hub-cmdb-links-plan.json'), true, flags: JSON_THROW_ON_ERROR);
Session::callAsSystem(function () use ($plan, $DB) {
    $groups = [];
    foreach ($plan['assets'] as $row) {
        $type = $row['itemtype'];
        if (!in_array($type, [Computer::class, NetworkEquipment::class], true)) throw new RuntimeException('Unsupported asset');
        $asset = new $type();
        if (!$asset->getFromDB($row['id']) || (int)$asset->fields['entities_id'] !== (int)$row['entity']) throw new RuntimeException('Asset mismatch');
        $existing = iterator_to_array($DB->request(['FROM'=>'glpi_groups_items','WHERE'=>['itemtype'=>$type,'items_id'=>$row['id'],'type'=>Group_Item::GROUP_TYPE_TECH]]));
        if ($existing || !empty($asset->fields['users_id_tech']) || !empty($row['owner'])) continue;
        $entity = (int)$row['entity'];
        if (!isset($groups[$entity])) {
            if ($entity === 0) $groups[$entity] = 13;
            else {
                $matches = iterator_to_array($DB->request(['FROM'=>'glpi_groups','WHERE'=>['name'=>'infraops/NOC','entities_id'=>$entity,'is_recursive'=>0]]));
                if ($matches) $groups[$entity] = (int)reset($matches)['id'];
                else {
                    $group = new Group();
                    $id = $group->add(['name'=>'infraops/NOC','entities_id'=>$entity,'is_recursive'=>0,
                                      'is_itemgroup'=>1,'is_assign'=>1,'is_notify'=>0,
                                      'comment'=>'Responsável operacional padrão ness.OS. Sem alteração de membros ou permissões de usuários.']);
                    if (!$id) throw new RuntimeException('Group create failed');
                    $groups[$entity] = $id;
                    echo json_encode(['created_group'=>$id,'entity'=>$entity]).PHP_EOL;
                }
            }
        }
        $link = new Group_Item();
        $id = $link->add(['groups_id'=>$groups[$entity],'itemtype'=>$type,'items_id'=>$row['id'],'type'=>Group_Item::GROUP_TYPE_TECH]);
        if (!$id) throw new RuntimeException('Owner link failed');
        echo json_encode(['owner_link'=>$id,'group'=>$groups[$entity],'itemtype'=>$type,'item_id'=>$row['id']]).PHP_EOL;
    }
});
