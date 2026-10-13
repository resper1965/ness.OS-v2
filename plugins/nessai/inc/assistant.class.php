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
 * @copyright Copyright (C) 2024-2026 ness. Tecnologia
 * @license   GPLv3 https://www.gnu.org/licenses/gpl-3.0.html
 * @link      https://ness.com.br
 * -------------------------------------------------------------------------
 */

if (!defined('GLPI_ROOT')) {
    die("Sorry. You can't access this file directly");
}

/**
 * PluginNessaiAssistant - AI-powered ticket assistant.
 *
 * Provides three high-level actions (suggest, summarize, translate)
 * that compose a prompt from ticket data, optionally enrich it with
 * Knowledge Base articles, and dispatch it to the configured LLM
 * provider (OpenAI, Google Gemini, Anthropic Claude, or Ollama).
 */
class PluginNessaiAssistant
{
    /** @var int Maximum characters to include per KB article in the prompt */
    private const KB_ARTICLE_MAX_CHARS = 500;

    /** @var int Maximum number of KB articles to include */
    private const KB_MAX_RESULTS = 3;

    // ──────────────────────────────────────────────────────────────
    //  Public action methods
    // ──────────────────────────────────────────────────────────────

    /**
     * Generate a professional response suggestion for a ticket.
     *
     * @param array $ticketData Ticket fields (id, name, content, urgency, etc.).
     * @param array $followups  Chronological list of followup entries.
     *
     * @return array{text: string, prompt_tokens: int, completion_tokens: int}
     */
    public static function suggest(array $ticketData, array $followups = []): array
    {
        $context = self::buildContext($ticketData, $followups);

        $systemPrompt = self::buildSystemPrompt();

        $userPrompt  = "Com base no chamado abaixo, escreva uma resposta técnica profissional em Português.\n";
        $userPrompt .= "A resposta deve ser clara, objetiva e orientada à solução do problema.\n";
        $userPrompt .= "Use formatação adequada (listas, passos numerados) quando apropriado.\n\n";

        // Enrich with Knowledge Base articles if enabled.
        $userPrompt .= self::appendKbContext($ticketData);

        $userPrompt .= $context;

        return self::callLLM($systemPrompt, $userPrompt);
    }

    /**
     * Create a concise timeline summary of the ticket.
     *
     * @param array $ticketData Ticket fields.
     * @param array $followups  Chronological list of followup entries.
     *
     * @return array{text: string, prompt_tokens: int, completion_tokens: int}
     */
    public static function summarize(array $ticketData, array $followups = []): array
    {
        $context = self::buildContext($ticketData, $followups);

        $systemPrompt = self::buildSystemPrompt();

        $userPrompt  = "Crie um resumo conciso da timeline do chamado abaixo.\n";
        $userPrompt .= "Inclua: problema reportado, ações tomadas, status atual e próximos passos (se houver).\n";
        $userPrompt .= "Formato: lista cronológica com datas quando disponíveis.\n\n";

        $userPrompt .= self::appendKbContext($ticketData);

        $userPrompt .= $context;

        return self::callLLM($systemPrompt, $userPrompt);
    }

    /**
     * Translate the ticket content to English.
     *
     * @param array $ticketData Ticket fields.
     * @param array $followups  Chronological list of followup entries.
     *
     * @return array{text: string, prompt_tokens: int, completion_tokens: int}
     */
    public static function translate(array $ticketData, array $followups = []): array
    {
        $context = self::buildContext($ticketData, $followups);

        $systemPrompt  = "You are a professional translator. ";
        $systemPrompt .= "Translate the following IT support ticket content from its original language to English. ";
        $systemPrompt .= "Preserve technical terms, ticket structure, and formatting. ";
        $systemPrompt .= "Do not add commentary or interpretation — only translate.";

        $userPrompt  = "Translate the following ticket content to English:\n\n";
        $userPrompt .= $context;

        return self::callLLM($systemPrompt, $userPrompt);
    }

    // ──────────────────────────────────────────────────────────────
    //  Context builders
    // ──────────────────────────────────────────────────────────────

