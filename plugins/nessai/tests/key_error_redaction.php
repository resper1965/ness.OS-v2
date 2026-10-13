<?php

define('GLPI_ROOT', __DIR__);

class PluginNessaiConfig {
    public static function getConfig(string $key, mixed $default = null): mixed {
        return $key === 'api_key_encrypted' ? 'synthetic-encrypted-value' : $default;
    }
}

class GLPIKey {
    public function decrypt(string $encrypted): never {
        throw new RuntimeException('synthetic-secret-from-decrypt');
    }
}

require __DIR__ . '/../inc/assistant.class.php';

$result = PluginNessaiAssistant::suggest(['id' => 41, 'name' => 'ticket']);
if (str_contains($result['text'], 'synthetic-secret-from-decrypt')) {
    fwrite(STDERR, "Key failure leaked internal detail\n");
    exit(1);
}
if (($result['prompt_tokens'] ?? null) !== 0) {
    fwrite(STDERR, "Key failure returned nonzero token count\n");
    exit(1);
}
echo "PASS: key failure redacted\n";
