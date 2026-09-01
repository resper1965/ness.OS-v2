# 🏛️ Mapeamento Arquitetural Real — Plataforma AIOps & SOC (`zabbix.ness`)

> **Documento histórico.** A referência vigente é [Arquitetura oficial do ness.OS](architecture/ness-os-official-architecture.md), regida pelas ADRs 0012 e 0013.

> **Projeto:** `zabbix.ness` (Monorepo Enterprise: NOC Zabbix 7.0 + AIOps Multi-Tenant `n.infraops` + SOC `n.secops`)
> **Versão:** 2.2 (Julho/2026) — Diagramas Otimizados para Visualização Limpa (Sem Cruzamentos de Linhas)

---

## 1. Visão Geral do Ecossistema (C4 Context Diagram)

O diagrama abaixo foi reestruturado no fluxo top-to-bottom exato para garantir visualização limpa no leitor de Markdown, **sem linhas cruzadas, curvas quebradas ou pontas soltas**.

```mermaid
flowchart TB
    %% CAMADA 1: ATIVOS DOS CLIENTES (ENTRADA)
    subgraph L1 ["1. Coleta em Endpoints (Ativos dos Clientes)"]
        WazuhAgent["💻 Agente Wazuh + Sysmon<br/>(Logs & Eventos de Segurança)"]
        ZabbixAgent["📊 Agente / Proxy Zabbix<br/>(Métricas & Disponibilidade)"]
        GLPIAgent["📋 Agente GLPI<br/>(Inventário Hardware/Software)"]
    end

    %% CAMADA 2: SPOKES E COLETORES
    subgraph L2 ["2. Servidores de Coleta & Spokes"]
        WazuhSpoke["🏢 Spokes Wazuh (Enterprise / SMB)<br/>(Managers Locais 4.14)"]
        ZabbixServer["📊 Servidor Zabbix 7.0 LTS<br/>(zabbix.ness.com.br - NOC)"]
    end

    %% CAMADA 3: HUB AIOPS CENTRAL
    subgraph L3 ["3. Hub Central AIOps & SOC Central"]
        WazuhHub["🛡️ Wazuh Hub 4.14 Indexer<br/>(OpenSearch Central)"]
        Caddy["🌐 Caddy Reverse Proxy<br/>(caddy:2-alpine)"]
        FastAPI["🧠 FastAPI Backend - ness.OS<br/>(Triage Camada 4 & Integrador)"]
        RedisDB[(⚡ Redis 7<br/>Cache, Broker & Locks)]
        PostgresDB[(🗄️ PostgreSQL 16<br/>TimescaleDB + pgvector)]
        CeleryWorkers["⚡ Celery Workers<br/>(Alertas & ML/Anomalias)"]
        AuthentikSSO["🔑 Authentik SSO IdP<br/>(sso.ness.com.br)"]
        n8nOrchestrator["⚡ n8n Workflows<br/>(n8n.ness.com.br)"]
        EvolutionGW["💬 Evolution API<br/>(waba.ness.com.br - WhatsApp)"]
    end

    %% CAMADA 4: SERVIÇOS EXTERNOS E DESTINOS
    subgraph L4 ["4. Serviços Externos, IA & Notificações"]
        MISP["☣️ Servidor MISP Threat Intel<br/>(misp.ness.com.br / REST API)"]
        Gemini["🤖 Google Gemini 2.5 Flash<br/>(RCA & Post-Mortem LLM)"]
        GLPIServer["🎫 Servidor GLPI ITSM<br/>(n-ticket.ness.com.br)"]
        Analista["👤 Analista NOC / SOC ness."]
        Cliente["👥 Gestor / Usuário do Cliente"]
    end

    %% FLUXOS: CAMADA 1 -> CAMADA 2
    WazuhAgent -->|TLS 1514| WazuhSpoke
    ZabbixAgent -->|Métricas 10051| ZabbixServer
    GLPIAgent -->|Inventário HTTP| GLPIServer

    %% FLUXOS: CAMADA 2 -> CAMADA 3
    WazuhSpoke -->|Filebeat HTTPS 9200| WazuhHub
    WazuhHub -->|Webhook JSON| Caddy
    ZabbixServer -->|Webhook Alertas| Caddy

    %% FLUXOS INTERNOS DO HUB (CAMADA 3)
    Caddy --> FastAPI
    FastAPI <--> RedisDB
    FastAPI <--> PostgresDB
    FastAPI --> CeleryWorkers
    FastAPI --> n8nOrchestrator

    %% FLUXOS: CAMADA 3 -> CAMADA 4
    FastAPI -->|Consulta IOCs| MISP
    FastAPI -->|Prompt Sanitizado| Gemini
    n8nOrchestrator -->|Disparo Alertas| EvolutionGW
    n8nOrchestrator -->|Abre Chamados| GLPIServer

    EvolutionGW -->|WhatsApp| Analista
    GLPIServer -->|Chamados / SLA| Cliente
    AuthentikSSO -.->|SSO SAML / OIDC| ZabbixServer
    AuthentikSSO -.->|SSO OIDC| GLPIServer
```

