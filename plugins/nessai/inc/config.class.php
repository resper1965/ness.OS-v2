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
 * @copyright Copyright (C) 2024-2026 ness. Tecnologia
 * @license   GPLv3 https://www.gnu.org/licenses/gpl-3.0.html
 * @link      https://ness.com.br
 * -------------------------------------------------------------------------
 */

if (!defined('GLPI_ROOT')) {
    die("Sorry. You can't access this file directly");
}

/**
 * PluginNessaiConfig - Configuration management for ness. AI plugin.
 *
 * Handles LLM provider selection, API key encryption/decryption,
 * model parameters, and feature toggles. Renders a Tabler-styled
 * configuration form in the GLPI Setup > General tab.
 */
class PluginNessaiConfig extends CommonDBTM
{
    /** @var string[] Cached configuration values */
    private static array $configCache = [];

    /** @var bool Whether the cache has been loaded */
    private static bool $cacheLoaded = false;

    /**
     * Available LLM providers with display labels.
     */
    private const LLM_PROVIDERS = [
        'openai'  => 'OpenAI',
        'gemini'  => 'Google Gemini',
        'claude'  => 'Anthropic Claude',
        'ollama'  => 'Ollama Local',
    ];

    /**
     * Default configuration values for fresh installations.
     */
    private const DEFAULTS = [
        'llm_provider'       => 'openai',
        'api_key_encrypted'  => '',
        'api_endpoint'       => 'http://localhost:11434',
        'model_name'         => 'gpt-4o-mini',
        'system_prompt'      => 'Você é um assistente técnico de TI especializado em suporte helpdesk. Responda de forma profissional, clara e objetiva.',
        'org_context'        => '',
        'max_tokens'         => '1024',
        'temperature'        => '0.7',
        'enable_kb_search'   => '0',
        'enable_auto_summary' => '0',
        'enable_translation' => '0',
    ];

    // ──────────────────────────────────────────────────────────────
    //  Tab interface (CommonGLPI)
    // ──────────────────────────────────────────────────────────────

    /**
     * @inheritDoc
     */
    public function getTabNameForItem(CommonGLPI $item, $withtemplate = 0): string
    {
        if (!($item instanceof Config)) {
            return '';
        }

        if (!Session::haveRight('config', READ)) {
            return '';
        }

        return '<i class="ti ti-robot me-1"></i>' . __('ness. AI', 'nessai');
    }

    /**
     * @inheritDoc
     */
    public static function displayTabContentForItem(
        CommonGLPI $item,
        $tabnum = 1,
        $withtemplate = 0
    ): bool {
        if ($item instanceof Config) {
            $config = new self();
            $config->show();
        }

        return true;
    }

    // ──────────────────────────────────────────────────────────────
    //  Configuration read / write helpers
    // ──────────────────────────────────────────────────────────────

    /**
     * Retrieve a single configuration value by name.
     *
     * Results are cached in a static variable so repeated calls within
     * the same request don't hit the database again.
     *
     * @param string     $name         Configuration key.
     * @param mixed|null $defaultValue Fallback when key is absent.
     *
     * @return mixed
     */
    public static function getConfig(string $name, mixed $defaultValue = null): mixed
    {
        if (!self::$cacheLoaded) {
            $values = Config::getConfigurationValues('nessai');
            self::$configCache = is_array($values) ? $values : [];
            self::$cacheLoaded = true;
        }

        if (array_key_exists($name, self::$configCache)) {
            return self::$configCache[$name];
        }

        // Fall back to hard-coded default, then caller-supplied default.
        return self::DEFAULTS[$name] ?? $defaultValue;
    }

    /**
     * Persist a single configuration value.
     *
     * @param string $name  Configuration key.
     * @param mixed  $value Value to store.
     */
    public static function setConfig(string $name, mixed $value): void
    {
        Config::setConfigurationValues('nessai', [$name => $value]);

        // Invalidate cache so the next read picks up the new value.
        self::$configCache[$name] = $value;
    }

    // ──────────────────────────────────────────────────────────────
    //  Form rendering
    // ──────────────────────────────────────────────────────────────

