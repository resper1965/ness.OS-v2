<?php
declare(strict_types=1);
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
if (in_array('--enable', $argv, true)) {
 $saved=json_decode(file_get_contents('/var/lib/ness-os/hub-rollout/result.json'),true,512,JSON_THROW_ON_ERROR);
 $actions=(new CAction())->get(['actionids'=>[$saved['action_id']],'output'=>['actionid','name','status']]);
 if (count($actions)!==1 || $actions[0]['name']!=='ness.OS Hub - alert ingestion') {throw new RuntimeException('Action identity mismatch');}
 (new CAction())->update([['actionid'=>$saved['action_id'],'status'=>0,
  'filter'=>['evaltype'=>0,'conditions'=>[['conditiontype'=>1,'operator'=>1,'value'=>'10962']]]]]);
 echo json_encode(['action_id'=>$saved['action_id'],'enabled'=>true,'excluded_unowned_host'=>'10962']).PHP_EOL;
 exit;
}
$key=trim(file_get_contents('/var/lib/ness-os/hub-rollout/webhook.key'));
if (strlen($key)<48) {throw new RuntimeException('Webhook key missing');}
$users=(new CUser())->get(['output'=>['userid','roleid'],'filter'=>['username'=>'svc_ninfraops_api'],'selectMedias'=>'extend']);
if (count($users)!==1 || $users[0]['medias']) {throw new RuntimeException('Unexpected service media state');}
$user=$users[0];
$role=(new CRole())->get(['roleids'=>[$user['roleid']],'output'=>'extend','selectRules'=>'extend'])[0];
file_put_contents('/var/lib/ness-os/hub-rollout/role-before.json',json_encode($role));
chmod('/var/lib/ness-os/hub-rollout/role-before.json',0600);
$name='ness.OS Hub - alert ingestion';
if ((new CMediatype())->get(['filter'=>['name'=>$name]]) || (new CAction())->get(['filter'=>['name'=>$name]])) {throw new RuntimeException('Existing rollout requires inspection');}
$script= <<<'JS'
var p=JSON.parse(value), tags={}, entries=JSON.parse(p.tags || '[]');
for(var i=0;i<entries.length;i++){tags[entries[i].tag]=entries[i].value;}
var payload={event_id:p.event_id,host_id:p.host_id,host_name:p.host_name,
 trigger_id:p.trigger_id,trigger_name:p.trigger_name,severity:parseInt(p.severity,10),
 status:'PROBLEM',tags:tags};
var request=new HttpRequest();
request.addHeader('Content-Type: application/json');
request.addHeader('X-Api-Key: '+p.api_key);
var response=request.post(p.url,JSON.stringify(payload));
if(request.getStatus()!==202){throw 'Hub rejected alert: HTTP '+request.getStatus();}
return JSON.stringify({accepted:true});
JS;
$values=['url'=>'https://hub.ness.com.br/v1/alerts','api_key'=>$key,
 'event_id'=>'{EVENT.ID}','host_id'=>'{HOST.ID}','host_name'=>'{HOST.HOST}',
 'trigger_id'=>'{TRIGGER.ID}','trigger_name'=>'{EVENT.NAME}',
 'severity'=>'{EVENT.NSEVERITY}','tags'=>'{EVENT.TAGSJSON}'];
$parameters=[];foreach($values as $k=>$v){$parameters[]=['name'=>$k,'value'=>$v];}
DBstart();
try {
 $methods=$role['rules']['api']; $methods[]='event.acknowledge';
 (new CRole())->update([['roleid'=>$role['roleid'],'name'=>'n.infraops Hub Integration',
  'rules'=>['api'=>array_values(array_unique($methods)), 'actions'=>[
   ['name'=>'acknowledge_problems','status'=>1],['name'=>'add_problem_comments','status'=>1],
  ]]]]);
 $media=(new CMediatype())->create([['type'=>4,'name'=>$name,'status'=>0,'script'=>$script,
  'parameters'=>$parameters,'timeout'=>'10s','maxattempts'=>3,'attempt_interval'=>'10s']]);
 $mediaId=$media['mediatypeids'][0];
 (new CUser())->update([['userid'=>$user['userid'],'medias'=>[['mediatypeid'=>$mediaId,
  'sendto'=>['hub'],'active'=>0,'severity'=>63,'period'=>'1-7,00:00-24:00']]]]);
 $action=(new CAction())->create([['name'=>$name,'eventsource'=>0,'status'=>1,
  'filter'=>['evaltype'=>0,'conditions'=>[]],
  'operations'=>[['operationtype'=>0,'esc_step_from'=>1,'esc_step_to'=>1,
    'opmessage_usr'=>[['userid'=>$user['userid']]],
    'opmessage'=>['default_msg'=>0,'mediatypeid'=>$mediaId,'subject'=>'Hub incident','message'=>'Hub incident']]]]]);
 if (!DBend(true)) {throw new RuntimeException('Commit failed');}
 $result=['media_id'=>$mediaId,'action_id'=>$action['actionids'][0],'action_enabled'=>false,
  'role_id'=>$role['roleid'],'user_id'=>$user['userid'],'host_permissions'=>'unchanged-read-only',
  'new_api_permission'=>'event.acknowledge','actions'=>['acknowledge','comment']];
 file_put_contents('/var/lib/ness-os/hub-rollout/result.json',json_encode($result));
 echo json_encode($result).PHP_EOL;
} catch(Throwable $e) {DBend(false);throw $e;}
