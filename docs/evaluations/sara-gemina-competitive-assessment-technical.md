# Avaliação Comparativa — SARA (GEMINA) vs ness.OS — VERSÃO TÉCNICA PURA

> **Análise técnica de produto**  
> **Fonte:** SARA Agent Windows v1.0, Guia Rápido de Instalação GEMINA  
> **Foco:** Comparação de arquitetura, capacidades e diferenças estruturais — sem considerações de timeline ou mercado

---

## 🎯 Tese Central

**SARA e ness.OS não são substitutos diretos. Operam em camadas diferentes:**

| Dimensão | SARA | ness.OS |
|---|---|---|
| **Responsabilidade** | VER (coleta + detecção local) | ENTENDER (correlação + decisão) |
| **Pergunta que responde** | "O que aconteceu no meu endpoint?" | "O que significa? O que devo fazer?" |
| **Loop de ação** | Unidirecional (agente → cloud) | Bidirecional (fonte → hub → ação → feedback) |
| **Escala de análise** | Máquina individual | Organização inteira |

---

## 📋 Comparação Técnica Condensada

### Coleta e Visibilidade

| Aspecto | SARA | ness.OS |
|---|---|---|
| **Fonte primária** | Agente Windows nativo (ETW + WMI) | Multiple (Zabbix + Wazuh + GLPI) |
| **O que coleta** | Eventos SO, inventário, USB, AD posture | Métricas + eventos + ativos + tickets |
| **Único diferenciador** | USB control + AD posture (PingCastle replacement) | Multi-source correlation |
| **Qualidade de coleta** | Especializada (Windows endpoint) | Generalista (toda stack) |
| **Overhead computacional** | Muito baixo (background service, não visível) | Moderado (Hub é container, não no endpoint) |

### Processamento e Análise

| Aspecto | SARA | ness.OS |
|---|---|---|
| **Lógica de processamento** | Local (agente calcula compliance) + cloud (detections) | Centralizado no Hub (fingerprint, correlação,RCA) |
| **Deduplicação** | Não mencionada | ✅ Explicit (SHA-256 fingerprint + Redis locks) |
| **Correlação de eventos** | "Aprimorada" (vago) | ✅ Explícita (fingerprint → incidente) |
| **Inteligência artificial** | Não mencionada | ✅ Gemini 2.5 Flash (RCA) |
| **Detecção de anomalias** | Alertas pré-configurados CISA/EPSS | ✅ Gemini (pattern discovery) |

### Orquestração e Resposta

| Aspecto | SARA | ness.OS |
|---|---|---|
| **Automação de resposta** | Não mencionada | ✅ n8n (workflows condicionais) |
| **Tickets/ITSM** | Não integrado | ✅ GLPI nativo |
| **Notificações** | Portal SARA apenas | ✅ WhatsApp, email, Slack (n8n routing) |
| **Remediação** | Não documentada | ✅ RMM playbooks automatizados |
| **Feedback loop** | Não (coleta → detecção apenas) | ✅ (incidente → ação → nova coleta) |

### Multitenancy e Governança

| Aspecto | SARA | ness.OS |
|---|---|---|
| **Multi-tenant nativo** | ❌ Não mencionado | ✅ RLS PostgreSQL planejado |
| **Isolamento de dados** | Org-path no token | Cliente-level no banco de dados |
| **RBAC granular** | Token + portal roles (não detalhado) | ✅ Authentik + GLPI roles |
| **Auditoria** | Não documentada | ✅ PostgreSQL audit logs |
| **Governança de secrets** | Token com expiração | Psono Community (PoC) + SOPS/age |

---

## 🔌 Padrões de Integração Possível

### Cenário 1: SARA como Fonte Adicional

```
SARA (coleta Windows postura)
    ↓ webhook
Hub AIOps
    ↓
Correlação + RCA
    ↓
n8n (ação)
```

**Requer:**
- Webhook SARA → FastAPI Hub (não documentado, custom)
- Normalização SARA events → modelo ness.OS
- Novo connector em ness.OS para SARA data

