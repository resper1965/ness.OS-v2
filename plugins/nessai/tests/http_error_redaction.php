<?php

define('GLPI_ROOT', __DIR__);

$listener = stream_socket_server('tcp://127.0.0.1:0', $errorCode, $errorMessage);
if ($listener === false) {
    throw new RuntimeException('Unable to reserve a local test port');
}
$port = (int) substr(strrchr(stream_socket_get_name($listener, false), ':'), 1);
fclose($listener);

class PluginNessaiConfig {
    public static int $port;
    public static string $path = '';
    public static function getConfig(string $key, mixed $default = null): mixed {
        return $key === 'llm_provider' ? 'ollama'
            : ($key === 'api_endpoint' ? 'http://127.0.0.1:' . self::$port . self::$path : $default);
    }
}

class Toolbox {
    public static array $errors = [];
    public static function logError(string $message): void { self::$errors[] = $message; }
}

PluginNessaiConfig::$port = $port;
$router = tempnam(sys_get_temp_dir(), 'nessai-http-');
file_put_contents($router, <<<'PHP'
<?php
if (str_starts_with($_SERVER['REQUEST_URI'], '/malformed/')) {
    echo 'synthetic-private-provider-detail-not-json';
    return;
}
http_response_code(429);
header('Content-Type: application/json');
echo json_encode(['error' => ['message' => 'synthetic-private-provider-detail']]);
PHP);

$process = proc_open([PHP_BINARY, '-S', "127.0.0.1:$port", $router],
    [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
if (!is_resource($process)) {
    unlink($router);
    throw new RuntimeException('Unable to start local test provider');
}

try {
    $ready = false;
    for ($attempt = 0; $attempt < 30; $attempt++) {
        $socket = @fsockopen('127.0.0.1', $port, $errorCode, $errorMessage, 0.1);
        if ($socket !== false) {
            fclose($socket);
            $ready = true;
            break;
        }
        usleep(50000);
    }
    if (!$ready) {
        throw new RuntimeException('Local test provider did not start');
    }

    require __DIR__ . '/../inc/assistant.class.php';
    $result = PluginNessaiAssistant::suggest(['id' => 41, 'name' => 'ticket']);
    if (!str_contains($result['text'], 'Erro:')
        || str_contains($result['text'], 'synthetic-private-provider-detail')
        || str_contains(implode('\n', Toolbox::$errors), 'synthetic-private-provider-detail')) {
        fwrite(STDERR, "Provider HTTP detail escaped to user or log\n");
        exit(1);
    }
    echo "PASS: provider HTTP error redacted\n";

    PluginNessaiConfig::$path = '/malformed';
    Toolbox::$errors = [];
    $malformed = PluginNessaiAssistant::suggest(['id' => 41, 'name' => 'ticket']);
    if (!str_contains($malformed['text'], 'Erro:')
        || str_contains($malformed['text'], 'synthetic-private-provider-detail')
        || str_contains(implode('\n', Toolbox::$errors), 'synthetic-private-provider-detail')) {
        fwrite(STDERR, "Malformed provider response escaped to user or log\n");
        exit(1);
    }
    echo "PASS: malformed provider response redacted\n";
} finally {
    proc_terminate($process);
    foreach ($pipes as $pipe) {
        fclose($pipe);
    }
    proc_close($process);
    unlink($router);
}
