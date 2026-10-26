<?php

$root = sys_get_temp_dir() . '/nessai-access-' . bin2hex(random_bytes(6));
mkdir($root . '/plugins/nessai/front', 0700, true);
mkdir($root . '/inc', 0700, true);
$stub = <<<'PHP'
<?php
$_POST = ['ticket_id' => '41', 'action' => 'suggest'];
class Session {
    public static function checkLoginUser(): void {}
    public static function getLoginUserID(): int { return 7; }
}
class Ticket {
    public array $fields = [
        'itilcategories_id' => 0,
        'name' => 'private ticket',
        'content' => 'private content',
        'type' => 1,
        'urgency' => 3,
        'priority' => 3,
    ];
    public function getFromDB(int $id): bool { return $id === 41; }
    public function canViewItem(): bool { return false; }
}
class FakeDB {
    public function request(array $query): never { throw new RuntimeException('FORBIDDEN_DB_READ'); }
}
$DB = new FakeDB();
class PluginNessaiAssistant {
    public static function suggest(): never { throw new RuntimeException('FORBIDDEN_AI_CALL'); }
}
PHP;
file_put_contents($root . '/inc/includes.php', $stub);

$previous = getcwd();
try {
    chdir($root . '/plugins/nessai/front');
    ob_start();
    include __DIR__ . '/../front/ajax.php';
    $body = ob_get_clean();
    $response = json_decode($body, true);
    if (http_response_code() !== 403 || $response !== ['success' => false, 'error' => 'Acesso negado ao ticket.']) {
        fwrite(STDERR, "Unauthorized ticket reached data or AI processing: $body\n");
        exit(1);
    }
    echo "PASS: unauthorized ticket denied before data/AI access\n";
} finally {
    chdir($previous);
    unlink($root . '/inc/includes.php');
    rmdir($root . '/inc');
    rmdir($root . '/plugins/nessai/front');
    rmdir($root . '/plugins/nessai');
    rmdir($root . '/plugins');
    rmdir($root);
}
