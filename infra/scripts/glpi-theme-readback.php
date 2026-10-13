<?php
/** Read-only GLPI palette discovery check; prints no configuration or secrets. */

require '/var/www/glpi/vendor/autoload.php';
$kernel = new \Glpi\Kernel\Kernel();
$kernel->boot();

$theme = \Glpi\UI\ThemeManager::getInstance()->getTheme('ness-light');
if ($theme === null || $theme->getName() !== 'ness.') {
    fwrite(STDERR, "ness. palette is not recognized\n");
    exit(1);
}

echo json_encode(['theme' => $theme->getKey(), 'label' => $theme->getName()]) . PHP_EOL;
