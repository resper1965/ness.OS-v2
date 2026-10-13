<?php

/**
 * -------------------------------------------------------------------------
 * ness. AI - Plugin for GLPI
 * -------------------------------------------------------------------------
 *
 * LICENSE
 *
 * This file is part of ness. AI.
 *
 * ness. AI is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3 of the License, or
 * (at your option) any later version.
 *
 * ness. AI is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with ness. AI. If not, see <http://www.gnu.org/licenses/>.
 * -------------------------------------------------------------------------
 * @copyright Copyright (C) 2026 ness.
 * @license   GPLv3 https://www.gnu.org/licenses/gpl-3.0.html
 * @link      https://ness.com.br
 * -------------------------------------------------------------------------
 */

include('../../../inc/includes.php');

header('Content-Type: application/json; charset=utf-8');

try {
    // ---- Authentication check ----
    Session::checkLoginUser();

    // ---- Read & validate POST parameters ----
    $ticketId = (int) ($_POST['ticket_id'] ?? 0);
    $action   = trim($_POST['action'] ?? '');

    $allowedActions = ['suggest', 'summarize', 'translate'];

    if (!in_array($action, $allowedActions, true)) {
        throw new \InvalidArgumentException(
            "Ação inválida '{$action}'. Valores permitidos: " . implode(', ', $allowedActions)
        );
    }

    if ($ticketId <= 0) {
        throw new \InvalidArgumentException('ticket_id inválido ou ausente.');
    }

    // ---- Load the Ticket ----
    $ticket = new Ticket();
    if (!$ticket->getFromDB($ticketId)) {
        throw new \RuntimeException("Ticket #{$ticketId} não encontrado.");
    }
    if (!$ticket->canViewItem()) {
        http_response_code(403);
        echo json_encode([
            'success' => false,
            'error'   => 'Acesso negado ao ticket.',
        ], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
        return;
    }

    // ---- Build ticket context ----
    global $DB;

    // Category name via JOIN
    $categoryName = '';
    if ($ticket->fields['itilcategories_id'] > 0) {
        $catIterator = $DB->request([
            'SELECT' => ['name'],
            'FROM'   => 'glpi_itilcategories',
            'WHERE'  => ['id' => $ticket->fields['itilcategories_id']],
            'LIMIT'  => 1,
        ]);
        foreach ($catIterator as $catRow) {
            $categoryName = $catRow['name'];
        }
    }

    $ticketData = [
        'id'       => $ticketId,
        'name'     => $ticket->fields['name'],
        'content'  => $ticket->fields['content'],
        'type'     => $ticket->fields['type'],
        'urgency'  => $ticket->fields['urgency'],
        'priority' => $ticket->fields['priority'],
        'category' => $categoryName,
    ];

    // ---- Load last 5 follow-ups ----
    $followups = [];
    $fuIterator = $DB->request([
        'SELECT'   => ['id', 'content', 'date', 'users_id'],
        'FROM'     => 'glpi_itilfollowups',
        'WHERE'    => [
            'itemtype' => 'Ticket',
            'items_id' => $ticketId,
        ],
        'ORDER'    => 'date DESC',
        'LIMIT'    => 5,
    ]);

    foreach ($fuIterator as $fuRow) {
        $followups[] = [
            'id'       => (int) $fuRow['id'],
            'content'  => $fuRow['content'],
            'date'     => $fuRow['date'],
            'users_id' => (int) $fuRow['users_id'],
        ];
    }

    // ---- Delegate to the Assistant class ----
    $startMs = (int) (microtime(true) * 1000);

    /** @var array{response: string, prompt_tokens: int, completion_tokens: int} $result */
    $result = PluginNessaiAssistant::$action($ticketData, $followups);

    $elapsedMs = (int) (microtime(true) * 1000) - $startMs;

    // ---- Load current config for provider/model metadata ----
    $configRow = $DB->request([
        'SELECT' => ['llm_provider', 'model_name'],
        'FROM'   => 'glpi_plugin_nessai_configs',
        'LIMIT'  => 1,
    ]);

    $provider  = 'gemini';
    $modelName = 'gemini-2.5-flash';
    foreach ($configRow as $cfgRow) {
        $provider  = $cfgRow['llm_provider'];
        $modelName = $cfgRow['model_name'];
    }

    // ---- Log the interaction ----
    $DB->doQuery(
        "INSERT INTO `glpi_plugin_nessai_logs`
            (`tickets_id`, `users_id`, `action`, `prompt_tokens`,
             `completion_tokens`, `llm_provider`, `model_name`, `response_time_ms`)
         VALUES
            ({$ticketId},
             " . (int) Session::getLoginUserID() . ",
             '{$action}',
             " . (int) ($result['prompt_tokens'] ?? 0) . ",
             " . (int) ($result['completion_tokens'] ?? 0) . ",
             '" . $DB->escape($provider) . "',
             '" . $DB->escape($modelName) . "',
             {$elapsedMs})"
    );

    // ---- Return success response ----
    echo json_encode([
        'success'  => true,
        'response' => $result['response'] ?? '',
        'tokens'   => [
            'prompt'     => (int) ($result['prompt_tokens'] ?? 0),
            'completion' => (int) ($result['completion_tokens'] ?? 0),
        ],
        'time_ms'  => $elapsedMs,
    ], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);

} catch (\Throwable $e) {
    http_response_code(400);
    echo json_encode([
        'success' => false,
        'error'   => $e->getMessage(),
    ], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
}