    /**
     * Assemble a textual context string from ticket data and followups.
     *
     * @param array $ticketData Ticket fields.
     * @param array $followups  Followup entries.
     *
     * @return string Formatted context block.
     */
    private static function buildContext(array $ticketData, array $followups): string
    {
        $lines = [];
        $lines[] = '=== CHAMADO ===';

        if (!empty($ticketData['id'])) {
            $lines[] = 'ID: #' . $ticketData['id'];
        }
        if (!empty($ticketData['name'])) {
            $lines[] = 'Título: ' . $ticketData['name'];
        }
        if (!empty($ticketData['content'])) {
            $lines[] = 'Descrição: ' . strip_tags($ticketData['content']);
        }
        if (!empty($ticketData['urgency'])) {
            $lines[] = 'Urgência: ' . self::urgencyLabel((int) $ticketData['urgency']);
        }
        if (!empty($ticketData['priority'])) {
            $lines[] = 'Prioridade: ' . self::urgencyLabel((int) $ticketData['priority']);
        }
        if (!empty($ticketData['itilcategories_id'])) {
            $lines[] = 'Categoria: ' . Dropdown::getDropdownName(
                'glpi_itilcategories',
                (int) $ticketData['itilcategories_id']
            );
        }
        if (!empty($ticketData['status'])) {
            $lines[] = 'Status: ' . Ticket::getStatus($ticketData['status']);
        }
        if (!empty($ticketData['date'])) {
            $lines[] = 'Abertura: ' . $ticketData['date'];
        }
        if (!empty($ticketData['date_mod'])) {
            $lines[] = 'Última atualização: ' . $ticketData['date_mod'];
        }

        // Followups / timeline entries.
        if (!empty($followups)) {
            $lines[] = '';
            $lines[] = '=== ACOMPANHAMENTOS ===';
            foreach ($followups as $index => $fu) {
                $num = $index + 1;
                $lines[] = "--- Acompanhamento #{$num} ---";
                if (!empty($fu['date'])) {
                    $lines[] = 'Data: ' . $fu['date'];
                }
                if (!empty($fu['users_id'])) {
                    $lines[] = 'Autor: ' . getUserName((int) $fu['users_id']);
                }
                if (!empty($fu['content'])) {
                    $lines[] = 'Conteúdo: ' . strip_tags($fu['content']);
                }
            }
        }

        return implode("\n", $lines);
    }

    /**
     * Build the combined system prompt from config values.
     *
     * @return string
     */
    private static function buildSystemPrompt(): string
    {
        $systemPrompt = PluginNessaiConfig::getConfig(
            'system_prompt',
            'Você é um assistente técnico de TI especializado em suporte helpdesk.'
        );

        $orgContext = PluginNessaiConfig::getConfig('org_context', '');
        if (!empty($orgContext)) {
            $systemPrompt .= "\n\n=== CONTEXTO ORGANIZACIONAL ===\n" . $orgContext;
        }

        return $systemPrompt;
    }

    /**
     * If KB search is enabled, find relevant articles and format them
     * as additional context for the prompt.
     *
     * @param array $ticketData Ticket fields (uses 'name' + 'content' as search terms).
     *
     * @return string KB context block (empty string if disabled or no results).
     */
    private static function appendKbContext(array $ticketData): string
    {
        $enableKb = (bool) PluginNessaiConfig::getConfig('enable_kb_search', false);
        if (!$enableKb) {
            return '';
        }

        // A missing entity cannot be used as authorization for KB enrichment.
        $entityId = (int) ($ticketData['entities_id'] ?? 0);
        if ($entityId <= 0) {
            return '';
        }

        $searchTerms = trim(
            ($ticketData['name'] ?? '') . ' ' . strip_tags($ticketData['content'] ?? '')
        );

        if (empty($searchTerms)) {
            return '';
        }

        $articles = self::searchKnowledgeBase($searchTerms, $entityId);
        if (empty($articles)) {
            return '';
        }

        $block = "=== ARTIGOS DA BASE DE CONHECIMENTO ===\n";
        foreach ($articles as $i => $article) {
            $num = $i + 1;
            $block .= "--- Artigo #{$num}: {$article['name']} ---\n";
            $block .= "{$article['answer']}\n\n";
        }
        $block .= "=== FIM DOS ARTIGOS ===\n\n";

        return $block;
    }

    // ──────────────────────────────────────────────────────────────
    //  Knowledge Base search
    // ──────────────────────────────────────────────────────────────

