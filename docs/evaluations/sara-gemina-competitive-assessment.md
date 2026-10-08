# Avaliação Competitiva — SARA (GEMINA) vs ness.OS

> Análise técnica de produto  
> Fonte: SARA Agent Windows v1.0 (documentação técnica GEMINA)  
> Foco: Capacidades, arquitetura, diferenças de escopo — sem considerações de timeline ou mercado

---

## 🎯 Veredito

**SARA e ness.OS operam em camadas diferentes da stack de segurança/operações.**

- **SARA:** Especialista de **coleta em endpoint** (eventos, inventário, postura local)
- **ness.OS:** Plataforma de **decisão e orquestração** (correlação, RCA, automação, multi-tenant)

Não são substitutos diretos, mas podem ser **complementares ou competidores** dependendo de arquitetura:
- **Complementar:** SARA → webhook → Hub AIOps (fluxo de dados)
- **Competidor:** Cliente usa SARA como "suficiente" e não investe em orquestração

| Aspecto | SARA | ness.OS |
|---|---|---|
| **Escopo principal** | Endpoint (coleta + postura) | Operações de TI (NOC + AIOps + ITSM) |
| **Núcleo técnico** | Agente C/C++ leve em background | Hub arquiteturado em containers (API + Workers + BD) |
| **Suporta** | Windows 10 1809+ / Server 2016+ | Debian + Docker (Zabbix + PostgreSQL + Redis + Celery) |
| **Escalabilidade** | Ilimitada de agentes (token governa) | 5.000 endpoints (Zabbix) |
| **Banco de dados** | Não mencionado (cloud GEMIN CDOC) | PostgreSQL 16 + TimescaleDB + pgvector |
| **Multi-tenancy** | Não mencionado | ✅ RLS planejado |
| **Autenticação** | SSO (LDAP/OIDC) não na coleta, apenas portal | OIDC + Authentik centralizado |
| **Automação** | Não evidente | ✅ n8n nativo |

---

## 📊 Análise Detalhada

### 1. SARA: O Que É

**Visibilidade contínua de endpoint:**
- Agente leve que roda em background sem interface/login/impacto
- Coleta eventos de segurança do SO e aplicações
- Envia criptografado à plataforma CDOC (controladora GEMINA)
- Dados normalizados, correlacionados, transformados em detecções/alertas
- **Fonte primária de visibilidade** — sem agente, plataforma "só enxerga o que atravessa a rede"

**Plataforma de destino (CDOC — implied in docs):**
- Visibilidade de agentes e seu radar de postura
- Inventário de software (pacotes, autorização, ciclo de vida, shadow IT)
- Gestão de vulnerabilidades (mapa calor: exploração × criticidade, CISA KEV, EPSS, CVEs por SO, SLA de correção)
- Postura de Active Directory (exposição de domínio, superfície Tier 0, equivalente ao PingCastle)

### 2. O Que Mantém do Wazuh

✅ Scan de vulnerabilidades do endpoint  
✅ Compliance contra CIS Benchmark  
✅ Coleta de logs e eventos de segurança

### 3. O Que Adiciona (Novo vs Wazuh)

➕ **Inventário de software e hardware** (GLPI-like, mas somente para o endpoint)  
➕ **Controle de portas USB** (física security)  
➕ **Usuários logados e existentes na máquina** (lateral movement awareness)  
➕ **Correlação e coleta aprimoradas** (claims na doc, não detalha)  
➕ **Visibilidade de vulnerabilidades centralizada** (vs distribuída)  
➕ **Postura do AD** (substitui PingCastle)

### 4. Método de Distribuição

| Método | Quando Usar | Trigger |
|---|---|---|
| **Local** | Servidor crítico, piloto | Manual |
| **GPO (AD)** | Parque em domínio, não migrado ao Intune | Reinicialização |
| **Intune** | Moderno, com estações remotas | Ciclo do IME |

