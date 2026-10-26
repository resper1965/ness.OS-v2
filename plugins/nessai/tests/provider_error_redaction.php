<?php

$root = sys_get_temp_dir() . '/nessai-error-' . bin2hex(random_bytes(6));
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
        'itilcategories_id' => 0, 'name' => 'ticket', 'content' => 'content',
        'type' => 1, 'urgency' => 3, 'priority' => 3,
    ];
    public function getFromDB(int $id): bool { return $id === 41; }
    public function canViewItem(): bool { return true; }
}
class FakeDB {
    public function request(array $query): array { return []; }
    public function doQuery(string $query): void {}
    public function escape(string $value): string { return $value; }
}
$DB = new FakeDB();
class PluginNessaiAssistant {
    public static function suggest(array $ticket, array $followups): never {
        throw new RuntimeException('provider-secret-synthetic');
    }
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
    if (http_response_code() !== 500 || !is_array($response)
        || ($response['success'] ?? null) !== false
        || str_contains($body, 'provider-secret-synthetic')) {
        fwrite(STDERR, "Provider detail escaped to browser: $body\n");
        exit(1);
    }
    echo "PASS: provider failure redacted\n";
} finally {
    chdir($previous);
    unlink($root . '/inc/includes.php');
    rmdir($root . '/inc');
    rmdir($root . '/plugins/nessai/front');
    rmdir($root . '/plugins/nessai');
    rmdir($root . '/plugins');
    rmdir($root);
}
