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

Html::redirect($CFG_GLPI['root_doc'] . '/front/config.form.php?forcetab=PluginNessaiConfig$1');
