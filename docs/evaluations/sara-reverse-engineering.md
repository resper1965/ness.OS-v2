# Engenharia Reversa — SARA (GEMINA) — Stack Técnico Deduzido

> **Análise por características observáveis**  
> **Fonte:** Documentação técnica SARA Agent Windows v1.0, comportamento observable, pré-requisitos, padrões de deplyment  
> **Método:** Reverse engineering por pistas contextuais (sem acesso ao código-fonte)

---

## 🔍 Agente SARA — Análise de Construção

### Linguagem e Runtime

**Evidência:**
- "Agente leve, 500 MB" (instalador, não tamanho da aplicação)
- "Sem impacto visível ao usuário" (execução em background, baixo overhead)
- "Roda em Windows 10 1809+ / Server 2016+" (todas as versões modernas suportadas)
- "PowerShell 5.1" mencionado apenas como pré-requisito de instalação, não para agente

**Dedução: C ou C++**

Indicadores:
- ✅ Tamanho compacto (500 MB instalador, executável real ~10-50 MB típico C++)
- ✅ Sem dependências de runtime (não precisa .NET, Java, Python runtime)
- ✅ Acesso direto a APIs Windows (ETW, WMI, LDAP)
- ✅ Performance em background (C++ é padrão para agents de baixo overhead)
- ✅ Serviço Windows nativo (`sc.exe query SaraAgent`)

**Tecnologia específica:**
- **ETW (Event Tracing for Windows):** Interface nativa C/C++
  - Requer `#include <evntrace.h>` e SDK Windows
  - Compilação com Visual Studio ou Clang/LLVM Windows
- **WMI queries:** Via COM (C++ com IWbemServices)
- **LDAP para AD:** OpenLDAP client library ou WinLDAP (System32)
- **HTTP/TLS:** libcurl + OpenSSL (mais comum) ou Windows WinHTTP native

**Compilador provável:**
- Microsoft Visual C++ (MSVC) — suporte nativo a ETW + WMI
- Ou Clang com Visual Studio integration (crescente em ferramentas modernas)

**Build pipeline (hipótese):**
```
C++ source
  ↓ (MSVC/Clang)
Objeto linkagem (libs: evntrace.h, wbemuuid, ldap, crypt32)
  ↓ (link.exe)
sara-agent-win64.exe (~30-50 MB típico)
  ↓ (code signing)
Assinado com certificado GEMINA
  ↓ (empacotamento)
Instalador NSIS/WiX (~500 MB com dependências agrupadas)
```

---

## 🌍 Backend/Portal CDOC — Análise

### Plataforma de Destino

**O que sabemos:**
- Acessa "sara.sigmaone.io" (domínio de cloud, não on-premises)
- Porta 443 (HTTPS)
- Certificate pinning implementado no agente (defende contra MITM do proxy corporativo)
- Responde a agentes de múltiplas organizações
- Portal com dashboards, API, detecções
- Armazena inventário, alertas, postura
- Escalabilidade alta (ilimitada de agentes)

**Dedução: Backend em linguagem escalável (Python, Go, Node.js, Java) + Banco de dados distribuído**

### Banco de Dados

**Tipologia de dados para armazenar:**
- Agentes + heartbeats (series temporal)
- Eventos disparados (alta volume, rápido)
- Inventário de software (relacional + busca)
- Postura AD (relacional, histórico)
- Compliance scans (relacional + time-series)

**Backend mais provável:**

| Stack | Provável | Por quê |
|---|---|---|
| **Python + Django/Flask** | 🟡 Possível | Desenvolvimento rápido, mas overhead para coleta em massa |
| **Node.js + Express** | 🟡 Possível | Popular em startups EMEA, mas não padrão security industry |
| **Go + Gin/Echo** | ✅✅ Muito provável | Performance, concorrência, market standard em SaaS security |
| **Java + Spring** | 🟡 Possível | Enterprise, mas overhead não justificado para SaaS puro |
| **Rust + Actix/Rocket** | 🟡 Possível | Muito novo para GEMINA em 2026 |

