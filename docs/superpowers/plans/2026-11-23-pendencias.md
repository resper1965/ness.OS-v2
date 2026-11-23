# Pendências de 23/11 — plano de execução

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Passos com `- [ ]`.

**Goal:** fechar o que não depende de terceiros: página de Vulnerabilidades no Hub, carga e envio mensal, andamento da virada.

**Architecture:** o stack orquestra (cron do `agente`): roda `vuln-mensal.py` nos dois Wazuh via SSH, traz `hub.csv` e carrega no Postgres do Hub com `\copy` (sem endpoint de ingestão). O Hub lê a tabela, filtra por cliente (`resolve_tenant_scope`) e exporta xlsx no layout do Cássio. O e-mail mensal sai do contêiner da API (`ResendEmailClient`), disparado pelo mesmo cron.

**Tech Stack:** FastAPI + SQLAlchemy async, Postgres, React 19, stdlib (zipfile) para o xlsx.

**Spec:** resumo da sessão (Decisions → Página de Vulnerabilidades).

## Global Constraints
- Cliente vê só o próprio (`resolve_tenant_scope`); NOC vê tudo.
- UI sem nome de fornecedor; DS 2.0.1; `ness.OS`.
- xlsx: 35 colunas na ordem de `BRUTO`, severidade "1 - Crítica".
- Windows sem suporte = 1 achado crítico `SO-SEM-SUPORTE` por máquina.
- Produção só com frase do Esper; entrega por PR.

## Review Focus
1. Cliente pedindo `customer_id` de outro → 403 (teste).
2. Carga parcial (um Wazuh fora) não pode apagar o outro cliente: a troca é por cliente, em transação.
3. Filtro com caractere de LIKE (`%`, `_`) não vira curinga: busca por igualdade/prefixo com escape.
4. Export grande (≈110 mil linhas) não estoura memória: escrita em arquivo temporário, streaming.
5. Tabela vazia → página com estado vazio, não erro.

---

### Task 1: tabela + carga
**Files:** `app/backend/app/migrate.py` (bloco `VULN_SQL`), `app/backend/sql/001_schema.sql` (`vuln:begin/end`), `out/vuln-mensal.py` (gera `hub.csv`), `infra/scripts/vuln-carga.sh`.
- [ ] Tabela `n_secops_vulnerabilities(customer_id, agent, os, package, version, cve, severity, cvss, eol, detected_at, raw jsonb, loaded_at)`; índices por `(customer_id, severity)`.
- [ ] Paridade migrate × 001 no `test_bootstrap_sql.py`.
- [ ] `vuln-carga.sh`: por servidor, extrai, copia, e numa transação `DELETE WHERE customer_id IN (<clientes do arquivo>)` + `\copy`.

### Task 2: API
**Files:** `app/backend/app/api/routers/vulns.py`, `app/backend/app/main.py`, `app/backend/tests/test_vulns_api.py`.
- [ ] `GET /api/secops/vulnerabilities` (filtros, página de 100, totais por severidade, top 10 máquinas e pacotes).
- [ ] `GET /api/secops/vulnerabilities/export` → xlsx streaming.
- [ ] Teste: escopo do cliente, filtro, export abre como zip com 35 colunas.

### Task 3: tela
**Files:** `app/frontend/src/components/VulnsView.tsx`, `App.tsx`, `app-nav.test.ts`.
- [ ] View `vulns` ("Vulnerabilidades"), visível a operador; filtros, KPIs, tops, tabela, botão exportar.

### Task 4: envio mensal
**Files:** `app/backend/app/services/vuln_report.py`; cron no stack (`0 6 1 * *`).
- [ ] Resumo por cliente × severidade + link para a exportação; destino `ccarvalho@ness.com.br`. Anexo não: o xlsx da RZK tem 36 MB.

### Fora deste plano (dependem de terceiros ou de frase)
- Integração Wazuh → Hub nos servidores novos (nenhum alerta chega desde a virada): decidir o canal e ligar depois da virada.
- Topologia (Ismael), SecOps (destinatário), Hostinger `agent.conf`, promoção do PR.
