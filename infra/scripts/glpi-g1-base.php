<?php
// G1, parte fixa (spec 2026-11-24): categorias NOC/SOC/Serviço, perfil Técnico externo,
// grupo Plantão e desligamento das regras de rota/SLA antigas. Pessoas e equipes vêm do
// Hub (glpi_team_sync), não daqui. Sem --apply só mostra o que faria. Idempotente.
// Uso: sudo -n docker exec -i -u www-data ninf-glpi php -- [--apply] < glpi-g1-base.php
$apply = in_array('--apply', $argv, true);
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
global $DB, $CFG_GLPI;
if ((int)($CFG_GLPI['use_notifications'] ?? 1) !== 0) {
    throw new RuntimeException('Notificações do GLPI precisam estar desligadas');
}
$out = fn(string $op, string $what) => print(json_encode(['op' => $op, 'item' => $what], JSON_UNESCAPED_UNICODE) . PHP_EOL);

Session::callAsSystem(function () use ($apply, $out, $DB) {
    $DB->beginTransaction();
    try {
    // Categorias: renomeia/reparenta as existentes, sem migrar chamado (ids preservados;
    // o Hub usa glpi_infra_category_id=4 e glpi_security_category_id=24).
    $cats = [
        4 => ['name' => 'NOC', 'parent' => 0, 'was' => 'Infraestrutura e Redes'],
        5 => ['name' => 'SOC', 'parent' => 0, 'was' => 'Segurança da Informação'],
        1 => ['name' => 'Serviço', 'parent' => 0, 'was' => 'TI'],
    ];
    foreach ($cats as $id => $c) {
        $cat = new ITILCategory();
        if (!$cat->getFromDB($id) || !in_array($cat->fields['name'], [$c['name'], $c['was']], true)) {
            throw new RuntimeException("Categoria $id inesperada");
        }
        if ($cat->fields['name'] === $c['name'] && (int)$cat->fields['itilcategories_id'] === $c['parent']) {
            $out('OK', "categoria {$c['name']}");
            continue;
        }
        $out('UPDATE', "categoria $id {$cat->fields['name']} -> {$c['name']} (raiz)");
        if ($apply && !$cat->update(['id' => $id, 'name' => $c['name'], 'itilcategories_id' => $c['parent']])) {
            throw new RuntimeException("Falha na categoria $id");
        }
    }

    // Grupo padrão da categoria atribuiria infraops/secops por cima da regra por entidade.
    foreach ($DB->request(['FROM' => 'glpi_itilcategories', 'WHERE' => ['NOT' => ['groups_id' => 0]]]) as $r) {
        $out('UPDATE', "categoria {$r['id']} {$r['name']}: limpar grupo padrão {$r['groups_id']}");
        if ($apply && !(new ITILCategory())->update(['id' => $r['id'], 'groups_id' => 0])) {
            throw new RuntimeException("Falha ao limpar grupo da categoria {$r['id']}");
        }
    }

    // Regras antigas: rota por categoria para grupo fixo e SLA por prioridade sem SLM.
    // O grupo passa a vir da entidade e o prazo do contrato (Task 1b).
    foreach ([142, 143, 144, 145, 146, 147] as $id) {
        $rule = new Rule();
        if (!$rule->getFromDB($id) || $rule->fields['sub_type'] !== 'RuleTicket') {
            throw new RuntimeException("Regra $id inesperada");
        }
        if (!(int)$rule->fields['is_active']) {
            $out('OK', "regra desligada {$rule->fields['name']}");
            continue;
        }
        $out('UPDATE', "desligar regra {$rule->fields['name']}");
        if ($apply && !$rule->update(['id' => $id, 'is_active' => 0])) {
            throw new RuntimeException("Falha na regra $id");
        }
    }

    // Plantão: vê todas as entidades (recursivo na raiz).
    $found = iterator_to_array($DB->request(['FROM' => 'glpi_groups', 'WHERE' => ['name' => 'ness · Plantão', 'entities_id' => 0]]));
    if ($found) {
        $out('OK', 'grupo ness · Plantão');
    } else {
        $out('CREATE', 'grupo ness · Plantão');
        if ($apply && !(new Group())->add(['name' => 'ness · Plantão', 'entities_id' => 0, 'is_recursive' => 1,
            'is_assign' => 1, 'is_notify' => 0, 'is_requester' => 0, 'is_watcher' => 1,
            'comment' => 'Gerido pelo ness.OS Hub. Membros vêm do cadastro de pessoas do Hub.'])) {
            throw new RuntimeException('Falha no grupo Plantão');
        }
    }

    // Técnico externo: Technician sem gestão de usuários, grupos, entidades, SLA ou transferência.
    // A restrição à entidade do cliente vem da habilitação (Profile_User não recursivo, Task 1b).
    $found = iterator_to_array($DB->request(['FROM' => 'glpi_profiles', 'WHERE' => ['name' => 'Técnico externo']]));
    $pid = $found ? (int)reset($found)['id'] : 0;
    if (!$found) {
        $out('CREATE', 'perfil Técnico externo (base Technician)');
        $tech = new Profile();
        if (!$tech->getFromDB(6) || $tech->fields['name'] !== 'Technician') {
            throw new RuntimeException('Perfil Technician inesperado');
        }
        if ($apply) {
            $fields = $tech->fields;
            unset($fields['id'], $fields['date_mod'], $fields['date_creation']);
            $fields['name'] = 'Técnico externo';
            $fields['comment'] = 'Técnico do cliente. Gerido pelo ness.OS Hub.';
            $fields['is_default'] = 0;
            foreach (['helpdesk_item_type', 'managed_domainrecordtypes'] as $f) {
                if (is_string($fields[$f] ?? null)) {
                    $fields[$f] = importArrayFromDB($fields[$f]);
                }
            }
            $pid = (int)(new Profile())->add($fields);
            if (!$pid) {
                throw new RuntimeException('Falha no perfil');
            }
        }
    }
    // Direitos: sempre reconciliados (perfil novo ou já existente), a partir do Technician.
    // Lista fechada: só o trabalho com chamados escreve; o resto fica no máximo em leitura.
    $rights = [];
    foreach ($DB->request(['FROM' => 'glpi_profilerights', 'WHERE' => ['profiles_id' => 6]]) as $r) {
        $rights[$r['name']] = (int)$r['rights'];
    }
    foreach (['user' => READ, 'group' => READ, 'entity' => READ, 'slm' => READ, 'transfer' => 0,
              'ticketcost' => 0, 'budget' => 0, 'contract' => 0] as $k => $v) {
        $rights[$k] = $v;
    }
    $write = ['ticket', 'followup', 'task', 'ticketvalidation', 'knowbase', 'reminder_public',
              'rssfeed_public', 'reservation', 'personalization'];
    foreach ($rights as $k => $v) {
        if (!in_array($k, $write, true)) {
            $rights[$k] = $v & READ;
        }
    }
    if ($pid) {
        $cur = [];
        foreach ($DB->request(['FROM' => 'glpi_profilerights', 'WHERE' => ['profiles_id' => $pid]]) as $r) {
            $cur[$r['name']] = (int)$r['rights'];
        }
        $diff = array_keys(array_filter($rights, fn($v, $k) => ($cur[$k] ?? null) !== $v, ARRAY_FILTER_USE_BOTH));
        if ($diff) {
            $out('UPDATE', 'direitos do perfil Técnico externo: ' . implode(',', $diff));
            if ($apply) {
                ProfileRight::updateProfileRights($pid, $rights);
            }
        } else {
            $out('OK', 'perfil Técnico externo');
        }
    } elseif ($apply) {
        throw new RuntimeException('Perfil sem id');
    }
        $DB->commit();
    } catch (Throwable $e) {
        $DB->rollBack();
        throw $e;
    }
});
echo json_encode(['mode' => $apply ? 'apply' : 'preview']) . PHP_EOL;
