# Guia de Webhooks e Workflows n8n

O fluxo de NOC AIOps foi projetado de forma que o n8n sirva como o **Orquestrador de Integrações Visuais** na "borda" (atualizar DeskManager, disparar mensagens na Evolution API/WhatsApp).

Você precisará criar **dois workflows principais no n8n** ouvindo via Webhook. Abaixo estão os formatos exatos de JSON enviados pelo backend FastAPI e seus workers.

## 1. Workflow: Criação de Ticket e Alerta Inicial
- **Webhook Method:** `POST`
- **Webhook URL Esperada:** `http://<n8n-ip>:5678/webhook/incident-created` (ou equivalente no seu domínio n8n). A base deve estar configurada em `NINF_N8N_BASE_URL`.
- **Quem dispara:** worker de alertas FastAPI (`process_alert`)

### Funcionalidade:
O n8n deve pegar este payload, chamar a API do DeskManager para criar um ticket de incidente e enviar uma notificação no grupo de NOC do WhatsApp contendo as tags e dados do host.

### Payload de Exemplo (Enviado pelo worker de alertas):
```json
{
  "fingerprint": "8d3e2ab1-e5d3-4f91",
  "title": "CPU load is too high",
  "severity": 4,
  "severity_label": "HIGH",
  "status": "PROBLEM",
  "host_name": "srv-db-01",
  "trigger_id": "99381",
  "trigger_name": "CPU load is too high",
  "sanitized_description": "CPU load is > 95% for 5 minutes.",
  "alert_count": 3,
  "first_seen": "2026-07-06T12:00:00Z",
  "last_seen": "2026-07-06T12:15:00Z"
}
```

### O que o n8n DEVE retornar:
O webhook no n8n precisa retornar uma resposta JSON contendo o `ticket_id` criado. O worker usará esse identificador no passo seguinte de RCA com Gemini.
```json
{
  "ticket_id": "123456"
}
```

---

## 2. Workflow: PostMortem e Fechamento/Update
- **Webhook Method:** `POST`
- **Webhook URL Esperada:** `http://<n8n-ip>:5678/webhook/postmortem-ready`
- **Quem dispara:** FastAPI (`/api/incident/analyze`) após a análise do Gemini ser concluída.

### Funcionalidade:
O n8n deve pegar este payload, usar o `ticket_id` para adicionar uma "Interação Interna" no DeskManager com a Causa Raiz e Análise, e por fim mandar outra mensagem no WhatsApp com o "Resumo Executivo" do PostMortem.

### Payload de Exemplo (Enviado pelo FastAPI):
```json
{
  "ticket_id": "123456",
  "incident_fingerprint": "8d3e2ab1-e5d3-4f91",
  "summary": "Ocorreu um pico de CPU devido a uma query mal otimizada no banco de dados.",
  "root_cause": "A query 'SELECT * FROM logs' travou a tabela e saturou I/O, elevando o load da CPU.",
  "markdown_report": "# Post Mortem\n\n## Resumo Executivo\n...",
  "blast_radius": [
    "Serviço de Autenticação",
    "Banco de Dados Principal"
  ],
  "corrective_actions": [
    "Adicionar índice na tabela de logs.",
    "Limitar a retenção dos logs na base relacional."
  ]
}
```

## Segurança e pré-requisitos para ativação

- Configure `NINF_N8N_WEBHOOK_API_KEY` com pelo menos 32 caracteres no `.env` do
  Hub. O cliente backend envia esse segredo no header `X-Ness-Webhook-Key` e o
  primeiro nó Code de cada workflow rejeita chamadas sem correspondência. Os
  exports ainda não usam Header Auth nativo no nó Webhook; habilite essa proteção
  adicional antes de expor os endpoints fora da rede privada.
- `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` é requerido pelas expressões atuais dos
  workflows. Até mover os segredos para credenciais n8n e reativar o bloqueio,
  somente administradores de confiança devem editar/importar workflows.
- A credencial SMTP referenciada pelos exports é específica da instância n8n.
  Confirme a credencial `ness.OS Resend SMTP` no destino; não presuma que o ID do
  arquivo exista em outra instância.
- `NINF_EVOLUTION_API_KEY` precisa estar no `.env` do Compose para envio WhatsApp.
  O Compose a encaminha ao n8n; se estiver vazia, a Evolution deve rejeitar o
  envio e nenhum valor de placeholder deve ser usado.
- Conteúdo dinâmico de incidentes é escapado antes de entrar no HTML. Ainda assim,
  valide os dois fluxos em UAT com destinatários fictícios antes de liberar envio.