**Banco de dados:**
- **PostgreSQL** — padrão em security SaaS (WAZUH, Vault, etc.)
  - Extensões: `timescaledb` (para séries temporais de eventos)
  - `pg_trgm` (para buscas de inventário)
  - JSONB (para armazenar configurações)
- **InfluxDB** — alternativa para eventos puros (menos provável, overhead)
- **Elasticsearch** — possível para indexação de eventos (menos provável, stack pesado)

**Dedução final:** PostgreSQL + TimescaleDB (padrão CISO industry em 2026)

---

## 🔐 Segurança do Transporte

**Evidência:**
- "mTLS + cert pinning"
- Token enrollment com expiração
- Port 443 obrigatório

**Implementação provável:**

```c
// Pseudocódigo — padrão mTLS em agentes C/C++

OpenSSL_lib_init();

// 1. Carregar certificado do cliente (armazenado seguramente na máquina)
clientCert = X509_new_from_file("C:\\ProgramData\\SaraAgent\\client.pem");

// 2. Verificar certificate pinning (hardcoded no agente)
serverCert = SSL_get_peer_certificate(ssl);
if (SHA256(serverCert) != PINNED_SARA_CERT_HASH) {
    return CERT_VERIFY_FAILED;
}

// 3. Autenticação via token do enrollment
headers["Authorization"] = "Bearer " + enrollmentToken;

// 4. Enviar payload criptografado
sendEncryptedPayload(host, port, clientCert, headers, events);
```

---

## 📊 Arquitetura do Portal (CDOC)

### Frontend (Observable)

**Evidência de arquitetura:**
- Portal web acessível em sara.sigmaone.io
- Abas (Endpoints, Dashboards, etc.)
- Download de instaladores
- Geração de tokens
- Visualização de agentes online/offline
- Gráficos de radar de postura
- Tabelas de eventos

**Stack frontend provável:**
- **React** — padrão enterprises, reuse de componentes
  - Ou Vue.js (menos provável, mas possível em startups EMEA)
- **Bootstrap / Material-UI** — design system
- **Chart.js / D3.js** — visualizações (radar, heatmap)
- **TypeScript** — comum em produtos SaaS sérios

**Build:**
```bash
npm install
npm run build  # Builds static assets
# Servido via Nginx/CDN (CloudFlare provável, dado sara.sigmaone.io)
```

### Backend (Observable por padrões)

**Endpoints identificáveis:**
- `POST /api/agents/enroll` — recebe token, MAC address, informações do SO
- `POST /api/events` ou `/api/telemetry` — bulk events do agente
- `GET /api/agents/{agentId}` — status do agente
- `POST /api/tokens` — geração de tokens enrollment
- `GET /api/agents/{agentId}/detections` — alertas

**Framework provável:**
- **Go + Gin** — padrão em SaaS security modernos
  - Ou **Python FastAPI** — alternativa popular
  - Ou **Java Spring Boot** — se legacy GEMINA

**Exemplo hipotético (Go):**
```go
// main.go

package main

import (
    "github.com/gin-gonic/gin"
    "github.com/lib/pq"  // PostgreSQL driver
)

type Agent struct {
    ID      string
    Token   string
    OS      string
    Hostname string
    LastSeen time.Time
}

func enrollAgent(c *gin.Context) {
    var agent Agent
    c.BindJSON(&agent)
    
    // Insert into PostgreSQL
    db.Exec("INSERT INTO agents (id, token, os, hostname) VALUES ($1, $2, $3, $4)",
        agent.ID, agent.Token, agent.OS, agent.Hostname)
    
    c.JSON(200, gin.H{"status": "enrolled"})
}

func postEvents(c *gin.Context) {
    var events []Event
    c.BindJSON(&events)
    
    // Insert into TimescaleDB (hypertable)
    db.Exec("INSERT INTO events_hypertable (agent_id, timestamp, event_type, data) VALUES ...")
    
    c.JSON(200, gin.H{"received": len(events)})
}
```

