<?php

define('GLPI_ROOT', __DIR__);

class PluginNessaiConfig {
    public static function getConfig(string $key, mixed $default = null): mixed {
        return match ($key) {
            'llm_provider' => 'synthetic-private-config-value',
            'api_key_encrypted' => 'synthetic-ciphertext',
            default => $default,
        };
    }
}

class GLPIKey {
    public function decrypt(string $encrypted): string { return 'synthetic-key'; }
}

class Toolbox {
    public static function logError(string $message): void {}
}

require __DIR__ . '/../inc/assistant.class.php';

$result = PluginNessaiAssistant::suggest(['id' => 41, 'name' => 'ticket']);
if (str_contains($result['text'], 'synthetic-private-config-value')
    || ($result['prompt_tokens'] ?? null) !== 0) {
    fwrite(STDERR, "Provider configuration leaked in the response\n");
    exit(1);
}
echo "PASS: provider configuration redacted\n";
