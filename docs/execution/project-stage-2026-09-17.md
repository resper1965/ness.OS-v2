# ness.OS — Estágio do Projeto e Status Consolidado (2026-09-17)

> **Base:** Consolidação de 27 dias de execução (21/08–17/09/2026)
> **Responsável:** Ricardo Esper  
> **Fase:** Gate 0 estendido — núcleo operacional fragmentado, transmutação vencida

---

## 1. Diagnóstico Executivo

### ✅ Fundação Operacional Consolidada

| Componente | Status | Qualidade |
|---|---|---|
| **Zabbix NOC (produção)** | Ativo, limpo do XMRig, backup diário | ESTÁVEL |
| **Hub AIOps (pré-produção)** | 14 contêineres, dockerizado, backup noturno | SAUDÁVEL |
| **Backup local** | Zabbix + AIOps ambos testados com restore isolado | ✅ VALIDADO |
| **Backup externo S3** | Restic em Contabo Object Storage, checksums OK | ✅ VALIDADO |
| **Segredos em repositório** | Triados, reduzidos de 69 para 0 Gitleaks | 🟡 PARCIAL (Psono ainda não ativo) |
| **Política de privilégio** | `platform_admin` restrito a 3 pessoas | ✅ APROVADO |

### ❌ Transmutação Zabbix BLOQUEADA (27 DIAS VENCIDO)

| Atividade | Planejado | Status | Bloqueador |
|---|---|---|---|
| **Fábrica KVM8** | 21/08 + 3-5 dias | ✅ Concluída (22/08) | — |
| **Polimento backlog** | 22/08 + 5 dias | 🔴 NÃO INICIADO | Falta decisão formal |
| **Nova Contabo limpa** | 24/08 + contratação | 🟡 PENDENTE | Bloqueio de compra externo |
| **Corte DNS/IP** | 27/08 + janela + 7 d | 🔴 NÃO EXECUTADO | Dependência anterior |
| **Homologação Authentik-Zabbix** | Paralelo | 🔴 NÃO INICIADA | Falta proprietário |

**Resultado:** etapa planejada para 10–12 dias úteis levou 27 dias calendário e **não saiu de Gate 0**.

---

## 2. Concluído desde 21/08

### Segurança & Incidente

- ✅ XMRig removido, persistência neutralizada
- ✅ Conta `Admin` Zabbix desabilitada
- ✅ Senhas root rotacionadas, SSH por chave obrigatório
- ✅ Scripts suspeitos (58x) quarentenados
- ✅ Execução remota desabilitada no Zabbix Server
- ✅ Fail2ban restaurado e testado

### Backup & Recuperação

- ✅ Backup local diário habilitado (Zabbix 22:00, AIOps 23:00)
- ✅ Restore isolado comprovado (Zabbix: 203 tabelas, 674 hosts, 60.250 itens)
- ✅ Backup externo Restic automatizado (timer 23:30 Zabbix, 00:30 AIOps)
- ✅ Checksums SHA-256 validados ponta a ponta
- ✅ RPO 24h, RTO <4h comprovado em laboratório

### Infraestrutura

- ✅ KVM8 Hostinger reinstalada e endurecida (staging apenas)
- ✅ MariaDB 10.11.18 e Zabbix 7.0.27 em KVM8 idênticos à produção
- ✅ Swap persistente (8 GB Zabbix, 4 GB AIOps) sem reinício
- ✅ UFW e Fail2ban validados nas duas VPS
- ✅ NTP sincronizado, fuso `America/Sao_Paulo` correto

### Identidade & RBAC

- ✅ `platform_admin` restrito: Ricardo Esper, Rogério Salerno, Ismael Araujo
- ✅ Agnaldo Silva como User (observação)
- ✅ Conta técnica GLPI criada (`svc_ness_os`)
- ✅ Fluxo OIDC Hub→Authentik funcionando (OAuth callback corrigido)
- 🟡 Zabbix SAML: iniciado, não homologado

### Imagens & Artefatos

- ✅ 10 imagens Docker fixadas por digest
- ✅ GLPI 11.0.8 pinned
- ✅ Defaults PostgreSQL/Authentik rotacionados
- ✅ Credencial Basic Auth removida do frontend
- ✅ JWT Hub rotacionado, sessões revogadas