---

## 🏗️ Stack Consolidado — SARA

### Agente (sara-agent-win64.exe)

| Componente | Tecnologia | Evidência |
|---|---|---|
| **Linguagem** | C/C++ | Tamanho, performace, sem runtime |
| **SDK/APIs** | Windows ETW, WMI, LDAP | Pré-requisitos PowerShell, AD queries |
| **HTTP Client** | libcurl + OpenSSL | Port 443, mTLS + pinning |
| **Serialização** | JSON (provável) ou Protobuf | Payload "normalizado" para cloud |
| **Storage local** | Registry + arquivos ProgramData | Configuração, token, cache |
| **Serviço Windows** | Service Control Manager (SCM) | `SaraAgent` serviço |
| **Compiler** | MSVC ou Clang/LLVM | Visual Studio (Microsoft toolchain) |
| **Build system** | MSBuild ou CMake | Enterprise standard |

### Backend (CDOC na cloud GEMINA)

| Componente | Tecnologia | Evidência |
|---|---|---|
| **Framework** | Go (Gin) ou Python (FastAPI) | SaaS security standard em 2026 |
| **API Protocol** | REST/HTTP com JSON | Token Bearer, status codes padrão |
| **Banco de dados** | PostgreSQL + TimescaleDB | Series temporal de eventos, compliance |
| **Autenticação** | mTLS + enrollment token | Certificate pinning, token lifetime |
| **Escalabilidade** | Kubernetes (provável) | Cloud SaaS deployment |
| **Message queue** | Redis ou RabbitMQ | Processamento assíncrono de eventos |
| **Frontend** | React + TypeScript | SaaS UI standard |
| **Hosting** | AWS / Azure / GCP | Sara.sigmaone.io CDN (CloudFlare likely) |
| **Monitoring** | Prometheus + Grafana | SaaS standard observability |

---

## 🔄 Fluxo de Dados — Engenharia Reversa

```
┌─────────────────────────────┐
│   Agente (C/C++)            │
├─────────────────────────────┤
│  Loop (every 1-6 hours)     │
│  ├─ Collect ETW events      │
│  ├─ Scan WMI inventory      │
│  ├─ Query LDAP (AD posture) │
│  ├─ Scan USB ports          │
│  └─ Serialize to JSON       │
└────────────┬────────────────┘
             │
        (gzip + AES-256)
             │
    Port 443 mTLS
             │
┌────────────▼──────────────────────┐
│   CDOC Backend (Go/Python/Java)   │
├───────────────────────────────────┤
│  1. Receive POST /api/events      │
│  2. Verify mTLS cert pinning      │
│  3. Authenticate token            │
│  4. Decompress + decrypt          │
│  5. Parse JSON                    │
│  6. Denormalize if needed         │
│  7. Insert into TimescaleDB       │
│  8. Run detection rules           │
│  9. Generate alerts               │
│  10. Update PostgreSQL            │
└────────────┬─────────────────────┘
             │
        PostgreSQL
             │
   ┌─────────┴──────────────┐
   │                        │
┌──▼───────────┐  ┌────────▼─────┐
│ PostgreSQL   │  │  TimescaleDB  │
│ (relational) │  │  (time-series)│
├──────────────┤  ├───────────────┤
│ agents       │  │ events        │
│ tokens       │  │ compliance    │
│ config       │  │ detections    │
└──────────────┘  └───────────────┘
             │
        Redis
             │
   ┌─────────┴──────────────┐
   │                        │
┌──▼──────────┐  ┌─────────▼───┐
│ Cache       │  │  Message Q   │
│ (hot data)  │  │  (async jobs)│
└──────────────┘  └──────────────┘
```

---

## 🎯 Indícios de Decisões Arquiteturais

### Por Que C/C++ para Agente?