    /**
     * Full-text search on glpi_knowbaseitems using MySQL
     * NATURAL LANGUAGE MODE.
     *
     * @param string $searchTerms Free-text query.
     * @param int $entityId Exact entity of the authorized ticket.
     *
     * @return array<int, array{name: string, answer: string}> Top results.
     */
    private static function searchKnowledgeBase(string $searchTerms, int $entityId): array
    {
        /** @var \DBmysql $DB */
        global $DB;

        $results = [];
        if ($entityId <= 0) {
            return $results;
        }

        // Truncate search terms to avoid overly long queries.
        $searchTerms = mb_substr($searchTerms, 0, 200);

        $query = "SELECT DISTINCT kbi.`id`,
                         MATCH(kbi.`name`, kbi.`answer`) AGAINST(? IN NATURAL LANGUAGE MODE) AS `relevance`
                  FROM `glpi_knowbaseitems` AS kbi
                  INNER JOIN `glpi_entities_knowbaseitems` AS eki
                    ON eki.`knowbaseitems_id` = kbi.`id` AND eki.`entities_id` = ?
                  WHERE MATCH(kbi.`name`, kbi.`answer`) AGAINST(? IN NATURAL LANGUAGE MODE)
                  ORDER BY `relevance` DESC
                  LIMIT 30";

        try {
            $stmt = $DB->prepare($query);
            $stmt->bind_param('sis', $searchTerms, $entityId, $searchTerms);
            $stmt->execute();
            $res = $stmt->get_result();

            while ($row = $res->fetch_assoc()) {
                $article = new KnowbaseItem();
                if (!$article->getFromDB((int) ($row['id'] ?? 0)) || !$article->canViewItem()) {
                    continue;
                }
                $results[] = [
                    'name'   => $article->fields['name'] ?? '',
                    'answer' => mb_substr(
                        strip_tags($article->fields['answer'] ?? ''),
                        0,
                        self::KB_ARTICLE_MAX_CHARS
                    ),
                ];
                if (count($results) >= self::KB_MAX_RESULTS) {
                    break;
                }
            }

            $stmt->close();
        } catch (\Throwable $e) {
            Toolbox::logError('[nessai] Knowledge Base search failed.');
        }

        return $results;
    }

    // ──────────────────────────────────────────────────────────────
    //  LLM dispatcher
    // ──────────────────────────────────────────────────────────────

    /**
     * Send a prompt to the configured LLM provider and return the response.
     *
     * Supports OpenAI, Google Gemini, Anthropic Claude, and Ollama.
     * Uses `file_get_contents()` with `stream_context_create()` to avoid
     * a hard dependency on cURL.
     *
     * @param string $systemPrompt System-level instructions.
     * @param string $userPrompt   User-level prompt (ticket context + task).
     *
     * @return array{text: string, prompt_tokens: int, completion_tokens: int}
     */
    private static function callLLM(string $systemPrompt, string $userPrompt): array
    {
        $errorResult = static fn(string $msg): array => [
            'text'              => 'Erro: ' . $msg,
            'prompt_tokens'     => 0,
            'completion_tokens' => 0,
        ];

        // ── Read configuration ───────────────────────────────────
        $provider  = PluginNessaiConfig::getConfig('llm_provider', 'openai');
        $model     = PluginNessaiConfig::getConfig('model_name', 'gpt-4o-mini');
        $endpoint  = PluginNessaiConfig::getConfig('api_endpoint', 'http://localhost:11434');
        $maxTokens = (int) PluginNessaiConfig::getConfig('max_tokens', 1024);
        $temperature = (float) PluginNessaiConfig::getConfig('temperature', 0.7);

        // Decrypt API key.
        $encryptedKey = PluginNessaiConfig::getConfig('api_key_encrypted', '');
        $apiKey = '';
        if (!empty($encryptedKey)) {
            try {
                $apiKey = (new GLPIKey())->decrypt($encryptedKey);
            } catch (\Throwable $e) {
                return $errorResult('Falha ao descriptografar a chave de API.');
            }
        }

        if (empty($apiKey) && $provider !== 'ollama') {
            return $errorResult('Chave de API não configurada. Acesse Configuração > Geral > ness. AI.');
        }

        // ── Build request per provider ───────────────────────────
        try {
            [$url, $headers, $body] = match ($provider) {
                'openai' => self::buildOpenAIRequest($apiKey, $model, $systemPrompt, $userPrompt, $maxTokens, $temperature),
                'gemini' => self::buildGeminiRequest($apiKey, $model, $systemPrompt, $userPrompt, $maxTokens, $temperature),
                'claude' => self::buildClaudeRequest($apiKey, $model, $systemPrompt, $userPrompt, $maxTokens, $temperature),
                'ollama' => self::buildOllamaRequest($endpoint, $model, $systemPrompt, $userPrompt, $maxTokens, $temperature),
                default  => throw new \RuntimeException("Provedor LLM desconhecido: {$provider}"),
            };
        } catch (\Throwable $e) {
            Toolbox::logError('[nessai] Provider request setup failed: ' . get_class($e));
            return $errorResult('Falha ao preparar requisição ao provedor LLM.');
        }

        // ── Execute HTTP request ─────────────────────────────────
        $headerLines = [];
        foreach ($headers as $key => $value) {
            $headerLines[] = "{$key}: {$value}";
        }

        $context = stream_context_create([
            'http' => [
                'method'        => 'POST',
                'header'        => implode("\r\n", $headerLines),
                'content'       => json_encode($body, JSON_UNESCAPED_UNICODE),
                'timeout'       => 120,
                'ignore_errors' => true,
            ],
            'ssl' => [
                'verify_peer'      => true,
                'verify_peer_name' => true,
            ],
        ]);

        $responseRaw = @file_get_contents($url, false, $context);

        if ($responseRaw === false) {
            $lastError = error_get_last();
            $msg = $lastError['message'] ?? 'Falha na conexão com o provedor LLM.';
            Toolbox::logError("[nessai] HTTP request failed [{$provider}]: {$msg}");
            return $errorResult("Falha na requisição HTTP: {$msg}");
        }

        // Check HTTP status from response headers.
        $httpStatus = 0;
        if (isset($http_response_header) && is_array($http_response_header)) {
            foreach ($http_response_header as $header) {
                if (preg_match('/^HTTP\/[\d.]+ (\d+)/', $header, $m)) {
                    $httpStatus = (int) $m[1];
                }
            }
        }

        $response = json_decode($responseRaw, true);

        if (json_last_error() !== JSON_ERROR_NONE) {
            Toolbox::logError("[nessai] Invalid JSON from {$provider}");
            return $errorResult('Resposta inválida do provedor LLM (JSON inválido).');
        }

        if ($httpStatus >= 400) {
            Toolbox::logError("[nessai] API error [{$provider}] HTTP {$httpStatus}");
            return $errorResult("Erro da API ({$provider}): HTTP {$httpStatus}");
        }

        // ── Parse response per provider ──────────────────────────
        return match ($provider) {
            'openai' => self::parseOpenAIResponse($response),
            'gemini' => self::parseGeminiResponse($response),
            'claude' => self::parseClaudeResponse($response),
            'ollama' => self::parseOllamaResponse($response),
            default  => $errorResult("Parser não implementado para: {$provider}"),
        };
    }