### Integração GLPI

- ✅ Manifesto GLPI validado: 5 projetos, 13 work packages, 8 categorias
- ✅ Coleta GLPI Agent pronta (distribuição por RMM)
- ✅ API read-only testada (`importador` dry-run idempotente)
- 🟡 API gravação ainda bloqueada (rota privada AIOps→GLPI em PoC)

---

## 3. Em Andamento (Bloqueado)

### Polimento Zabbix (Backlog)

**Pendente desde 22/08:**

- 1.204 itens ativos não suportados (2,88%)
- 584 triggers habilitadas `unknown`
- 1.829 escalations históricas vencidas
- 274 hosts sem tags
- 20 hosts sem template

**Causa:** falta decisão executiva:
- Limpar em SQL direct (risco)?
- Reduzir lote por lote com validação?
- Aceitar as anomalias como técnica debt?

**Bloqueador:** ninguém foi designado como responsável.

### Transmutação Zabbix (plano vencido)

**Fases concluídas:**
1. ✅ Entrada e bootstrap KVM8
2. ✅ Fábrica reproduzível
3. 🟡 Ensaio restauração (parcial — sem coleta)

**Fases bloqueadas:**
4. ❌ Polimento pré-corte — aguardando decisão do backlog
5. ❌ Qualificação — UAT completo com coleta
6. ❌ Pacote de saída — documentação reproduzível
7. ❌ Corte final — nova Contabo + DNS + validação

**Causa raiz:** condicionalidade circular:
- Não é possível qualificar sem polimento
- Não é possível polir sem decisão sobre backlog
- Não é possível cortar sem qualificação comprovada

### Nova VPS Contabo Permanente

**Status:** aguardando aprovação de compra
- Especificação pronta: 8 vCPU, 32 GB RAM, 1 TB SSD
- Procedência: Contabo `Storage VPS 40`
- Custo: ~€55/mês
- Uso: Zabbix permanente pós-transmutação

**Bloqueador:** autorização de compra não documentada. KVM8 pode continuar como bridge por mais 14 dias se necessário.

### Homologação Identidade

**Status Authentik:**
- ✅ Core saudável
- ✅ Hub integrado
- 🟡 GLPI: acesso nominal validado, MFA não testada
- 🟡 n8n: sem teste
- 🟡 Zabbix SAML: configurado, sem validação ponta a ponta
- ❌ Wazuh: não iniciado (Wazuh fora do escopo Gate 0)

**Bloqueador:** nenhuma aplicação foi homologada formalmente. Falta matriz RACI.

---

## 4. Decisões Críticas Pendentes

### D-PAC-1: Estratégia de Polimento Zabbix

**Problema:** backlog técnico impede corte.

**Opções:**
1. **Limpar em lote controlado** (recomendado por engenharia)
   - Onda 1: FortiGate, switches, janelas de manutenção
   - Onda 2: Windows, Linux menores
   - Onda 3: triggers/escalations por template
   - Risco: baixo (rollback por restore)
   - Prazo: 5 dias úteis + validação 2 dias

2. **Aceitar como técnica debt**
   - Suspender polimento, cortar com backlog
   - Registrar riscos operacionais (falsos positivos, alertas obsoletos)
   - Risco: alto (sem rollback se problema emergir em produção)
   - Prazo: 0 dias (imediato)

3. **Aiar completamente**
   - Suspender transmutação indefinidamente
   - Manter Zabbix na Contabo origem com HotFix apenas
   - Risco: médio (não há snapshot comparativo, drift aumenta)
   - Prazo: indefinido

**Recomendação:** Opção 1 + aprovação explícita de Ricardo Esper.

**Decisor:** Ricardo Esper  
**Prazo para decisão:** 18/09/2026 (amanhã)

---

### D-PAC-2: Contratação da Nova Contabo

**Problema:** especificação pronta, mas sem compra formal.

**Cenário A — Contratação imediata:**
- Lead time: 24–48 horas
- Custo: ~€55/mês (permanente)
- Benefício: desacoplar KVM8 de produção

**Cenário B — Adiar + usar KVM8 estendida:**
- Lead time: 0 (máquina já existe)
- Custo: ~€9/mês (KVM8 temporária)
- Risco: KVM8 pode ser cancelada a qualquer hora
- Validade: máximo 14 dias sem compra Contabo