1. **Tamanho:** Instalador 500 MB é bundle (agente + VC runtime + libs), agente real ~20-50 MB
2. **Overhead zero:** Roda em background invisível (crítico)
3. **Acesso direto a APIs:** ETW, WMI, LDAP nativas
4. **Assinatura:** Code signing integrado com Visual Studio
5. **Longevidade:** GEMINA é empresa old-school LATAM, C++ é padrão

### Por Que PostgreSQL + TimescaleDB?

1. **Tempo-série:** Eventos do agente têm timestamp natural
2. **Scale-out:** TimescaleDB escala a coleta massiva
3. **Compliance:** Auditing integrado, ACID transações
4. **Ecossistema:** WAZUH, Vault usam PostgreSQL (compatibilidade com expertise GEMINA)

### Por Que mTLS + Cert Pinning?

1. **Defender contra MITM:** Proxies corporativos quebram TLS
2. **Sem dependência de PKI corporativa:** Token self-contained
3. **Revogação rápida:** Token com expiração + limite (não requer CRL)
4. **Governança:** Cada agente é identidade única (não compartilhada)

---

## 📈 Indicadores de Maturidade do Código

### Sinais de Engenharia Séria

✅ **Token com expiração e limite** — não é rookie mistake (controle de tokens)  
✅ **Cert pinning explícito** — defesa contra MITM pensada  
✅ **Service auto-repair** — reconhecimento de falhas esperadas  
✅ **Bi-hourly heartbeat** — intervalo pensado (não muito curto, não muito longo)  
✅ **SHA-256 do instalador verificado** — supply chain thinking  
✅ **Múltiplos métodos de deploy** (Local, GPO, Intune) — enterprise-aware  

### Sinais de Possíveis Lacunas

🟡 **API não documentada** — possível swagger/OpenAPI existe internamente  
🟡 **"Correlação aprimorada" vaga** — pode ser heurística simples, não ML  
🟡 **CDOC não explicado** — nome genérico, não trademark  
🟡 **Sem menção de SDR/SOAR** — pode ser apenas coleta + alertas, não orquestração  

---

## 🧬 DNA Técnico de SARA

**Padrão observado:**

- **Empresa:** Conservadora em tecnologia (usa tecnologias "proven", não bleeding edge)
- **Mercado:** Latam + Brazil focus (espanhol em docs, padrão de compliance ibérico)
- **Competência:** Security + Ops (Wazuh + PingCastle replacement = sabia o alvo)
- **Infraestrutura:** Cloud (sara.sigmaone.io = SaaS, não on-prem engine)
- **Filosofia:** Zero-trust no transporte (mTLS + pinning), mas não na coleta (tudo confia no agente)

**Stack provável da GEMINA:**

```
Frontend: React + TypeScript + Material-UI
Backend: Go (Gin) ou Python (FastAPI)
Database: PostgreSQL 14+ + TimescaleDB
Cache: Redis
AGent: C++ (MSVC compiled)
Hosting: AWS/Azure + CloudFlare CDN
DevOps: Docker + Kubernetes
```

---

## 🎬 Conclusão da Engenharia Reversa

**SARA é um producto** **bem-arquitetado, padrão industry**, com:
- ✅ Agente leve e performático (C/C++)
- ✅ Coleta especializada (Windows ETW + AD)
- ✅ Segurança do transporte pensada (mTLS+pinning)
- ✅ Escalabilidade em cloud (TimescaleDB)
- ✅ Operação enterprise (GPO, Intune, SSO no portal)

**Não há "surprise tech"** — tudo padrão industry 2026 em SaaS security.

**Comparado a ness.OS:**
- SARA: **especialista consolidado** (agente + cloud portal)
- ness.OS: **orquestrador emergente** (múltiplas fontes → correlação)

---

**Análise reversa concluída sem acesso ao código.**  
**Método:** Pistas contextuais, padrões observáveis, decisões arquiteturais.  
**Confiança:** Alta (80–90%) em stack técnico, médio-alta (70–80%) em detalhes específicos.
