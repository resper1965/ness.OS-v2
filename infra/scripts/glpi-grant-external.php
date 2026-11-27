<?php
// Dá o perfil "Técnico externo" a um usuário, só na entidade do cliente (sem recursão).
// O token de sync não faz isso de propósito: não tem direito sobre chamados. Idempotente. Nunca apaga.
// Sem --apply só mostra. Uso:
//   sudo -n docker exec -i -u www-data ninf-glpi php -- --user=<login> --entity=<id> [--apply] < glpi-grant-external.php
$apply = in_array('--apply', $argv, true);
$opt = [];
foreach ($argv as $a) {
    if (preg_match('/^--(user|entity)=(.+)$/', $a, $m)) {
        $opt[$m[1]] = $m[2];
    }
}
if (empty($opt['user']) || !ctype_digit($opt['entity'] ?? '') || (int)$opt['entity'] < 1) {
    fwrite(STDERR, "uso: --user=<login> --entity=<id da entidade do cliente, >=1> [--apply]\n");
    exit(2);
}
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
global $DB;
$out = fn(string $op, string $what) => print(json_encode(['op' => $op, 'item' => $what], JSON_UNESCAPED_UNICODE) . PHP_EOL);
$one = fn(string $t, array $w) => $DB->request(['FROM' => $t, 'WHERE' => $w])->current();

$found = $DB->request(['FROM' => 'glpi_users', 'WHERE' => ['name' => $opt['user'], 'is_active' => 1]]);
if (count($found) !== 1) {
    // Login duplicado no GLPI daria o perfil à conta errada; o sync trata isso como erro.
    fwrite(STDERR, "esperava 1 usuário ativo com login {$opt['user']}, achei " . count($found) . "\n");
    exit(1);
}
$user = $found->current();
$prof = $one('glpi_profiles', ['name' => 'Técnico externo']);
$ent = $one('glpi_entities', ['id' => (int)$opt['entity']]);
if (!$user || !$prof || !$ent) {
    fwrite(STDERR, "usuário ativo, perfil ou entidade não encontrado\n");
    exit(1);
}
$row = ['users_id' => $user['id'], 'profiles_id' => $prof['id'], 'entities_id' => $ent['id'], 'is_recursive' => 0];
if ($one('glpi_profiles_users', $row)) {
    $out('OK', "{$opt['user']} já é Técnico externo em {$ent['name']}");
    exit(0);
}
$out('CREATE', "{$opt['user']} → Técnico externo em {$ent['name']}");
if ($apply) {
    $pu = new Profile_User();
    if (!$pu->add($row + ['is_dynamic' => 0])) {
        fwrite(STDERR, "GLPI recusou o vínculo\n");
        exit(1);
    }
    $out('DONE', 'vínculo criado');
}