**Segurança do enrollment:**
- Token de enrollment (expiração + limite de agentes obrigatório)
- Tratado como senha — não em SYSVOL, chat, e-mail
- SHA-256 do instalador verificado antes de usar

**Validação de sucesso:**
- Serviço ativo: `sc.exe query SaraAgent` → `STATE : 4 RUNNING`
- Registro no portal SARA (online status) — sintoma mais comum de falha: serviço rodando, máquina não no portal (token expirado, TLS intercept, bloqueia porta 443)

### 5. Rollout Recomendado pela GEMINA

```
Piloto técnico       → Onda 1        → Onda 2        → Onda 3
5–10 máquinas da TI    10% do parque    40% do parque    Restante
```

**Critérios de interrupção (GEMINA avisa para parar):**
- Taxa de falha > 10% em qualquer onda
- CPU do agente > 5% em máquinas ociosas
- Máquinas que não completam registro em 30 minutos

### 6. Pré-requisitos e Rede

| Requisito | Detalhe |
|---|---|
| **SO** | Windows 10 1809+ / Server 2016+, x64, 500 MB livres, PowerShell 5.1 |
| **Rede** | Saída TCP/443 para sara.sigmaone.io e *.sigmaone.io (firewall, proxy, SSE) |
| **TLS intercept** | Se houver SSL break-and-inspect, `sigmaone.io` no bypass (TLS cert pinning no agente) |
| **EDR** | Exclusões recíprocas: diretório do agente + processo `SaraAgent` |

---

## 💾 Arquitetura Técnica

---

## 🔄 Fluxo de Dados e Integração

### SARA: Fluxo de Coleta
```
Endpoint Windows
    ↓ (agente SARA.exe)
Eventos + Inventário + Postura 
    ↓ (criptografado, porta 443)
CDOC Portal (GEMINA cloud/on-prem)
    ↓ (API/webhook?)
[Integrações externas — não documentado]
```

### ness.OS: Fluxo de Operações
```
Múltiplas Fontes
├─ Zabbix (métricas, disponibilidade)
├─ Wazuh (eventos de segurança)
├─ GLPI (inventário, tickets, projetos)
└─ [SARA via webhook?]
    ↓
Hub AIOps (FastAPI)
├─ Fingerprint (deduplicação)
├─ Correlação (eventos → incidentes)
├─ Gemini LLM (RCA)
└─ Redis/PostgreSQL (estado)
    ↓
Orquestração (n8n)
├─ Tickets (GLPI)
├─ Playbooks (RMM, SSH)
└─ Notificações (Evolution/WhatsApp)
    ↓
Portal React (multi-tenant, RBAC)
```

**Diferença fundamental:**
- SARA = **fonte unidirecional** (coleta → plataforma CDOC)
- ness.OS = **hub bidirecional** (múltiplas fontes → decisão → ação → feedback)

---

## 📊 Matriz de Capacidades Técnicas

| Capacidade | SARA | ness.OS | Notas |
|---|---|---|---|
| **Coleta de eventos Windows** | ✅ Nativa | 🟡 Via Wazuh agent | SARA tem SDK de ETW nativo |
| **Inventário de software** | ✅ Curatorado | 🟡 GLPI Agent | SARA envia delta + shadow IT |
| **Controle de portas USB** | ✅ Nativo | ❌ Não planejado | Única diferenciação SARA |
| **Postura de Active Directory** | ✅ Nativo | ❌ Não planejado | Substitui PingCastle |
| **Logs de segurança eventos** | ✅ Windows Event Log | ✅ Via Wazuh/syslog | Equivalentes |
| **Compliance CIS** | ✅ Scanner | 🟡 GLPI Knowledge | SARA automático, ness.OS manual |
| **Detecção de vulnerabilidades** | ✅ Local + feed CISA | ✅ Gemini (RCA) | SARA alerta, ness.OS correlaciona |
| **Correlação de eventos** | 🟡 "Aprimorada" (?) | ✅ Hub AIOps claro | ness.OS tem fingerprint SHA-256 + locks Redis |
| **Deduplicação de alertas** | 🟡 Não mencionado | ✅ Lock distribuído + fingerprint | ness.OS explícito |
| **Automatização de resposta** | ❌ Não mencionado | ✅ n8n + playbooks | ness.OS avança em remediation |
| **ITSM (tickets)** | ❌ Não | ✅ GLPI nativo | Competence separada |
| **Multi-tenancy isolado** | ❌ Não mencionado | ✅ RLS PostgreSQL | ness.OS orientado MSP |
| **API REST estruturada** | 🟡 Mencionada brevemente | ✅ FastAPI documentado | ness.OS mais acessível |
| **CLI/automação** | 🟡 "Comunidade terceiros" | ✅ Python SDK + CLI | ness.OS nativo |
| **Escalabilidade de agentes** | ✅ Ilimitada | ✅ 5.000 endpoints (Zabbix) | Ambos escaláveis |