    /**
     * Render the Tabler-styled configuration form.
     *
     * Displayed inside the GLPI Setup > General panel as a custom tab.
     */
    public function show(): void
    {
        if (!Session::haveRight('config', READ)) {
            return;
        }

        $canUpdate = Session::haveRight('config', UPDATE);

        // ── Read current values ──────────────────────────────────
        $provider     = self::getConfig('llm_provider', 'openai');
        $apiEndpoint  = self::getConfig('api_endpoint', 'http://localhost:11434');
        $modelName    = self::getConfig('model_name', 'gpt-4o-mini');
        $systemPrompt = self::getConfig('system_prompt', self::DEFAULTS['system_prompt']);
        $orgContext   = self::getConfig('org_context', '');
        $maxTokens    = (int) self::getConfig('max_tokens', 1024);
        $temperature  = (float) self::getConfig('temperature', 0.7);
        $enableKb     = (bool) self::getConfig('enable_kb_search', false);
        $enableSummary = (bool) self::getConfig('enable_auto_summary', false);
        $enableTranslation = (bool) self::getConfig('enable_translation', false);

        // Decrypt API key to check if one exists (never display the real key).
        $encryptedKey = self::getConfig('api_key_encrypted', '');
        $hasApiKey    = false;
        if (!empty($encryptedKey)) {
            try {
                $decrypted = (new GLPIKey())->decrypt($encryptedKey);
                $hasApiKey = !empty($decrypted);
            } catch (\Throwable) {
                $hasApiKey = false;
            }
        }

        $formAction = Toolbox::getItemTypeFormURL('Config');

        // ── Begin form ───────────────────────────────────────────
        echo '<form name="form" action="' . $formAction . '" method="post">';
        echo Html::hidden('config_context', ['value' => 'nessai']);
        echo Html::hidden('config_class', ['value' => __CLASS__]);

        echo '<div class="card mb-4">';
        echo '<div class="card-header">';
        echo '<h3 class="card-title">';
        echo '<i class="ti ti-robot me-2"></i>';
        echo __('ness. AI — Configurações do Assistente', 'nessai');
        echo '</h3>';
        echo '</div>'; // .card-header

        echo '<div class="card-body">';

        // ── LLM Provider ─────────────────────────────────────────
        echo '<div class="row mb-3">';
        echo '<label class="col-lg-3 col-form-label">';
        echo __('Provedor LLM', 'nessai');
        echo '</label>';
        echo '<div class="col-lg-9">';
        echo '<select name="llm_provider" id="nessai_llm_provider" class="form-select"';
        if (!$canUpdate) {
            echo ' disabled';
        }
        echo '>';
        foreach (self::LLM_PROVIDERS as $value => $label) {
            $selected = ($value === $provider) ? ' selected' : '';
            echo "<option value=\"{$value}\"{$selected}>{$label}</option>";
        }
        echo '</select>';
        echo '</div>';
        echo '</div>';

        // ── API Key ──────────────────────────────────────────────
        echo '<div class="row mb-3">';
        echo '<label class="col-lg-3 col-form-label">';
        echo __('Chave de API', 'nessai');
        echo '</label>';
        echo '<div class="col-lg-9">';
        echo '<input type="password" name="api_key" class="form-control"';
        echo ' autocomplete="new-password"';
        echo ' placeholder="' . ($hasApiKey ? '••••••••' : __('Cole sua chave de API aqui', 'nessai')) . '"';
        echo ' value="' . ($hasApiKey ? '••••••••' : '') . '"';
        if (!$canUpdate) {
            echo ' disabled';
        }
        echo '>';
        if ($hasApiKey) {
            echo '<div class="form-text text-muted">';
            echo '<i class="ti ti-lock me-1"></i>';
            echo __('Chave armazenada de forma criptografada. Deixe em branco para manter a atual.', 'nessai');
            echo '</div>';
        }
        echo '</div>';
        echo '</div>';

        // ── API Endpoint (Ollama only) ───────────────────────────
        $ollamaDisplay = ($provider === 'ollama') ? '' : ' style="display:none;"';
        echo '<div class="row mb-3 nessai-ollama-field"' . $ollamaDisplay . '>';
        echo '<label class="col-lg-3 col-form-label">';
        echo __('Endpoint da API', 'nessai');
        echo '</label>';
        echo '<div class="col-lg-9">';
        echo '<input type="text" name="api_endpoint" class="form-control"';
        echo ' value="' . htmlspecialchars($apiEndpoint, ENT_QUOTES, 'UTF-8') . '"';
        echo ' placeholder="http://localhost:11434"';
        if (!$canUpdate) {
            echo ' disabled';
        }
        echo '>';
        echo '<div class="form-text text-muted">';
        echo __('URL do servidor Ollama local (ex: http://localhost:11434)', 'nessai');
        echo '</div>';
        echo '</div>';
        echo '</div>';

        // ── Model Name ───────────────────────────────────────────
        echo '<div class="row mb-3">';
        echo '<label class="col-lg-3 col-form-label">';
        echo __('Nome do Modelo', 'nessai');
        echo '</label>';
        echo '<div class="col-lg-9">';
        echo '<input type="text" name="model_name" class="form-control"';
        echo ' value="' . htmlspecialchars($modelName, ENT_QUOTES, 'UTF-8') . '"';
        echo ' placeholder="gpt-4o-mini"';
        if (!$canUpdate) {
            echo ' disabled';
        }
        echo '>';
        echo '</div>';
        echo '</div>';

        // ── System Prompt ────────────────────────────────────────
        echo '<div class="row mb-3">';
        echo '<label class="col-lg-3 col-form-label">';
        echo __('Prompt do Sistema', 'nessai');
        echo '</label>';
        echo '<div class="col-lg-9">';
        echo '<textarea name="system_prompt" class="form-control" rows="5"';
        if (!$canUpdate) {
            echo ' disabled';
        }
        echo '>' . htmlspecialchars($systemPrompt, ENT_QUOTES, 'UTF-8') . '</textarea>';
        echo '<div class="form-text text-muted">';
        echo __('Instruções gerais enviadas ao modelo em todas as requisições.', 'nessai');
        echo '</div>';
        echo '</div>';
        echo '</div>';

        // ── Organization Context ─────────────────────────────────
        echo '<div class="row mb-3">';
        echo '<label class="col-lg-3 col-form-label">';
        echo __('Contexto Organizacional', 'nessai');
        echo '</label>';
        echo '<div class="col-lg-9">';
        echo '<textarea name="org_context" class="form-control" rows="5"';
        if (!$canUpdate) {
            echo ' disabled';
        }
        echo '>' . htmlspecialchars($orgContext, ENT_QUOTES, 'UTF-8') . '</textarea>';
        echo '<div class="form-text text-muted">';
        echo __('Descreva sua organização, produtos, serviços e padrões para contextualizar as respostas da IA.', 'nessai');
        echo '</div>';
        echo '</div>';
        echo '</div>';

        // ── Max Tokens ───────────────────────────────────────────
        echo '<div class="row mb-3">';
        echo '<label class="col-lg-3 col-form-label">';
        echo __('Máximo de Tokens', 'nessai');
        echo '</label>';
        echo '<div class="col-lg-9">';
        echo '<input type="number" name="max_tokens" class="form-control"';
        echo ' value="' . $maxTokens . '"';
        echo ' min="64" max="32768" step="64"';
        if (!$canUpdate) {
            echo ' disabled';
        }
        echo '>';
        echo '</div>';
        echo '</div>';

        // ── Temperature ──────────────────────────────────────────
        echo '<div class="row mb-3">';
        echo '<label class="col-lg-3 col-form-label">';
        echo __('Temperatura', 'nessai');
        echo '</label>';
        echo '<div class="col-lg-9">';
        echo '<input type="number" name="temperature" class="form-control"';
        echo ' value="' . $temperature . '"';
        echo ' min="0" max="2" step="0.1"';
        if (!$canUpdate) {
            echo ' disabled';
        }
        echo '>';
        echo '<div class="form-text text-muted">';
        echo __('0 = determinístico, 1 = criativo, 2 = muito criativo.', 'nessai');
        echo '</div>';
        echo '</div>';
        echo '</div>';

        // ── Feature Toggles ──────────────────────────────────────
        echo '<div class="row mb-3">';
        echo '<label class="col-lg-3 col-form-label">';
        echo __('Funcionalidades', 'nessai');
        echo '</label>';
        echo '<div class="col-lg-9">';

        // KB Search
        echo '<div class="form-check form-switch mb-2">';
        echo '<input type="hidden" name="enable_kb_search" value="0">';
        echo '<input type="checkbox" name="enable_kb_search" value="1"';
        echo ' class="form-check-input" id="nessai_kb_search"';
        if ($enableKb) {
            echo ' checked';
        }
        if (!$canUpdate) {
            echo ' disabled';
        }
        echo '>';
        echo '<label class="form-check-label" for="nessai_kb_search">';
        echo '<i class="ti ti-book me-1"></i>';
        echo __('Buscar na Base de Conhecimento', 'nessai');
        echo '</label>';
        echo '</div>';

        // Auto Summary
        echo '<div class="form-check form-switch mb-2">';
        echo '<input type="hidden" name="enable_auto_summary" value="0">';
        echo '<input type="checkbox" name="enable_auto_summary" value="1"';
        echo ' class="form-check-input" id="nessai_auto_summary"';
        if ($enableSummary) {
            echo ' checked';
        }
        if (!$canUpdate) {
            echo ' disabled';
        }
        echo '>';
        echo '<label class="form-check-label" for="nessai_auto_summary">';
        echo '<i class="ti ti-list-details me-1"></i>';
        echo __('Resumo Automático da Timeline', 'nessai');
        echo '</label>';
        echo '</div>';

        // Translation
        echo '<div class="form-check form-switch mb-2">';
        echo '<input type="hidden" name="enable_translation" value="0">';
        echo '<input type="checkbox" name="enable_translation" value="1"';
        echo ' class="form-check-input" id="nessai_translation"';
        if ($enableTranslation) {
            echo ' checked';
        }
        if (!$canUpdate) {
            echo ' disabled';
        }
        echo '>';
        echo '<label class="form-check-label" for="nessai_translation">';
        echo '<i class="ti ti-language me-1"></i>';
        echo __('Tradução para Inglês', 'nessai');
        echo '</label>';
        echo '</div>';

        echo '</div>'; // .col-lg-9
        echo '</div>'; // .row

        // ── Submit ───────────────────────────────────────────────
        if ($canUpdate) {
            echo '<div class="row">';
            echo '<div class="col-lg-9 offset-lg-3">';
            echo '<button type="submit" name="update" class="btn" style="background-color:#00ade8; color:#fff;">';
            echo '<i class="ti ti-device-floppy me-1"></i>';
            echo __('Salvar configurações', 'nessai');
            echo '</button>';
            echo '</div>';
            echo '</div>';
        }

        echo '</div>'; // .card-body
        echo '</div>'; // .card

        // JavaScript: toggle Ollama endpoint visibility.
        echo <<<'JS'
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            const providerSelect = document.getElementById('nessai_llm_provider');
            if (!providerSelect) return;

            providerSelect.addEventListener('change', function() {
                const ollamaFields = document.querySelectorAll('.nessai-ollama-field');
                ollamaFields.forEach(function(el) {
                    el.style.display = (providerSelect.value === 'ollama') ? '' : 'none';
                });
            });
        });
        </script>
        JS;

        Html::closeForm();
    }

    // ──────────────────────────────────────────────────────────────
    //  Config update hook
    // ──────────────────────────────────────────────────────────────

    /**
     * Process configuration form submission.
     *
     * Called by GLPI's Config class when the form with
     * config_class = PluginNessaiConfig is submitted.
     *
     * Handles API key encryption: if the submitted value is the
     * masked placeholder or empty, the existing encrypted key is
     * preserved. Otherwise the new key is encrypted and stored.
     *
     * @param array $input Raw POST data from the form.
     *
     * @return array Processed data ready for storage.
     */
    public static function configUpdate(array $input): array
    {
        $apiKeyRaw = $input['api_key'] ?? '';

        // Only re-encrypt when the user supplies a real new key.
        if (!empty($apiKeyRaw) && $apiKeyRaw !== '••••••••') {
            $encrypted = (new GLPIKey())->encrypt($apiKeyRaw);
            $input['api_key_encrypted'] = $encrypted;
        }

        // Never store the plaintext key.
        unset($input['api_key']);

        // Invalidate static cache for the next read.
        self::$cacheLoaded = false;
        self::$configCache = [];

        return $input;
    }
}
