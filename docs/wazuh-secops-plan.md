# Wazuh MSSP + Shuffle SOAR + Analistas Agênticos IA — n.secops (ness.OS)

## Goal
Implantar arquitetura Wazuh 4.14.6 Hub-to-Spoke + Shuffle SOAR + Analistas SOC/NOC 
agênticos baseados em IA (Gemini), integrados ao módulo n.secops do ness.OS.
Resultado: SOC que pré-triagem, enriquece e responde alertas automaticamente 24/7.

---

## Arquitetura Completa

```
CAMADA 3 — HUB SOC Central (VPS dedicado: 8 vCPU / 32 GB / 800 GB NVMe)
  Wazuh Indexer 4.14.6 (OpenSearch) — índices wazuh-alerts-<cliente>-*
  Wazuh Dashboard — painel único multi-cliente (MFA, porta 443)
  Shuffle SOAR — orquestração de playbooks e integração de ferramentas
  → Repositório externo (VPS backup): snapshots diários via S3-like API

CAMADA SOAR / IA (roda no Hub ou VPS 1 ness.OS)
  Shuffle CE (Docker) — recebe webhooks do Wazuh, executa playbooks
  ness.OS AI Agent (FastAPI + Gemini) — analista agêntico SOC/NOC
  Evolution API (WhatsApp) — notificações e paging on-call

CAMADA 2 — SPOKE por modelo de contrato
  Enterprise: 1 Spoke VPS dedicado por cliente
  SMB: Spoke compartilhado (até 3 clientes por Spoke com agent groups isolados)
  Wazuh Manager 4.14.6 + Filebeat — análise local, envia só alertas ao Hub

CAMADA 1 — ENDPOINTS (máquinas dos clientes)
  Agente Wazuh 4.14.6 — FIM, SCA, inventário, canal Sysmon
  Sysmon (Windows) — processos, rede, DNS, registro, hashes SHA256
```

---

## Fluxo de Dados e Decisão (Agêntico)

```
[Endpoint] --1514/TLS--> [Spoke Manager] --analisa--> [alerta gerado]
                                 |
                         [Filebeat] --9200/HTTPS VLAN--> [Hub Indexer]
                                                               |
                         [Wazuh Integrator] --webhook--> [Shuffle SOAR]
                                                               |
                                    ┌──────── Enriquecimento ──────────┐
                                    │  VirusTotal (IP/hash/domain)     │
                                    │  AbuseIPDB (reputação IP)        │
                                    │  MITRE ATT&CK (tática/técnica)   │
                                    │  Wazuh API (contexto do agente)  │
                                    └─────────────────────────────────┘
                                                               |
                                              [ness.OS AI Agent endpoint]
                                              Gemini analisa: alerta + contexto
                                              Classifica: FP / LOW / MED / HIGH / CRIT
                                              Gera: triage summary em PT-BR
                                              Decide: ação a tomar
                                                               |
                              ┌────────────────────────────────┼──────────────────────┐
                              ▼                                ▼                      ▼
                    [Auto-close FP]                 [Criar ticket ITSM]    [Paging WhatsApp]
                    [Wazuh silence rule]            [Atera/Freshdesk]      [on-call analista]
                              ▼
                    [Active Response]
                    [bloquear IP, isolar host]
```

---

## Tasks

### Fase A — Hub + Wazuh 4.14.6

- [ ] A1: Provisionar VPS Hub no Contabo via API (Contabo Cloud VPS XL)
  Spec: 8 vCPU / 32 GB / 800 GB NVMe — wazuh.ness.com.br / IP privado VLAN
  Verificar: SSH root, free -h = 32GB, nvme lista os 800GB

- [ ] A2: Configurar rede privada VLAN Contabo entre Hub e Spokes
  Ativar private networking no painel Contabo para ambos os VPS
  Verificar: Hub pinga Spoke-piloto via IP privado 10.0.x.x

- [ ] A3: Instalar Wazuh 4.14.6 Hub (Docker single-node, gerar certs internos)
  wazuh-docker com wazuh-indexer + wazuh-manager + wazuh-dashboard
  Rodar generate-certs.yml antes do docker compose up
  Verificar: curl -k https://localhost:9200 retorna {"name":"wazuh-indexer"}

- [ ] A4: Configurar segurança e acesso Hub
  UFW: bloquear 9200 e 55000 para internet; liberar apenas IPs VLAN privados
  Caddy: wazuh.ness.com.br → 443 com Authelia MFA (TOTP + LDAP)
  Verificar: curl IP_EXTERNO:9200 = Connection refused; Dashboard abre com login MFA

