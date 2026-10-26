<?php
declare(strict_types=1);
// SSH-authorized emergency bootstrap; never run against the live source.
if (gethostname() !== 'zbx-prd-01' || posix_geteuid() !== 0) {
    throw new RuntimeException('Requires root on isolated zbx-prd-01');
}
if (trim((string)shell_exec('systemctl is-enabled zabbix-server 2>/dev/null')) !== 'masked'
    || trim((string)shell_exec('systemctl is-active zabbix-server 2>/dev/null')) !== 'inactive'
    || trim((string)shell_exec("ss -H -lnt 'sport = :10051'")) !== '') {
    throw new RuntimeException('Isolation required');
}
umask(0077);
chdir('/usr/share/zabbix');
require_once 'include/func.inc.php';
require_once 'include/classes/core/APP.php';
APP::getInstance()->run(APP::EXEC_MODE_API);
API::setWrapper();
$admin = DBfetch(DBselect('SELECT u.userid,u.username,u.roleid,r.type FROM users u JOIN role r ON r.roleid=u.roleid WHERE u.userid=4'));
if (!$admin || (int)$admin['type'] !== USER_TYPE_SUPER_ADMIN) {
    throw new RuntimeException('Expected recovery audit actor unavailable');
}
CApiService::$userData = ['userid'=>$admin['userid'], 'username'=>$admin['username'],
    'roleid'=>$admin['roleid'], 'type'=>(int)$admin['type'], 'userip'=>'127.0.0.1'];
$username = 'ness_uat_breakglass';
$groupname = 'ness.os UAT emergency recovery';
$passwordfile = '/etc/ness-os/zabbix-uat-recovery.password';
if ((new CUser())->get(['filter'=>['username'=>$username]])
    || (new CUserGroup())->get(['filter'=>['name'=>$groupname]])
    || file_exists($passwordfile)) {
    throw new RuntimeException('Existing recovery state: inspect, do not overwrite');
}
if (!in_array('--apply', $argv, true)) {
    echo "recovery_preflight=PASS; mode=preview\n";
    exit;
}
if (!is_dir('/etc/ness-os')) { throw new RuntimeException('Protected directory missing'); }
$password = bin2hex(random_bytes(32));
$file = fopen($passwordfile, 'x');
if ($file === false) { throw new RuntimeException('Cannot reserve protected secret'); }
if (fwrite($file, $password."\n") !== strlen($password)+1) {
    fclose($file);
    throw new RuntimeException('Secret persistence failed; no account created');
}
fclose($file);
chmod($passwordfile, 0600);
DBstart();
try {
    $group = (new CUserGroup())->create([['name'=>$groupname,'gui_access'=>1,'users_status'=>0]]);
    $user = (new CUser())->create([['username'=>$username,'passwd'=>$password,
        'name'=>'Authorized UAT','surname'=>'Emergency recovery','roleid'=>$admin['roleid'],
        'usrgrps'=>[['usrgrpid'=>$group['usrgrpids'][0]]]]]);
    if (!DBend(true)) { throw new RuntimeException('Recovery commit failed'); }
    echo json_encode(['recovery_created'=>true,'userid'=>$user['userids'][0],
        'username'=>$username,'secret_file'=>$passwordfile,'scope'=>'isolated UAT only']).PHP_EOL;
} catch (Throwable $e) {
    DBend(false);
    throw new RuntimeException('Native API recovery failed; inspect protected state', 0, $e);
}
