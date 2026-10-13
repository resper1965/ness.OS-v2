<?php

define('GLPI_ROOT', __DIR__);

class PluginNessaiConfig {
    public static function getConfig(string $key, mixed $default = null): mixed {
        return $key === 'enable_kb_search' ? true : $default;
    }
}

class Toolbox {
    public static function logError(string $message): void {}
}

class FakeResult {
    private int $offset = 0;
    public function __construct(private array $rows) {}
    public function fetch_assoc(): ?array { return $this->rows[$this->offset++] ?? null; }
}

class FakeStatement {
    private int $entityId = 0;
    public function __construct(private FakeDB $db, public string $sql) {}
    public function bind_param(string $types, mixed &...$params): void {
        if ($types !== 'sis') {
            throw new RuntimeException('Entity-bound query required');
        }
        $this->entityId = (int) $params[1];
    }
    public function execute(): void {}
    public function get_result(): FakeResult {
        return new FakeResult(array_values(array_filter(
            $this->db->rows,
            fn(array $row): bool => $row['entities_id'] === $this->entityId
        )));
    }
    public function close(): void {}
}

class FakeDB {
    public int $queries = 0;
    public array $rows = [
        ['id' => 1, 'entities_id' => 1],
        ['id' => 2, 'entities_id' => 2],
        ['id' => 3, 'entities_id' => 1],
    ];
    public function prepare(string $query): FakeStatement {
        $this->queries++;
        if (!str_contains($query, 'glpi_entities_knowbaseitems')
            || !str_contains($query, 'eki.`entities_id` = ?')) {
            throw new RuntimeException('KB exact-entity predicate missing');
        }
        return new FakeStatement($this, $query);
    }
}

class KnowbaseItem {
    public array $fields = [];
    public function getFromDB(int $id): bool {
        $this->fields = match ($id) {
            1 => ['name' => 'visible', 'answer' => 'Visible answer'],
            2 => ['name' => 'foreign', 'answer' => 'Foreign secret'],
            3 => ['name' => 'restricted', 'answer' => 'Restricted secret'],
            default => [],
        };
        return $this->fields !== [];
    }
    public function canViewItem(): bool { return ($this->fields['name'] ?? '') === 'visible'; }
}

$DB = new FakeDB();
require __DIR__ . '/../inc/assistant.class.php';

$append = new ReflectionMethod(PluginNessaiAssistant::class, 'appendKbContext');
$withoutEntity = $append->invoke(null, ['name' => 'test', 'content' => 'test']);
if ($withoutEntity !== '' || $DB->queries !== 0) {
    throw new RuntimeException('KB search must fail closed without ticket entity');
}

$context = $append->invoke(null, ['name' => 'test', 'content' => 'test', 'entities_id' => 1]);
if (!str_contains($context, 'Visible answer')
    || str_contains($context, 'Foreign secret')
    || str_contains($context, 'Restricted secret')) {
    throw new RuntimeException('KB context crossed entity or native article visibility');
}

echo "PASS: KB context isolated to ticket entity and native visibility\n";
