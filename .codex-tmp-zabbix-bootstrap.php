<?php

declare(strict_types=1);

chdir('/usr/share/zabbix');
require_once 'include/func.inc.php';
require_once 'include/classes/core/APP.php';

APP::getInstance()->run(APP::EXEC_MODE_API);

echo json_encode([
    'app_booted' => true,
    'token_service' => class_exists('CToken'),
    'user_group_service' => class_exists('CUserGroup'),
    'user_service' => class_exists('CUser'),
], JSON_THROW_ON_ERROR) . PHP_EOL;
