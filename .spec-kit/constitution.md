# Project Constitution — n.infraops

Este documento serve como a Constituição do projeto **n.infraops**, ditando as regras fundamentais, decisões arquiteturais, e restrições que devem ser seguidas por todos os desenvolvedores e agentes de IA.

---

## 1. Missão e Escopo
O **n.infraops** é uma plataforma de AIOps open-source corporativa projetada para centralizar, deduplicar, correlacionar e remediar de forma inteligente os alertas gerados pelo Zabbix 7.0 LTS.

*   **Foco Principal:** Reduzir fadiga de alertas (alert fatigue) e acelerar o tempo médio de reparo (MTTR).
*   **Ambiente Alvo:** 374 hosts, ~59K itens, e ~25K triggers no Zabbix.

---

## 2. Stack Tecnológica
Nenhuma alteração na stack principal pode ser feita sem aprovação do comitê técnico:

*   **Backend API & Workers:** Python 3.12+ (FastAPI + Celery + Redis 7).
*   **Banco de Dados:** PostgreSQL 16 estendido com:
    *   **TimescaleDB:** Para séries temporais e armazenamento de métricas.
    *   **pgvector:** Para armazenamento e busca semântica de embeddings de incidentes e runbooks (dimensão 768).
*   **Orquestração de Borda:** n8n (Self-hosted) para gerenciar fluxo de abertura de chamados e notificações.
*   **Sistemas Externos:**
    *   DeskManager (API Rest para Ticketing).
    *   Evolution API (Gateway de WhatsApp para alertas).
    *   Gemini API (Modelo `gemini-2.5-flash` para análise RAG e pós-incidente).
*   **Automação / Remediação:** Drivers RMM (Datto, Atera) e SSH via Netmiko para ativos de rede sem agente.

---

## 3. Diretrizes de Segurança (CISO-Mindset)
*   **Sanitização de Dados:** Antes de salvar qualquer log/alerta no banco de dados, enviá-lo ao Gemini API, ou exibi-lo no Slack/WhatsApp, os dados **devem** ser limpos contra vazamentos de PII ou credenciais:
    *   Substituir IPv4 por `[IP_REDACTED]`.
    *   Remover senhas, API keys, Connection strings e Bearer tokens.
*   **Controle de Credenciais:** As credenciais locais de produção devem residir estritamente em um arquivo `.env` protegido com permissões restritas de leitura (`chmod 600` ou equivalente).
*   **Repositório Seguro:** O repositório no GitHub deve ser **privado** por segurança, evitando exposição acidental de infraestrutura.

---

## 4. Políticas de Operação & Decisões de Design (Grill-Me)
Estas decisões foram acordadas com o operador e devem ser seguidas estritamente:

*   **Estratégia de Deploy:** Docker Compose direto na VPS Linux (8 GB de RAM), garantindo isolamento total e simplicidade operacional.
*   **Filtro de Incidentes:** Apenas alertas de severidade **HIGH** e **DISASTER** (severidades 4 e 5 no Zabbix) acionam a geração de relatórios post-mortem e abertura automática de chamados de alta prioridade.
*   **Fluxo de Aprovação de Playbooks:**
    *   **Human-in-the-loop (Slack):** Playbooks destrutivos exigem aprovação manual via Slack (botões interativos).
    *   **Timeout & Escalação:** Se um playbook aguardar aprovação por mais de **15 minutos**, a execução é cancelada na fila atual e o incidente é escalado automaticamente para o gestor via WhatsApp.
*   **Retenção de Dados:**
    *   Dados de incidentes no PostgreSQL: **90 dias**.
    *   Relatórios de post-mortem (Incident Reports): **365 dias** para garantir uma base histórica rica para o RAG.
