<?php
// Perfil "ness.OS Hub Sync" e usuário svc_ness_sync, usados por glpi_team_sync (Hub). Aplicado em produção em 25/11.
// Imprime só a linha NINF_GLPI_TEAM_USER_TOKEN=... em stdout (redirecionar direto para o env, nunca para a tela).
// Uso: sudo -n docker exec -i -u www-data ninf-glpi php -- < glpi-sync-user.php | sudo -n tee -a /etc/ness-os/glpi-integration.env
// Rotação: apagar a linha antiga do env e rodar de novo com o usuário já existente (só regenera o token).
// `config` é exigido pelo GLPI para ler/editar ações e critérios de regra (RuleAction/RuleCriteria herdam de Rule).
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
global $DB;
$log = fn(string $m) => fwrite(STDERR, $m . PHP_EOL);
Session::callAsSystem(function () use ($DB, $log) {
    $DB->beginTransaction();
    try {
        $p = $DB->request(['FROM' => 'glpi_profiles', 'WHERE' => ['name' => 'ness.OS Hub Sync']])->current();
        $pid = $p ? (int)$p['id'] : (int)(new Profile())->add(['name' => 'ness.OS Hub Sync', 'interface' => 'central',
            'is_default' => 0, 'comment' => 'Conta do Hub para sincronizar pessoas, grupos e regras. Sem direitos de chamado.']);
        if (!$pid) { throw new RuntimeException('perfil'); }
        ProfileRight::updateProfileRights($pid, ['user' => 31, 'group' => 31, 'rule_ticket' => 31,
            'entity' => 33, 'profile' => 1, 'config' => READ | UPDATE]);
        $row = $DB->request(['FROM' => 'glpi_users', 'WHERE' => ['name' => 'svc_ness_sync']])->current();
        if ($row) {
            $uid = (int)$row['id'];
        } else {
            $pw = bin2hex(random_bytes(12)) . 'Aa1!';
            $uid = (int)(new User())->add(['name' => 'svc_ness_sync', 'realname' => 'ness.OS Hub Sync',
                'is_active' => 1, 'authtype' => 1, 'password' => $pw, 'password2' => $pw]);
            if (!$uid) { throw new RuntimeException('usuario'); }
            if (!(new Profile_User())->add(['users_id' => $uid, 'profiles_id' => $pid, 'entities_id' => 0, 'is_recursive' => 1])) {
                throw new RuntimeException('habilitacao');
            }
        }
        (new User())->update(['id' => $uid, '_regenerate_api_token' => 1]);
        $tok = (new GLPIKey())->decrypt($DB->request(['FROM' => 'glpi_users', 'WHERE' => ['id' => $uid]])->current()['api_token']);
        $DB->commit();
        echo "NINF_GLPI_TEAM_USER_TOKEN=$tok" . PHP_EOL;
    } catch (Throwable $e) {
        $DB->rollBack();
        $log('ERRO ' . $e->getMessage());
        exit(1);
    }
});