- [ ] A5: Configurar index routing multi-tenant no Filebeat
  Template Filebeat output: index = "wazuh-alerts-%{[agent.group]}-%{+YYYY.MM.dd}"
  OpenSearch DLS (Document Level Security) por tenant group
  ILM: retenção 90 dias, rollover em 50 GB por índice
  Verificar: alertas de clientes distintos aparecem em índices separados

### Fase B — Spoke-Piloto + Onboarding

- [ ] B1: Provisionar VPS Spoke-piloto (Enterprise: 8 vCPU / 16 GB / 200 GB NVMe)
  Instalar Wazuh Manager 4.14.6 + Filebeat
  Filebeat configurado com índice "wazuh-alerts-cliente-a-*"
  Verificar: agentes aparecem no Hub Dashboard com agent.group = cliente-a

- [ ] B2: Onboarding primeiro cliente real (3-5 endpoints piloto)
  Windows: instalar Wazuh Agent + Sysmon com sysmonconfig-modular (Olaf Hartong)
  Linux: instalar Wazuh Agent (sem Sysmon)
  agent.conf centralizado: Sysmon/Operational + Security + PowerShell/Operational
  Verificar: agentes Active, eventos Sysmon Event ID 1/3/11 indexados no Hub

- [ ] B3: SCA por cliente — ness. Baseline
  Criar policy YAML custom: ness_security_baseline.yml (CIS Controls + LGPD)
  Distribuir via agent.conf do grupo do cliente
  Verificar: SCA tab do Dashboard mostra score por agente com checks aprovados/reprovados

### Fase C — Shuffle SOAR

- [ ] C1: Deploy Shuffle CE (Docker) no Hub VPS
  Docker compose do Shuffle Community Edition (github.com/Shuffle/Shuffle)
  Configurar backend_url, shuffle_gensec_url, opensearch connection
  Verificar: Shuffle UI abre em http://localhost:3001 (acesso apenas via túnel SSH)

- [ ] C2: Instalar Wazuh App no Shuffle + configurar webhook
  No Shuffle: adicionar Wazuh app, configurar URL do Manager API (porta 55000) + JWT
  No Wazuh Manager ossec.conf: configurar Integrator para enviar alertas level >= 7 ao Shuffle
  Verificar: alert de teste aparece no Shuffle workflow trigger

- [ ] C3: Criar playbook de enriquecimento no Shuffle
  Nó 1: recebe alerta Wazuh (JSON)
  Nó 2: VirusTotal — consulta hash/IP do alerta
  Nó 3: AbuseIPDB — consulta IP de origem
  Nó 4: MITRE ATT&CK — mapa rule.mitre.id para técnica/tática
  Nó 5: Wazuh API — busca dados completos do agente (syscollector)
  Nó 6: HTTP POST para ness.OS AI Agent endpoint com payload enriquecido
  Verificar: payload chegando no endpoint /api/secops/triage com todos os campos

### Fase D — Analista Agêntico IA

- [ ] D1: Criar endpoint de triage no ness.OS backend
  app/api/routers/secops_ai.py — POST /api/secops/triage
  Recebe payload Shuffle enriquecido (alerta + VT + AbuseIPDB + MITRE + agente)
  Verificar: endpoint responde 200 com JSON vazio (stub)

- [ ] D2: Implementar AI Agent com Gemini (app/integrations/soc_agent.py)
  PydanticAI ou Google GenAI SDK — modelo gemini-2.0-flash
  System prompt: "Você é um analista SOC sênior da ness. Analise o alerta..."
  Ferramentas (tools): wazuh_silence_rule, create_ticket_atera, send_whatsapp
  Output estruturado: classificação, confiança, triage_summary (PT-BR), ação
  Verificar: teste unitário com alert fictício retorna JSON com campos corretos

- [ ] D3: Integrar decisões de volta ao Shuffle
  Shuffle recebe response do AI Agent
  Branch por decisão:
    FP → Wazuh API: adicionar regra de silêncio temporária (24h)
    LOW → índice no Indexer, sem ação imediata
    MED → criar ticket no Atera via API
    HIGH → criar ticket + WhatsApp para analista on-call
    CRIT → criar ticket urgente + WhatsApp + Active Response (bloquear IP)
  Verificar: alerta HIGH gera ticket no Atera E mensagem WhatsApp no grupo SOC

- [ ] D4: Dashboard n.secops no ness.OS (CoreDashboard expansion)
  Widget: "Alertas triados por IA hoje" (contadores: FP / LOW / MED / HIGH / CRIT)
  Widget: "Últimas 10 decisões do Agente" (tabela com link para ticket)
  Widget: "Agentes por cliente" (status: Active / Disconnected)
  Widget: "SCA Score por cliente" (barra de progresso 0-100%)
  Verificar: dados aparecem após 1 ciclo de alertas reais

### Fase E — Backup e Hardening