**Benefício:** Captura USB + AD posture que Wazuh não cobre

### Cenário 2: SARA como Substituição Parcial

```
Cliente abandona Wazuh
    SARA (eventos Windows substituem Wazuh agent)
    ├─ Zabbix (métricas)
    ├─ SARA (eventos + inventário)
    └─ GLPI (tickets + CMDB)
    ↓
Hub AIOps (correlação apenas)
```

**Risco:** SARA é Windows-only. Linux/network não coberlo.

### Cenário 3: SARA é "Suficiente"

```
Cliente usa SARA portal
    └─ Todas as detecções no CDOC
    ↓
Não adota ness.OS (competição direta pelo tempo do cliente)
```

---

## 🏛️ Arquitetura Comparada

### SARA: Coleta Especializada

```
┌─────────────────────────────────────┐
│        Agente SARA (C++)            │
├─────────────────────────────────────┤
│  - ETW (Event Tracing for Windows)  │
│  - WMI queries (inventory)          │
│  - USB monitoring                   │
│  - LDAP/AD queries (posture)        │
│  - CIS compliance scanner           │
│  - CISA CVE feed (local cache)      │
├─────────────────────────────────────┤
│  Token enrollment (mTLS pinning)    │
│  Service auto-repair                │
│  Bi-hourly check-in                 │
└──────────────┬──────────────────────┘
               │
        Port 443 (TLS 1.3)
               │
    ┌──────────▼──────────┐
    │  CDOC (GEMINA)      │
    │  - Detections       │
    │  - Dashboards       │
    │  - API (unclear)    │
    └─────────────────────┘
```

**Design Philosophy:**
- Agente é **autossuficiente** (não depende de coleta parcial)
- Cloud é **stateless para agente** (histórico não precisa ficar no agente)
- Confiança é **token + mTLS** (sem dependência de infraestrutura corporativa)

### ness.OS: Orquestração Centralizada

```
┌──────────────────┐  ┌─────────────────┐
│  Zabbix 7.0 LTS  │  │ Wazuh Manager   │
└────────┬─────────┘  └────────┬────────┘
         │                    │
         └────────┬───────────┘
                  │ (webhook)
      ┌───────────▼──────────────┐
      │  Hub AIOps (FastAPI)     │
      ├──────────────────────────┤
      │  1. Ingest               │
      │  2. Normalize            │
      │  3. Fingerprint (SHA256) │
      │  4. Deduplicate (Redis)  │
      │  5. Correlate            │
      │  6. RCA (Gemini LLM)     │
      │  7. Score/Qualify        │
      ├──────────────────────────┤
      │  PostgreSQL + Redis      │
      │  Workers (Celery)        │
      └────────┬────────┬────────┘
               │        │
       ┌───────▼┐  ┌────▼─────┐
       │  n8n   │  │ GLPI+    │
       │Workflow│  │Authentik │
       └─────────┘  └──────────┘
               │
       ┌───────▼──────────┐
       │  Portal React    │
       │  (multi-tenant)  │
       └──────────────────┘
```

**Design Philosophy:**
- Hub é **ponto único de inteligência** (múltiplas fontes → uma verdade)
- Correlação é **semântica** (fingerprint, não ID)
- Ação é **condicional** (n8n workflows, not hardcoded)

---

## 💾 Diferenças Estruturais Fundamentais

### SARA: Pattern Matching

```
Event A (timestamp, host, eventID)
    ↓
Local rule (CIS/CISA)
    ↓
Alert: "Found X"
    ↓
[End — ação depende do operador no portal]
```

### ness.OS: Semantic Correlation

