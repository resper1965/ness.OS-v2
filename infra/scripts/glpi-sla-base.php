<?php
// SLA por tipo de atuação, sem cadastro por cliente (spec 2026-11-24, Task 2b revista).
// Padrão interno do Hub: crítica (prioridade 5) 15/240 min, alta (4) 30/480 min. Ajuste depois no GLPI.
//   NOC (categoria 4): TTO + TTR   SOC (categoria 5): só TTO   Serviço: sem SLA.
// Calendário 24x7 (o Hub usa calendário próprio para avisar; aqui o relógio do chamado).
// Sem --apply só mostra o que faria. Idempotente. Nunca apaga.
// Uso: sudo -n docker exec -i -u www-data ninf-glpi php -- [--apply] < glpi-sla-base.php
$apply = in_array('--apply', $argv, true);
require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();
global $DB, $CFG_GLPI;
if ((int)($CFG_GLPI['use_notifications'] ?? 1) !== 0) {
    throw new RuntimeException('Notificações do GLPI precisam estar desligadas');
}
$out = fn(string $op, string $what) => print(json_encode(['op' => $op, 'item' => $what], JSON_UNESCAPED_UNICODE) . PHP_EOL);
const NOC = 4;
const SOC = 5;
// [prioridade GLPI, TTO min, TTR min]
$NOC = [5 => [15, 240], 4 => [30, 480]];
$SOC = [5 => [15, null], 4 => [30, null]];

function find(string $table, array $where): ?array
{
    global $DB;
    $r = iterator_to_array($DB->request(['FROM' => $table, 'WHERE' => $where]));
    return $r ? reset($r) : null;
}