**Recomendação:** Cenário A — contratação hoje, não vale economizar €45 este mês se houver rerisco operacional.

**Decisor:** Ricardo Esper  
**Prazo para decisão:** 18/09/2026

---

### D-PAC-3: Psono Community ou Adiar Cofre

**Problema:** segredos ainda sem casa (Psono PoC não iniciado).

**Opções:**
1. **Iniciar Psono PoC paralelo** (não bloqueia Zabbix)
   - VPS nova 2 vCPU, 4 GB, 40 GB
   - Prazo: 3 dias para PoC, 2 dias para hardening
   - Custo: ~€3/mês
   - Benefício: libera pipeline de secrets

2. **Adiar até Gate 1**
   - Manter segredos em arquivo local (atual)
   - Risco: acesso break-glass, auditoria, automação
   - Custo: 0 (mas atrasa)

**Recomendação:** Opção 1 — não bloqueia Zabbix, ativa cofre em paralelo.

**Decisor:** Ricardo Esper  
**Prazo para decisão:** 18/09/2026

---

## 5. Cronograma Realista (Revisado)

### Cenário Base: Decisões Aprovadas Amanhã

```
17/09 — Consolidação de status (hoje)
18/09 — Decisões críticas aprovadas
  ↓
19/09 — Polimento Onda 1 iniciado (FortiGate + switches)
20–21/09 — UAT FortiGate (staging KVM8)
22/09 — Validação, rollback pronto
  ↓
23/09 — Onda 2 polimento (Windows menores)
24–25/09 — UAT Onda 2
26/09 — Validação
  ↓
27/09 — Onda 3 (triggers/escalations)
28–29/09 — UAT Onda 3
30/09 — Validação final
  ↓
01/10 — Qualificação completa (coleta representativa)
02–03/10 — Testes TLS, proxy, MFA, autenticação
04/10 — Homologação Authentik-Zabbix
  ↓
05/10 — Empacotamento final (infraestrutura, runbooks, checksums)
06/10 — Aprovação técnica (go/no-go)
  ↓
07/10 — **CORTE PARA CONTABO NOVA**
        (janela 22:00 BRT, DNS + IP)
  ↓
08–14/10 — Observação (7 dias, rollback pronto)
15/10 — Aceite e liberação forense da Contabo origem
  ↓
16/10 — **Gate 1 Zabbix concluído**
```

**Melhorias vs. plano anterior:**
- Paralelização explícita (Psono + Zabbix)
- Ondas de polimento independentes
- Checkpoint a cada 2 dias
- Rollback garantido (não linear)

---

## 6. Ações Imediatas (Responsáveis & Prazos)

| Ação | Responsável | Prazo | Aceite |
|---|---|---|---|
| Aprovar estratégia Polimento (D-PAC-1) | Ricardo Esper | 18/09, 17:00 |  |
| Autorizar compra Contabo nova (D-PAC-2) | Ricardo Esper | 18/09, 17:00 |  |
| Autorizar PoC Psono (D-PAC-3) | Ricardo Esper | 18/09, 17:00 |  |
| Designar eng. Zabbix Onda 1 polimento | Ricardo Esper | 18/09, 18:00 |  |
| Provisionar VPS Psono | Eng. Infraestrutura | 19/09, meio-dia |  |
| Iniciar Onda 1 FortiGate | Eng. Zabbix | 19/09, 14:00 |  |
| Atualizar docs/execution/project-stage-2026-09-17.md | Eng. DevOps | 18/09, 20:00 |  |

---

## 7. Conclusão

**Gate 0 foi estendido de forma aceitável:**
- Incidente = contido e eliminado
- Backup = validado e operacional
- Infraestrutura = hardened e monitorada

**Transmutação venceu por falta de autorização executiva, não por impossibilidade técnica.**
- Engenharia pronta
- Caminho claro
- Decisões humanas aguardando aprovação

**Próxima hora:** decisões hoje (18/09) → lançamento Onda 1 amanhã (19/09) → Gate 1 em 16/10.

---

**Preparado por:** Sistema  
**Revisor:** Ricardo Esper  
**Versão:** 1.0 (17/09/2026, 09:00)  
**Próxima revisão:** 18/09/2026, após decisões