```
Event A (Zabbix: CPU spike)
Event B (Wazuh: login attempt)
    ↓
Fingerprint A+B (SHA256(host + type + time))
    ↓
Redis lock (prevent duplicate processing)
    ↓
Gemini LLM (context: "What does this mean together?")
    ↓
Incident C: {"type": "lateral_movement_attempt", "severity": HIGH, "next_action": "block_login_from_ip"}
    ↓
n8n workflow:
  IF severity == HIGH:
     ticket = GLPI.create(...)
     ansible_run("firewall_block", host=X)
     whatsapp_notify("SOC", incident_link)
  ELSE:
     log_to_postgres()
```

**Diferença:**
- SARA = **reativo** (evento → alertá)
- ness.OS = **preditivo** (múltiplos eventos → contexto → ação)

---

## 📊 Matriz de Competência

| Competência | SARA | ness.OS | Vencedor |
|---|---|---|---|
| **Visibilidade de Windows endpoint** | ✅✅✅ Nativa, especializada | 🟡🟡 Via agente Wazuh | SARA |
| **Postura de Active Directory** | ✅✅✅ Nativa (PingCastle replacement) | ❌ Não planejado | SARA |
| **Controle de portas USB** | ✅✅✅ Nativo | ❌ Não | SARA |
| **Correlação de eventos** | 🟡 Vago ("aprimorada") | ✅✅✅ Explícita, provável | ness.OS |
| **RCA via IA** | ❌ Não mencionado | ✅✅✅ Gemini | ness.OS |
| **Automação orquestrada** | ❌ Não mencionado | ✅✅✅ n8n | ness.OS |
| **ITSM integrado** | ❌ Não | ✅✅✅ GLPI | ness.OS |
| **Escalabilidade de agentes** | ✅✅✅ Ilimitada (token governa) | ✅✅ 5K endpoint (Zabbix) | SARA |
| **Multi-tenancy isolado** | ❌ Não mencionado | ✅✅✅ RLS planejado | ness.OS |
| **Facilidade de deploy** | ✅✅✅ Local + GPO + Intune | 🟡 Docker-dependent | SARA |
| **Criptografia ponta-a-ponta** | ✅✅✅ mTLS + pinning | 🟡 TLS para portal apenas | SARA |

---

## 🎯 Conclusão

### Se a Pergunta É "Quem Coleta Melhor?"

**SARA vence.** Especialistas em Windows, nativo de USB/AD posts/inventário. ness.OS depende de Wazuh agent for eventos similares.

### Se a Pergunta É "Quem Decide Melhor?"

**ness.OS vence.** Hub de correlação, RCA via IA, automação orquestrada. SARA não tem conceito de "próxima ação".

### Se a Pergunta É "Quem É Mais Completo?"

**Depende do cliente:**
- **Cliente precisa COLETA especializada + DECISÃO rápida:** Ambos (SARA coleta, ness.OS orquestra)
- **Cliente precisa coleta e é suficiente:** SARA (CDOC como tudo o que precisa)
- **Cliente precisa multi-tenant + operações unificadas:** ness.OS (Zabbix + Wazuh + GLPI)
- **Cliente é Windows-only:**  SARA (sem overhead Linux)
- **Cliente é heterogêneo (Windows + Linux + cloud):** ness.OS (suporta múltiplas fontes)

### Se a Pergunta É "Qual É o Futuro?"

**Integração.** SARA especialista → ness.OS orquestrador. Não competição, complementação.

```
┌─────────────────┐
│ Windows Posture │
│ (SARA)          │  ──┐
│ + USB control   │    │
└─────────────────┘    │    ┌──────────────┐
                       ├───→│ ness.OS Hub  │
┌─────────────────┐    │    │ (RCA + Auto) │
│ Eventos & Logs  │    │    └──────────────┘
│ (Zabbix+Wazuh)  │  ──┤
└─────────────────┘    │
                       │
┌─────────────────┐    │
│ Tickets & CMDB  │    │
│ (GLPI)          │  ──┘
└─────────────────┘
```

---

**Avaliação técnica conclusiva, sem timeline.**  
**Foco: Arquitetura, capacidade, diferenças estruturais.**  
**Próximo passo: Decidir integração (webhook, normalização, fluxos de dados).**