---

## 2. Detalhamento dos Contêineres em Produção (`app/docker-compose.yml`)

A VPS de AIOps roda a stack oficial de 14 contêineres Docker interconectados pela rede bridge `app_ninf-net`:

```mermaid
flowchart LR
    subgraph FrontendRoute [Borda & Proxy]
        CaddyProxy[ninf-caddy Proxy]
        WebApp[ninf-frontend React]
    end

    subgraph CoreApp [Backend & Workers]
        APIBackend[ninf-api FastAPI]
        WorkerAlerts[ninf-worker-alerts]
        WorkerML[ninf-worker-ml]
    end

    subgraph DataStores [Persistência & Fila]
        PG[ninf-postgres PG16]
        Redis[ninf-redis Cache/Broker]
    end

    subgraph AutomationAndAuth [SSO & Orquestração]
        AuthServer[ninf-authentik-server]
        AuthWorker[ninf-authentik-worker]
        N8N[ninf-n8n Engine]
        EvoAPI[ninf-evolution WhatsApp]
        EvoMgr[ninf-evolution-manager]
        GLPI[ninf-glpi Service Desk]
        GLPIDB[(ninf-glpi-db MariaDB)]
    end

    CaddyProxy --> WebApp
    CaddyProxy --> APIBackend
    APIBackend <--> PG
    APIBackend <--> Redis
    APIBackend --> WorkerAlerts
    APIBackend --> WorkerML
    APIBackend --> N8N
    N8N --> EvoAPI
    EvoAPI --> EvoMgr
    GLPI <--> GLPIDB
    CaddyProxy --> GLPI
    AuthServer <--> PG
    AuthWorker <--> Redis
```

### Inventário Factual de Contêineres

| Contêiner | Imagem / Base | Função & Responsabilidade | Limite de Memória |
|---|---|---|---|
| `ninf-api` | Python 3.12 (FastAPI) | Backend central da plataforma (`ness.OS`). Executa o Triage Worker (Camada 4), sanitização regex de PII e endpoints de API. | 512 MB |
| `ninf-worker-alerts` | Python 3.12 (Celery) | Worker dedicado para alertas de alta prioridade (filas `alerts.primary` e `alerts.deferred`). | 512 MB |
| `ninf-worker-ml` | Python 3.12 (Celery) | Worker pesado para análise de anomalias Z-Score Robusto (MAD), vetores pgvector e relatórios de Post-Mortem. | 1.0 GB |
| `ninf-postgres` | `timescale/timescaledb:latest-pg16` | Banco relacional + séries temporais + busca vetorial (`pgvector`). Contém as bases `nessops`, `authentik` e `evolution`. | 3.0 GB |
| `ninf-redis` | `redis:7-alpine` | Cache em memória (maxmemory 256MB LRU), broker de mensagens do Celery e locks distribuídos (`SET NX EX`). | 300 MB |
| `ninf-evolution` | `evoapicloud/evolution-api:latest` | Gateway de mensageria WhatsApp via Evolution API (`waba.ness.com.br`). | 1.5 GB |
| `ninf-evolution-manager` | `evoapicloud/evolution-manager` | Interface Web de gerenciamento de instâncias do WhatsApp (porta 8082). | Standard |
| `ninf-frontend` | Node / Vite (React App) | Single Page Application do Dashboard unificado (`hub.ness.com.br`). | 512 MB |
| `ninf-caddy` | `caddy:2-alpine` | Reverse proxy central com gerenciamento automático de certificados SSL Let's Encrypt para todas as rotas `.ness.com.br`. | Standard |
| `ninf-n8n` | `docker.n8n.io/n8nio/n8n:latest` | Orquestrador de workflows de automação (`n8n.ness.com.br`), integração com GLPI e disparos WhatsApp. | 1.0 GB |
| `ninf-authentik-server` | `ghcr.io/goauthentik/server:2026.5.6` | Servidor central de identidade e SSO (`sso.ness.com.br`) fornecendo OIDC e SAML 2.0. | 1.0 GB |
| `ninf-authentik-worker` | `ghcr.io/goauthentik/server:2026.5.6` | Background worker para tarefas assíncronas do Authentik (sincronização de usuários e políticas de acesso). | 1.0 GB |
| `ninf-glpi` | `elestio/glpi:latest` | GLPI/Service Desk publicado por `n-ticket.ness.com.br`. | 512 MB |
| `ninf-glpi-db` | `mariadb:10.11` | Banco exclusivo do GLPI. | 512 MB |

