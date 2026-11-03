<?php
declare(strict_types=1);
// Adds the recovery path to the Hub action: media type sends status=RESOLVED, action gets a recovery operation.
// Needs /var/lib/ness-os/hub-rollout/result.json from zabbix-hub-rollout.php. Writes *-before-recovery.json backups first.
if (!in_array('--apply', $argv, true)) {
 echo json_encode(['mode'=>'preview','write_required'=>'--apply']).PHP_EOL;
 exit;
}
chdir('/usr/share/zabbix');
require_once 'include/func.inc.php';
require_once 'include/classes/core/APP.php';
APP::getInstance()->run(APP::EXEC_MODE_API);
API::setWrapper();
$admin=DBfetch(DBselect('SELECT u.userid,u.username,u.roleid,r.type FROM users u JOIN role r ON r.roleid=u.roleid WHERE u.userid=4'));
if (!$admin || (int)$admin['type'] !== USER_TYPE_SUPER_ADMIN) {throw new RuntimeException('Administrator unavailable');}
CApiService::$userData=['userid'=>$admin['userid'],'username'=>$admin['username'],'roleid'=>$admin['roleid'],'type'=>(int)$admin['type'],'userip'=>'127.0.0.1'];
$dir='/var/lib/ness-os/hub-rollout';
$saved=json_decode(file_get_contents("$dir/result.json"),true,512,JSON_THROW_ON_ERROR);
$name='ness.OS Hub - alert ingestion';
$media=(new CMediatype())->get(['mediatypeids'=>[$saved['media_id']],'output'=>'extend','selectActions'=>['actionid']]);
$action=(new CAction())->get(['actionids'=>[$saved['action_id']],'output'=>'extend','selectOperations'=>'extend','selectRecoveryOperations'=>'extend','selectFilter'=>'extend']);
if (count($media)!==1 || $media[0]['name']!==$name || count($action)!==1 || $action[0]['name']!==$name) {throw new RuntimeException('Identity mismatch');}
if ($action[0]['recovery_operations']) {throw new RuntimeException('Recovery operation already present');}
foreach ($media[0]['parameters'] as $p) {if ($p['name']==='event_status') {throw new RuntimeException('event_status already present');}}
file_put_contents("$dir/mediatype-before-recovery.json",json_encode($media[0]));
file_put_contents("$dir/action-before-recovery.json",json_encode($action[0]));
chmod("$dir/mediatype-before-recovery.json",0600);
chmod("$dir/action-before-recovery.json",0600);
$script=$media[0]['script'];
$new=str_replace("status:'PROBLEM'","status:(p.event_status==='RESOLVED'?'RESOLVED':'PROBLEM')",$script,$n);
if ($n!==1) {throw new RuntimeException('Script layout changed');}
$params=$media[0]['parameters'];
$params[]=['name'=>'event_status','value'=>'{EVENT.STATUS}'];
$op=$action[0]['operations'][0];
DBstart();
try {
 (new CMediatype())->update([['mediatypeid'=>$saved['media_id'],'script'=>$new,'parameters'=>$params]]);
 (new CAction())->update([['actionid'=>$saved['action_id'],'recovery_operations'=>[['operationtype'=>0,
  'opmessage_usr'=>[['userid'=>$saved['user_id']]],
  'opmessage'=>['default_msg'=>0,'mediatypeid'=>$saved['media_id'],'subject'=>'Hub recovery','message'=>'Hub recovery']]]]]);
 if (!DBend(true)) {throw new RuntimeException('Commit failed');}
 echo json_encode(['media_id'=>$saved['media_id'],'action_id'=>$saved['action_id'],'recovery_operation'=>true,'event_status_param'=>true]).PHP_EOL;
} catch(Throwable $e) {DBend(false);throw $e;}