Session::callAsSystem(function () use ($apply, $out, $NOC, $SOC) {
    global $DB;
    $DB->beginTransaction();
    try {
        // Calendário 24x7: GLPI sem segmentos conta o dia todo? Não: precisa de um calendário com 7 dias.
        $cal = find('glpi_calendars', ['name' => 'ness · 24x7']);
        if (!$cal) {
            $out('CREATE', 'calendário ness · 24x7');
            if ($apply) {
                $c = new Calendar();
                $cid = (int)$c->add(['name' => 'ness · 24x7', 'entities_id' => 0, 'is_recursive' => 1,
                    'comment' => 'Gerido pelo ness.OS (SLA padrão). Atendimento 24x7.']);
                if (!$cid) {
                    throw new RuntimeException('Falha no calendário');
                }
                for ($d = 0; $d <= 6; $d++) {
                    if (!(new CalendarSegment())->add(['calendars_id' => $cid, 'day' => $d,
                        'begin' => '00:00:00', 'end' => '24:00:00', 'entities_id' => 0, 'is_recursive' => 1])) {
                        throw new RuntimeException("Falha no segmento $d");
                    }
                }
                $cal = ['id' => $cid];
            }
        } else {
            $out('OK', 'calendário ness · 24x7');
        }
        $calId = (int)($cal['id'] ?? 0);

        // Um SLM por tipo de atuação. SLA = (nome, tipo TTO/TTR, minutos).
        $plan = [
            'ness · Atuação direta (NOC)' => ['cat' => NOC, 'rows' => $NOC],
            'ness · nSecOps (SOC)' => ['cat' => SOC, 'rows' => $SOC],
        ];
        $slaIds = [];
        foreach ($plan as $slmName => $p) {
            $slm = find('glpi_slms', ['name' => $slmName]);
            if (!$slm) {
                $out('CREATE', "SLM $slmName");
                if ($apply) {
                    $id = (int)(new SLM())->add(['name' => $slmName, 'entities_id' => 0, 'is_recursive' => 1,
                        'calendars_id' => $calId, 'use_ticket_calendar' => 0,
                        'comment' => 'Gerido pelo ness.OS. Padrão interno; ajuste os prazos aqui.']);
                    if (!$id) {
                        throw new RuntimeException("Falha no SLM $slmName");
                    }
                    $slm = ['id' => $id];
                }
            } else {
                $out('OK', "SLM $slmName");
            }
            foreach ($p['rows'] as $prio => [$tto, $ttr]) {
                foreach ([[SLM::TTO, $tto, 'TTO'], [SLM::TTR, $ttr, 'TTR']] as [$type, $min, $lbl]) {
                    if ($min === null) {
                        continue;
                    }
                    $name = "$slmName · prioridade $prio · $lbl";
                    $sla = find('glpi_slas', ['name' => $name]);
                    if (!$sla) {
                        $out('CREATE', "SLA $name ({$min} min)");
                        if ($apply) {
                            $id = (int)(new SLA())->add(['name' => $name, 'slms_id' => $slm['id'], 'type' => $type,
                                'number_time' => $min, 'definition_time' => 'minute', 'entities_id' => 0,
                                'is_recursive' => 1, 'calendars_id' => $calId, 'use_ticket_calendar' => 0]);
                            if (!$id) {
                                throw new RuntimeException("Falha no SLA $name");
                            }
                            $sla = ['id' => $id];
                        }
                    } elseif ((int)$sla['number_time'] !== $min || $sla['definition_time'] !== 'minute') {
                        $out('KEEP', "SLA $name já difere ({$sla['number_time']} {$sla['definition_time']}); ajuste do GLPI preservado");
                    } else {
                        $out('OK', "SLA $name");
                    }
                    $slaIds[$p['cat']][$prio][$type] = $sla['id'] ?? null;
                }
            }
        }

        // Regra: categoria + prioridade -> SLA. Entra DEPOIS das regras de entidade (grupo).
        foreach ($plan as $slmName => $p) {
            foreach ($p['rows'] as $prio => $_) {
                $rname = "ness-sla " . ($p['cat'] === NOC ? 'NOC' : 'SOC') . " prioridade $prio";
                $rule = find('glpi_rules', ['name' => $rname, 'sub_type' => 'RuleTicket']);
                $ids = $slaIds[$p['cat']][$prio] ?? [];
                if ($rule) {
                    $out('OK', "regra $rname");
                    continue;
                }
                $out('CREATE', "regra $rname (inativa até completa)");
                if (!$apply) {
                    continue;
                }
                $max = (int)($DB->request(['SELECT' => ['MAX' => 'ranking AS m'], 'FROM' => 'glpi_rules',
                    'WHERE' => ['sub_type' => 'RuleTicket']])->current()['m'] ?? 0);
                $rid = (int)(new Rule())->add(['name' => $rname, 'sub_type' => 'RuleTicket', 'entities_id' => 0,
                    'is_recursive' => 1, 'is_active' => 0, 'match' => 'AND', 'ranking' => $max + 1,
                    'condition' => RuleTicket::ONADD + RuleTicket::ONUPDATE,
                    'comment' => 'Gerido pelo ness.OS. Prazo do padrão interno.']);
                if (!$rid) {
                    throw new RuntimeException("Falha na regra $rname");
                }
                $crit = [['itilcategories_id', Rule::PATTERN_UNDER, $p['cat']], ['priority', Rule::PATTERN_IS, $prio]];
                foreach ($crit as [$c, $cond, $pat]) {
                    if (!(new RuleCriteria())->add(['rules_id' => $rid, 'criteria' => $c, 'condition' => $cond, 'pattern' => $pat])) {
                        throw new RuntimeException("Falha no critério $c");
                    }
                }
                foreach ([SLM::TTO => 'slas_id_tto', SLM::TTR => 'slas_id_ttr'] as $type => $field) {
                    if (!empty($ids[$type]) && !(new RuleAction())->add(['rules_id' => $rid, 'action_type' => 'assign',
                        'field' => $field, 'value' => $ids[$type]])) {
                        throw new RuntimeException("Falha na ação $field");
                    }
                }
                if (!(new Rule())->update(['id' => $rid, 'is_active' => 1])) {
                    throw new RuntimeException("Falha ao ativar $rname");
                }
            }
        }
        $DB->commit();
    } catch (Throwable $e) {
        $DB->rollBack();
        throw $e;
    }
});
echo json_encode(['mode' => $apply ? 'apply' : 'preview']) . PHP_EOL;