- [ ] E1: Snapshot diário do Indexer para VPS backup (rsync + OpenSearch Snapshot API)
  Configurar repositório de snapshot no Indexer apontando para VPS backup via SSH
  Cronjob: snapshot às 02:00 UTC diariamente
  Backup de client.keys de cada Spoke também
  Verificar: GET /_snapshot/ness_backup/_all lista snapshots do último dia

- [ ] E2: Alertas de saúde do Hub no ness.OS
  Monitor: disk usage Indexer > 70% → alerta LOW / > 85% → alerta HIGH
  Monitor: events_dropped no analysisd > 0 → alerta Spoke saturando
  Monitor: Spoke Manager offline > 5 min → notificação WhatsApp
  Verificar: desligar Spoke-piloto por 6 minutos, receber WhatsApp de alerta

### Fase F — Google Workspace (Cavan)

- [ ] F1: Criar integração somente leitura para o tenant único da Cavan
  (Matriz e unidades fabris), com projeto Google Cloud e conta de serviço
  exclusivos.
- [ ] F2: Aprovar delegação de domínio de escopo mínimo para Reports API e
  Alert Center API; não conceder privilégios de alteração.
- [ ] F3: Executar GAM7 para inventário/postura inicial e armazenar apenas o
  relatório sanitizado e os achados, nunca chaves ou conteúdo de usuários.
- [ ] F4: Publicar o conector Google Workspace no pipeline AIOps/Wazuh,
  normalizando auditorias de login, administração, OAuth/token e Drive.
- [ ] F5: Criar a visão por serviços (Workspace geral, identidade,
  administração, colaboração) no portal executivo. Matriz/fábricas serão
  contexto dos eventos, não tenants distintos.

---

## Done When
- [ ] Hub SOC wazuh.ness.com.br rodando Wazuh 4.14.6 com MFA
- [ ] 1 Spoke Enterprise operacional, agentes Windows com Sysmon ativos
- [ ] Alertas level >= 7 chegando ao Shuffle e sendo triados pelo AI Agent
- [ ] Decisões do agente executadas: tickets Atera + WhatsApp on-call
- [ ] GET /api/core/overview no ness.OS reflete dados reais do Wazuh
- [ ] SCA score visível por cliente no n.secops dashboard
- [ ] Snapshots diários verificados no VPS backup

---

## Notes

### Versão: Wazuh 4.14.6 (estável, jul/2026)
  Manager, Indexer e Dashboard DEVEM ter versão idêntica (incluindo patch).
  Wazuh 5.0 beta em desenvolvimento (novo engine) — monitorar, não usar ainda.
  Breaking change 4.14.1: campo dstuser obrigatório — testar regras customizadas antes.

### Modelo de Spoke por contrato
  Enterprise (Spoke dedicado): 8 vCPU / 16 GB / 200 GB NVMe (~€22/mês Contabo)
  SMB (Spoke compartilhado, até 3 clientes): 4 vCPU / 8 GB / 100 GB NVMe (~€10/mês)
  Critério: tipo de contrato, não volume de endpoints

### Limites de escala (campo, não teórico)
  1 Manager: ~300-500 agentes confortáveis (monitorar events_dropped)
  Saturação: cat /var/ossec/var/run/wazuh-analysisd.state | grep events_dropped
  Escala horizontal: cluster manager (master + 2 workers) antes de 500 agentes

### Problemas MSSP conhecidos a prevenir
  Disk Full = read-only mode silencioso: alertar em 70% e 85% do disco Indexer
  Conflito de índices de estado em shared Indexer: prefixo por manager no Filebeat
  RBAC Manager API (55000) e Indexer (9200) são sistemas independentes: testar DLS

### Shuffle CE: onde roda?
  Co-localizar no Hub VPS (32 GB RAM, amplo) — Shuffle < 2 GB RAM
  Acesso somente via túnel SSH ou VPN — nunca expor porta Shuffle na internet

### AI Agent: modelo e ferramentas
  Gemini 2.0 Flash — custo baixo, latência < 2s para triage em PT-BR
  Tools: wazuh_get_agent, wazuh_active_response, atera_create_ticket, whatsapp_send
  Fallback: se Gemini timeout > 5s, Shuffle executa playbook padrão (HIGH = ticket + WA)
  Audit log: cada decisão do agente gravada em tabela soc_decisions no PostgreSQL

### Sysmon: config recomendada
  Usar sysmon-modular (Olaf Hartong) — melhor cobertura, exclusões otimizadas
  Sysmon gera 2-10x mais eventos que Windows Security Log — dimensionar Indexer
  Hash algorithms: MD5,SHA256,IMPHASH para correlação com threat intel
  Distribuir sysmonconfig.xml via Wodle Command no agent.conf do grupo Windows