---

## 3. Mapeamento de Domínios e Roteamento Caddy (`Caddyfile`)

Todas as requisições externas chegam ao contêiner `ninf-caddy` (portas 80/443) e são roteadas conforme o arquivo de produção [Caddyfile](../Caddyfile):

```mermaid
flowchart LR
    Internet((Navegador / Webhook)) --> Caddy[Caddy Reverse Proxy - ninf-caddy]

    Caddy -->|hub.ness.com.br| Frontend[ninf-frontend:3000 / React Dashboard]
    Caddy -->|api.ness.com.br| API[ninf-api:8000 / FastAPI Backend]
    Caddy -->|waba.ness.com.br| Evo[ninf-evolution:8080 / Evolution API]
    Caddy -->|sso.ness.com.br| Auth[ninf-authentik-server:9000 / Authentik SSO]
    Caddy -->|n-ticket.ness.com.br| GLPI[ninf-glpi:80 / GLPI Service Desk]
    Caddy -->|n8n.ness.com.br| N8N[ninf-n8n:5678 / n8n Workflow]
```

---

## 4. Onde Opera a Inteligência AIOps do Wazuh?

Conforme definido na especificação **Hub-to-Spoke** do repositório ([wazuh-secops-plan.md](../wazuh-secops-plan.md)):

```mermaid
sequenceDiagram
    autonumber
    participant Agent as Agente Wazuh + Sysmon (Cliente)
    participant Spoke as Spoke Manager (VPS Local/Cliente)
    participant HubIdx as Wazuh Hub Indexer (OpenSearch)
    participant API as FastAPI AIOps Hub (ninf-api)
    participant MISP as Servidor MISP (misp.ness.com.br)
    participant Gemini as Google Gemini 2.5 Flash
    participant N8N as n8n / Evolution API
    participant SOC as Analista SOC (Humano)

    Agent->>Spoke: Envia logs brutos via TLS (Porta 1514)
    Spoke->>Spoke: Análise local (Decoders + Regras Sigma/Wazuh)
    Spoke->>HubIdx: Envia alertas level >= 7 via Filebeat (Porta 9200)
    HubIdx->>API: Dispara Webhook JSON (/api/secops/triage)

    rect rgb(240, 248, 255)
        note over API: OPERAÇÃO AIOPS (No Hub AIOps)
        API->>API: 1. Sanitiza dados sensíveis (Sanitizer 7 Regex)
        API->>MISP: 2. Consulta IOCs (/attributes/restSearch)
        MISP-->>API: Retorna histórico de eventos e tags MITRE
        API->>API: 3. Triage Worker (Camada 4) calcula Risk Score (0-100)
    end

    alt Risk Score < 75 (Baixo Risco / Falso Positivo)
        API->>API: Ação ARCHIVE_NO_LLM (Bypass de IA >= 95%)
        API-->>HubIdx: 200 OK (Processado sem consumo de Gemini)
    else Risk Score >= 75 (Ameaça Confirmada)
        API->>Gemini: Solicita Análise RCA + Timeline + Playbook
        Gemini-->>API: Retorna relatório detalhado em PT-BR
        API->>N8N: Notifica incidente (GLPI + WhatsApp)
        N8N->>SOC: Envia alerta interativo no WhatsApp
        SOC->>API: Aprova execução de Resposta Ativa
        API->>Spoke: Envia comando Active Response (Isolar Host / Bloquear IP)
        Spoke->>Agent: Executa ação de contenção no endpoint
    end
```

---

## 5. Matriz de Infraestrutura e Custos Reais

| Componente | Servidor / Provedor | Capacidade | Custo Estimado |
|---|---|---|---|
| **Zabbix NOC** | Contabo Storage VPS 40 | 8 vCPU, 30 GB RAM, 1.2 TB SSD | €20,00/mês |
| **AIOps Hub Stack (14 Docker Containers)** | Contabo VPS (estado observado: 8 vCPU, 24 GB RAM, 400 GB SSD) | API, workers, dados, SSO, automação, mensageria e GLPI | Validar no painel Contabo |
| **Object Storage (Backups S3)** | Contabo S3 Storage | 250 GB Object Storage | €2,49/mês |
| **IA Gemini 2.5 Flash** | Google Cloud API | Pay-per-token (Com bypass ≥ 95% na Camada 4) | ~€10,00/mês |
| **Servidor MISP** | VPS Dedicada (Externa) | 2 vCPU, 4 GB RAM | (Infra do Cliente/SOC) |
| **Total Estimado da Plataforma** | | | **€38,49 / mês** |
