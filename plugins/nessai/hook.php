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

/**
 * Install the nessai plugin – create database tables and seed defaults.
 *
 * @return bool
 */
function plugin_nessai_install(): bool
{
    global $DB;

    // ------------------------------------------------------------------
    // Table: glpi_plugin_nessai_configs
    // ------------------------------------------------------------------
    if (!$DB->tableExists('glpi_plugin_nessai_configs')) {
        $DB->doQuery(
            "CREATE TABLE `glpi_plugin_nessai_configs` (
                `id`                  INT UNSIGNED    NOT NULL AUTO_INCREMENT,
                `llm_provider`        ENUM('openai','gemini','claude','ollama')
                                                      NOT NULL DEFAULT 'gemini',
                `api_key_encrypted`   TEXT            NULL,
                `api_endpoint`        VARCHAR(500)    NULL,
                `model_name`          VARCHAR(100)    NOT NULL DEFAULT 'gemini-2.5-flash',
                `system_prompt`       TEXT            NULL,
                `org_context`         TEXT            NULL,
                `max_tokens`          INT UNSIGNED    NOT NULL DEFAULT 1024,
                `temperature`         DECIMAL(2,1)    NOT NULL DEFAULT 0.3,
                `enable_kb_search`    TINYINT(1)      NOT NULL DEFAULT 1,
                `enable_auto_summary` TINYINT(1)      NOT NULL DEFAULT 1,
                `enable_translation`  TINYINT(1)      NOT NULL DEFAULT 0,
                `date_mod`            TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
                                                      ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
        );

        // Seed a default configuration row
        $systemPrompt = addslashes(
            'Você é o assistente técnico da ness., especialista em NOC e Help Desk. '
            . 'Responda de forma direta e profissional em português brasileiro. '
            . 'Quando disponível, referencie artigos da base de conhecimento interna.'
        );

        $DB->doQuery(
            "INSERT INTO `glpi_plugin_nessai_configs`
                (`llm_provider`, `model_name`, `system_prompt`)
             VALUES
                ('gemini', 'gemini-2.5-flash', '{$systemPrompt}')"
        );
    }

    // ------------------------------------------------------------------
    // Table: glpi_plugin_nessai_logs
    // ------------------------------------------------------------------
    if (!$DB->tableExists('glpi_plugin_nessai_logs')) {
        $DB->doQuery(
            "CREATE TABLE `glpi_plugin_nessai_logs` (
                `id`               INT UNSIGNED    NOT NULL AUTO_INCREMENT,
                `tickets_id`       INT UNSIGNED    NOT NULL,
                `users_id`         INT UNSIGNED    NOT NULL,
                `action`           ENUM('suggest','summarize','translate')
                                                   NOT NULL,
                `prompt_tokens`    INT UNSIGNED    NOT NULL DEFAULT 0,
                `completion_tokens` INT UNSIGNED   NOT NULL DEFAULT 0,
                `llm_provider`     VARCHAR(50)     NOT NULL,
                `model_name`       VARCHAR(100)    NOT NULL,
                `response_time_ms` INT UNSIGNED    NOT NULL DEFAULT 0,
                `date_creation`    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                INDEX `idx_tickets_id` (`tickets_id`),
                INDEX `idx_users_id`   (`users_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
        );
    }

    return true;
}

/**
 * Uninstall the nessai plugin – drop all plugin tables.
 *
 * @return bool
 */
function plugin_nessai_uninstall(): bool
{
    global $DB;

    $tables = [
        'glpi_plugin_nessai_configs',
        'glpi_plugin_nessai_logs',
    ];

    foreach ($tables as $table) {
        if ($DB->tableExists($table)) {
            $DB->doQuery("DROP TABLE `{$table}`");
        }
    }

    return true;
}
