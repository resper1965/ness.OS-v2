<?php
// Disposable GLPI accounts are restricted to a single entity and removed with --cleanup.
if (!in_array('--apply', $argv, true)) {
    echo json_encode(['mode' => 'preview', 'write_required' => '--apply']) . PHP_EOL;
    exit;
}
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel(); $kernel->boot();
$path = '/tmp/ness-glpi-access-check.json';
if (in_array('--cleanup', $argv, true)) {
    $accounts = json_decode(file_get_contents($path), true, flags: JSON_THROW_ON_ERROR);
    Session::callAsSystem(function () use ($accounts) {
        foreach ($accounts as $account) {
            $user = new User();
            if (!$user->getFromDB($account['id']) || $user->fields['name'] !== $account['name']) throw new RuntimeException('Cleanup identity mismatch');
            if (!$user->delete(['id'=>$account['id']], true)) throw new RuntimeException('Temporary user cleanup failed');
        }
    });
    unlink($path);
    echo json_encode(['temporary_accounts_removed'=>count($accounts)]).PHP_EOL;
    exit;
}
if (file_exists($path)) throw new RuntimeException('Previous validation accounts require cleanup');
$accounts = [];
$entities = in_array('--include-root', $argv, true) ? [0, 1, 8] : [1, 8];
Session::callAsSystem(function () use (&$accounts, $path, $entities) {
    foreach ($entities as $entity) {
        $name = 'ness-validation-'.bin2hex(random_bytes(8));
        $password = bin2hex(random_bytes(24));
        $token = bin2hex(random_bytes(32));
        $user = new User();
        $id = $user->add(['name'=>$name,'password'=>$password,'password2'=>$password,
                         'api_token'=>$token,'is_active'=>1,'authtype'=>Auth::DB_GLPI,
                         'entities_id'=>$entity,'profiles_id'=>8]);
        if (!$id) throw new RuntimeException('Temporary user creation failed');
        $accounts[] = ['id'=>$id,'name'=>$name,'entity'=>$entity,'token'=>$token];
        file_put_contents($path, json_encode($accounts)); chmod($path,0600);
        $profile = new Profile_User();
        global $DB;
        $bindings = iterator_to_array($DB->request(['FROM'=>'glpi_profiles_users','WHERE'=>['users_id'=>$id]]));
        if (!$bindings && !$profile->add(['users_id'=>$id,'profiles_id'=>8,'entities_id'=>$entity,'is_recursive'=>0])) throw new RuntimeException('Profile binding failed');
        foreach ($bindings as $binding) if ((int)$binding['entities_id']!==$entity || (int)$binding['profiles_id']!==8 || (int)$binding['is_recursive']!==0) throw new RuntimeException('Unexpected temporary access');
    }
});
echo json_encode(['temporary_accounts_created'=>count($accounts)]).PHP_EOL;