    // ──────────────────────────────────────────────────────────────
    //  Provider-specific request builders
    // ──────────────────────────────────────────────────────────────

    /**
     * Build OpenAI Chat Completions API request.
     *
     * @return array{0: string, 1: array<string,string>, 2: array}
     */
    private static function buildOpenAIRequest(
        string $apiKey,
        string $model,
        string $systemPrompt,
        string $userPrompt,
        int $maxTokens,
        float $temperature,
    ): array {
        $url = 'https://api.openai.com/v1/chat/completions';

        $headers = [
            'Content-Type'  => 'application/json',
            'Authorization' => 'Bearer ' . $apiKey,
        ];

        $body = [
            'model'       => $model,
            'messages'    => [
                ['role' => 'system', 'content' => $systemPrompt],
                ['role' => 'user',   'content' => $userPrompt],
            ],
            'max_tokens'  => $maxTokens,
            'temperature' => $temperature,
        ];

        return [$url, $headers, $body];
    }

    /**
     * Build Google Gemini generateContent API request.
     *
     * @return array{0: string, 1: array<string,string>, 2: array}
     */
    private static function buildGeminiRequest(
        string $apiKey,
        string $model,
        string $systemPrompt,
        string $userPrompt,
        int $maxTokens,
        float $temperature,
    ): array {
        $url = 'https://generativelanguage.googleapis.com/v1beta/models/'
            . urlencode($model)
            . ':generateContent?key=' . urlencode($apiKey);

        $headers = [
            'Content-Type' => 'application/json',
        ];

        $body = [
            'contents' => [
                [
                    'parts' => [
                        ['text' => $userPrompt],
                    ],
                ],
            ],
            'systemInstruction' => [
                'parts' => [
                    ['text' => $systemPrompt],
                ],
            ],
            'generationConfig' => [
                'maxOutputTokens' => $maxTokens,
                'temperature'     => $temperature,
            ],
        ];

        return [$url, $headers, $body];
    }