---

## 🏗️ Comparação Arquitetural

### SARA: Arquitetura Específica de Coleta

```
┌─────────────────────┐
│  Agente SARA.exe    │
│  (C++ leve, 500MB)  │
│  ├─ ETW monitor     │
│  ├─ Inventory scan  │
│  ├─ USB control     │
│  └─ AD query        │
└──────────┬──────────┘
           │
        (mTLS, cert pinning)
           │
        Port 443
           │
      sara.sigmaone.io
           │
┌──────────▼──────────┐
│  CDOC (Cloud)       │
│  ├─ Portal          │
│  ├─ Detections      │
│  ├─ Dashboards      │
│  └─ API (?)         │
└─────────────────────┘
```

**Características:**
- Agente autossuficiente (coleta local, não repousa em rede)
- Comunicação unidirecional (agente → portal)
- Confiança: mTLS + cert pinning (defende contra MITM)
- Token enrollment expiração + limite (govenrança)
- Serviço auto-repair (se falhar, reinicia)

### ness.OS: Arquitetura de Orquestração

```
┌─────────────────────┐     ┌────────────────────┐
│  Zabbix 7.0 LTS     │     │  Wazuh manager     │
│  ├─ Coleta          │     │  ├─ Spokes         │
│  ├─ Disponibilidade │     │  └─ Eventos        │
│  └─ Triggers        │     │                    │
└──────────┬──────────┘     └─────────┬──────────┘
           │                          │
           └──────────────┬───────────┘
                          │ (webhook)
         ┌────────────────▼──────────────┐
         │   Hub AIOps (FastAPI + Workers)│
         │   ├─ Fingerprint/Dedup        │
         │   ├─ Correlation              │
         │   ├─ RCA (Gemini LLM)         │
         │   ├─ Redis (locks + cache)    │
         │   └─ PostgreSQL + pgvector    │
         └────────────────┬──────────────┘
         ┌─────────────────┼─────────────────┐
         │                 │                 │
      ┌──▼──┐          ┌───▼────┐      ┌────▼────┐
      │GLPI │          │  n8n   │      │Authentik│
      │ITSM │          │Workflows│      │  SSO    │
      └─────┘          └────────┘      └────┬────┘
                            │                │
         ┌─────────────────┬─┴────────────────┘
         │                 │
      ┌──▼──────────────┐──▼──────┐
      │  Automação RMM  │Notificações
      │  - Playbooks    │ - WhatsApp
      │  - SSH exec     │ - Email
      │  - Datto/Atera  │ - Chat
      └─────────────────┴─────────┘
         ┌────────────────────┐
         │  React PWA Portal  │
         │  (multi-tenant)    │
         │  ├─ Dashboard NOC  │
         │  ├─ Incidents      │
         │  └─ RBAC          │
         └────────────────────┘
```

**Características:**
- Hub como ponto único de correlação
- Múltiplas entradas de dados (normalize, correlacione)
- Saídas controladas (não tudo passa direto)
- Estado persistente (PostgreSQL + Redis)
- Orquestração condicional (n8n workfows)

---

## 🎯 Diferenças Estruturais
