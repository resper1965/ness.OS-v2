<?php
// Add the approved internal operating plan through GLPI models. Never overwrite
// operator edits, deadlines, SLA values, existing articles or customer records.
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
global $DB, $CFG_GLPI;
$plan = json_decode(file_get_contents($argv[1]), true, flags: JSON_THROW_ON_ERROR);
$apply = ($argv[2] ?? '') === '--apply';
if ((int)$plan['entity_id'] !== 0 || (int)$plan['owner_group_id'] !== 13) {
    throw new RuntimeException('Unexpected operating entity or group');
}
$urlBefore = Config::getConfigurationValues('core', ['url_base']);
if ($plan['public_url'] !== 'https://n-ticket.ness.com.br'
    || !in_array($urlBefore['url_base'], ['http://localhost', $plan['public_url']], true)) {
    throw new RuntimeException('Unexpected public URL; review required');
}
if ((int)($CFG_GLPI['use_notifications'] ?? 1) !== 0) {
    throw new RuntimeException('Notifications must already be disabled; no messages authorized');
}
$owner = new Group();
if (!$owner->getFromDB(13) || (int)$owner->fields['entities_id'] !== 0) {
    throw new RuntimeException('Internal owner group missing');
}
foreach ([1, 2] as $id) {
    $state = new ProjectState();
    if (!$state->getFromDB($id) || (int)$state->fields['is_finished'] !== 0) {
        throw new RuntimeException('Expected open project state unavailable');
    }
}
$before = ['projects' => [], 'tasks' => [], 'articles' => []];
$before['configuration'] = $urlBefore;
$before['projects'] = array_values(iterator_to_array($DB->request([
    'FROM' => Project::getTable(), 'WHERE' => ['code' => $plan['project']['code']],
])));
foreach ($before['projects'] as $project) {
    $before['tasks'] = array_merge($before['tasks'], array_values(iterator_to_array($DB->request([
        'FROM' => ProjectTask::getTable(), 'WHERE' => ['projects_id' => $project['id']],
    ]))));
}
foreach ($plan['runbooks'] as $article) {
    $before['articles'] = array_merge($before['articles'], array_values(iterator_to_array($DB->request([
        'FROM' => KnowbaseItem::getTable(), 'WHERE' => ['name' => $article['name'], 'entities_id' => 0],
    ]))));
}
if (!$apply) {
    echo json_encode(['mode' => 'preview', 'project' => $plan['project']['name'],
        'task_count' => count($plan['tasks']), 'runbook_count' => count($plan['runbooks']),
        'existing' => array_map('count', $before)], JSON_UNESCAPED_UNICODE) . PHP_EOL;
    exit;
}
$result = ['created' => [], 'existing' => [], 'project_id' => null, 'tasks' => [], 'runbooks' => []];
$snapshot = '/tmp/ness-operations-foundation-before-' . date('YmdHis') . '.json';
file_put_contents($snapshot, json_encode($before, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
chmod($snapshot, 0600);

Session::callAsSystem(function () use ($DB, $plan, &$result) {
    $ensure = function (string $class, array $where, array $input) use ($DB, &$result): int {
        $rows = array_values(iterator_to_array($DB->request(['FROM' => $class::getTable(), 'WHERE' => $where])));
        if (count($rows) > 1) {
            throw new RuntimeException('Ambiguous managed object: ' . $class);
        }
        if ($rows) {
            $row = $rows[0];
            if (!empty($row['is_deleted']) || !empty($row['is_recursive'])
                || (isset($row['entities_id']) && (int)$row['entities_id'] !== 0)) {
                throw new RuntimeException('Existing object scope/state changed: ' . $class);
            }
            $result['existing'][] = ['type' => $class, 'id' => (int)$row['id']];
            return (int)$row['id'];
        }
        $item = new $class();
        $id = $item->add($input + ['_disablenotif' => true]);
        if (!$id) {
            throw new RuntimeException('Native creation failed: ' . $class);
        }
        $result['created'][] = ['type' => $class, 'id' => (int)$id];
        return (int)$id;
    };
    $DB->beginTransaction();
    try {
        $configuration = Config::getConfigurationValues('core', ['url_base']);
        if ($configuration['url_base'] !== $plan['public_url']) {
            Config::setConfigurationValues('core', ['url_base' => $plan['public_url']]);
        }
        $project = $ensure(Project::class, ['code' => $plan['project']['code']], $plan['project'] + [
            'entities_id' => 0, 'is_recursive' => 0, 'groups_id' => 13,
            'projectstates_id' => 2, 'auto_percent_done' => 0, 'percent_done' => 0,
            'show_on_global_gantt' => 0,
        ]);
        $result['project_id'] = $project;
        $ensure(ProjectTeam::class, ['projects_id' => $project, 'itemtype' => 'Group', 'items_id' => 13],
            ['projects_id' => $project, 'itemtype' => 'Group', 'items_id' => 13]);
        foreach ($plan['tasks'] as $task) {
            $marker = 'ness-os-gate:' . $task['key'];
            $id = $ensure(ProjectTask::class, ['projects_id' => $project, 'comment' => $marker], [
                'projects_id' => $project, 'name' => $task['name'], 'content' => $task['content'],
                'comment' => $marker, 'entities_id' => 0, 'is_recursive' => 0,
                'projectstates_id' => $task['state'], 'auto_percent_done' => 0, 'percent_done' => 0,
            ]);
            $ensure(ProjectTaskTeam::class, ['projecttasks_id' => $id, 'itemtype' => 'Group', 'items_id' => 13],
                ['projecttasks_id' => $id, 'itemtype' => 'Group', 'items_id' => 13]);
            $result['tasks'][$task['key']] = $id;
        }
        foreach ($plan['runbooks'] as $article) {
            $category = new KnowbaseItemCategory();
            if (!$category->getFromDB($article['category_id'])) {
                throw new RuntimeException('Knowledge category missing');
            }
            $id = $ensure(KnowbaseItem::class, ['name' => $article['name'], 'entities_id' => 0], [
                'name' => $article['name'], 'answer' => $article['answer'], 'entities_id' => 0,
                'is_recursive' => 0, 'is_faq' => 0, 'show_in_service_catalog' => 0,
                '_categories' => [$article['category_id']],
                '_visibility' => ['_type' => 'Entity', 'entities_id' => 0, 'is_recursive' => 0],
            ]);
            $links = array_values(iterator_to_array($DB->request([
                'FROM' => Entity_KnowbaseItem::getTable(), 'WHERE' => ['knowbaseitems_id' => $id],
            ])));
            $item = new KnowbaseItem();
            $item->getFromDB($id);
            if (count($links) !== 1 || (int)$links[0]['entities_id'] !== 0
                || (int)$links[0]['is_recursive'] !== 0 || (int)$item->fields['is_faq'] !== 0) {
                throw new RuntimeException('Knowledge visibility is not internal-only');
            }
            $result['runbooks'][] = $id;
        }
        $DB->commit();
    } catch (Throwable $error) {
        $DB->rollback();
        throw $error;
    }
});
echo json_encode($result + ['before_snapshot' => $snapshot], JSON_UNESCAPED_UNICODE) . PHP_EOL;