    /**
     * Build Anthropic Claude Messages API request.
     *
     * @return array{0: string, 1: array<string,string>, 2: array}
     */
    private static function buildClaudeRequest(
        string $apiKey,
        string $model,
        string $systemPrompt,
        string $userPrompt,
        int $maxTokens,
        float $temperature,
    ): array {
        $url = 'https://api.anthropic.com/v1/messages';

        $headers = [
            'Content-Type'      => 'application/json',
            'x-api-key'         => $apiKey,
            'anthropic-version' => '2023-06-01',
        ];

        $body = [
            'model'      => $model,
            'max_tokens' => $maxTokens,
            'temperature' => $temperature,
            'system'     => $systemPrompt,
            'messages'   => [
                ['role' => 'user', 'content' => $userPrompt],
            ],
        ];

        return [$url, $headers, $body];
    }

    /**
     * Build Ollama local API request.
     *
     * @return array{0: string, 1: array<string,string>, 2: array}
     */
    private static function buildOllamaRequest(
        string $endpoint,
        string $model,
        string $systemPrompt,
        string $userPrompt,
        int $maxTokens,
        float $temperature,
    ): array {
        $url = rtrim($endpoint, '/') . '/api/generate';

        $headers = [
            'Content-Type' => 'application/json',
        ];

        $body = [
            'model'   => $model,
            'prompt'  => $userPrompt,
            'system'  => $systemPrompt,
            'stream'  => false,
            'options' => [
                'num_predict'  => $maxTokens,
                'temperature'  => $temperature,
            ],
        ];

        return [$url, $headers, $body];
    }

    // ──────────────────────────────────────────────────────────────
    //  Provider-specific response parsers
    // ──────────────────────────────────────────────────────────────

    /**
     * Parse OpenAI Chat Completions response.
     *
     * @return array{text: string, prompt_tokens: int, completion_tokens: int}
     */
    private static function parseOpenAIResponse(array $response): array
    {
        $text = $response['choices'][0]['message']['content'] ?? '';

        return [
            'text'              => trim($text),
            'prompt_tokens'     => (int) ($response['usage']['prompt_tokens'] ?? 0),
            'completion_tokens' => (int) ($response['usage']['completion_tokens'] ?? 0),
        ];
    }

    /**
     * Parse Google Gemini generateContent response.
     *
     * @return array{text: string, prompt_tokens: int, completion_tokens: int}
     */
    private static function parseGeminiResponse(array $response): array
    {
        $text = $response['candidates'][0]['content']['parts'][0]['text'] ?? '';

        $promptTokens     = (int) ($response['usageMetadata']['promptTokenCount'] ?? 0);
        $completionTokens = (int) ($response['usageMetadata']['candidatesTokenCount'] ?? 0);

        return [
            'text'              => trim($text),
            'prompt_tokens'     => $promptTokens,
            'completion_tokens' => $completionTokens,
        ];
    }

    /**
     * Parse Anthropic Claude Messages response.
     *
     * @return array{text: string, prompt_tokens: int, completion_tokens: int}
     */
    private static function parseClaudeResponse(array $response): array
    {
        $text = '';
        foreach (($response['content'] ?? []) as $block) {
            if (($block['type'] ?? '') === 'text') {
                $text .= $block['text'];
            }
        }

        return [
            'text'              => trim($text),
            'prompt_tokens'     => (int) ($response['usage']['input_tokens'] ?? 0),
            'completion_tokens' => (int) ($response['usage']['output_tokens'] ?? 0),
        ];
    }

    /**
     * Parse Ollama generate response.
     *
     * @return array{text: string, prompt_tokens: int, completion_tokens: int}
     */
    private static function parseOllamaResponse(array $response): array
    {
        $text = $response['response'] ?? '';

        return [
            'text'              => trim($text),
            'prompt_tokens'     => (int) ($response['prompt_eval_count'] ?? 0),
            'completion_tokens' => (int) ($response['eval_count'] ?? 0),
        ];
    }

    // ──────────────────────────────────────────────────────────────
    //  Utility helpers
    // ──────────────────────────────────────────────────────────────

    /**
     * Map GLPI urgency/priority integer to a human-readable label.
     *
     * @param int $level GLPI urgency/priority value (1–5).
     *
     * @return string Localized label.
     */
    private static function urgencyLabel(int $level): string
    {
        return match ($level) {
            1       => __('Muito baixa'),
            2       => __('Baixa'),
            3       => __('Média'),
            4       => __('Alta'),
            5       => __('Muito alta'),
            default => (string) $level,
        };
    }
}
