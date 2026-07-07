# Guia de Webhooks e Workflows n8n

O fluxo de NOC AIOps foi projetado de forma que o n8n sirva como o **Orquestrador de Integrações Visuais** na "borda" (atualizar DeskManager, disparar mensagens na Evolution API/WhatsApp).

Você precisará criar **dois workflows principais no n8n** ouvindo via Webhook. Abaixo estão os formatos exatos de JSON que a aplicação (Keep e FastAPI) vai enviar.

## 1. Workflow: Criação de Ticket e Alerta Inicial
- **Webhook Method:** `POST`
- **Webhook URL Esperada:** `http://<n8n-ip>:5678/webhook/incident-created` (ou equivalente no seu domínio n8n). *A URL real deve estar configurada no Keep (`NINF_N8N_BASE_URL`).*
- **Quem dispara:** Keep AIOps (`escalate-incident.yml`)

### Funcionalidade:
O n8n deve pegar este payload, chamar a API do DeskManager para criar um ticket de incidente e enviar uma notificação no grupo de NOC do WhatsApp contendo as tags e dados do host.

### Payload de Exemplo (Enviado pelo Keep):
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
O webhook no n8n precisa estar configurado para retornar uma reposta JSON contendo o `ticket_id` que ele acabou de criar. O Keep usará isso no próximo passo (Gemini RCA).
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
