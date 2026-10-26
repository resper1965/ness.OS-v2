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

use Glpi\Plugin\Hooks;
use Glpi\Http\Firewall;

define('PLUGIN_NESSAI_VERSION', '1.0.0');

/**
 * Init hooks, CSS/JS, config page, and menus for the nessai plugin.
 *
 * @return void
 */
function plugin_init_nessai(): void
{
    global $PLUGIN_HOOKS;

    // ---- Firewall: allow access to our AJAX endpoint ----
    Firewall::addPluginStrategyForLegacyScripts(
        'nessai',
        '#/front/ajax\\.php#',
        Firewall::STRATEGY_NO_CHECK
    );

    // ---- CSRF compliance flag (mandatory for GLPI 11.x plugins) ----
    $PLUGIN_HOOKS['csrf_compliant']['nessai'] = true;

    // ---- Only register the remaining hooks when the plugin is active ----
    $plugin = new Plugin();
    if ($plugin->isActivated('nessai')) {

        // CSS
        $PLUGIN_HOOKS[Hooks::ADD_CSS]['nessai'] = 'public/css/nessai.css';

        // JavaScript
        $PLUGIN_HOOKS[Hooks::ADD_JAVASCRIPT]['nessai'] = ['public/js/nessai.js'];

        // Configuration page
        $PLUGIN_HOOKS[Hooks::CONFIG_PAGE]['nessai'] = 'front/config.php';

        // Menu rewrite
        $PLUGIN_HOOKS[Hooks::REDEFINE_MENUS]['nessai'] = 'plugin_nessai_redefine_menus';

        // Register Config class on the main GLPI Config form (Super-Admin only)
        if (Session::getLoginUserID() && ($_SESSION['glpiactiveprofile']['id'] ?? 0) == 4) {
            Plugin::registerClass('PluginNessaiConfig', ['addtabon' => ['Config']]);
        }
    }
}

/**
 * Return plugin version information displayed in GLPI's plugin list.
 *
 * @return array<string, mixed>
 */
function plugin_version_nessai(): array
{
    return [
        'name'         => 'ness. AI',
        'version'      => PLUGIN_NESSAI_VERSION,
        'author'       => 'ness.',
        'license'      => 'GPLv3',
        'homepage'     => 'https://ness.com.br',
        'requirements' => [
            'glpi' => [
                'min' => '11.0',
            ],
            'php'  => [
                'min' => '8.1',
            ],
        ],
    ];
}

/**
 * Check prerequisites before plugin activation.
 *
 * @return bool
 */
function plugin_nessai_check_prerequisites(): bool
{
    return true;
}

/**
 * Check plugin configuration after activation.
 *
 * @return bool
 */
function plugin_nessai_check_config(): bool
{
    return true;
}

/**
 * Redefine GLPI menus to add a "ness. AI" entry under the "ness." parent.
 *
 * @param array<string, mixed> $menu Current GLPI menu structure.
 *
 * @return array<string, mixed> Modified menu structure.
 */
function plugin_nessai_redefine_menus(array $menu): array
{
    // Create the parent "ness." section if it doesn't exist yet
    if (!isset($menu['ness'])) {
        $menu['ness'] = [
            'title'   => 'ness.',
            'types'   => [],
            'content' => [],
        ];
    }

    // Add the "ness. AI" child entry
    $menu['ness']['content']['nessai'] = [
        'title' => 'ness. AI',
        'page'  => Plugin::getWebDir('nessai', true) . '/front/config.php',
        'icon'  => 'fa-solid fa-robot',
    ];

    return $menu;
}
