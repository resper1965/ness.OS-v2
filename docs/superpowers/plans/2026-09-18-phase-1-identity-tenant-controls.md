# Phase 1 Identity and Tenant Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Comprovar autenticação, MFA, revogação, break-glass, papéis e isolamento de tenant em todas as rotas e sessões do escopo implantado.

**Architecture:** Authentik é o provedor de identidade; aplicações validam claims normalizadas no backend. O tenant efetivo vem da autorização do servidor. Psono mantém recuperação administrativa protegida. Sessões HTTP e SSE compartilham a mesma política de validade e revogação.

**Tech Stack:** Authentik/OIDC, FastAPI, PostgreSQL, React, Psono, pytest e Playwright ou navegador controlado.

**Spec:** `docs/architecture/ness-os-official-architecture.md`.

## Global Constraints

- Gate de produção: Fase 0 aprovada. Desenvolvimento e testes locais podem avançar; mudança de autenticação, identidade ou tenant em produção fica bloqueada até o gate passar.
- Nunca usar parâmetros enviados pelo cliente como autoridade de tenant.
- Executar mudanças de MFA com duas contas administrativas testadas e procedimento de recuperação disponível.

---

### Task 1: Formalizar a matriz de acesso

**Files:**
- Create: `docs/security/access-control-matrix.md`
- Modify: `app/backend/app/api/routers/auth.py`
- Modify: `app/backend/tests/test_authentik_rbac.py`

**Interfaces:** Papéis mínimos `admin`, `operator` e `viewer`; cada endpoint documenta ação, escopo de tenant e resposta esperada para acesso negado.

- [x] Extrair todas as rotas protegidas de `app/backend/app/api/routers` e registrar na matriz com método, papel e tenant.
- [x] Criar teste que falha se uma rota protegida não declarar dependência de autorização reconhecida.
- [x] Executar `python -m pytest app/backend/tests/test_authentik_rbac.py -q`; esperado: falha para lacunas reais.
- [x] Centralizar a normalização de claims e a decisão de papel/tenant em `auth.py`.
- [x] Repetir o teste; esperado: todas as rotas mapeadas e acessos negados com 401/403 coerente.
- [x] Commit: `git add docs/security/access-control-matrix.md app/backend/app/api/routers/auth.py app/backend/tests/test_authentik_rbac.py && git commit -m "feat(auth): formalize role and tenant policy"`.

### Task 2: Aplicar revogação a streams e sessões longas

**Files:**
- Modify: `app/backend/app/api/routers/auth.py`
- Modify: `app/backend/app/api/routers/incidents.py`
- Modify: `app/backend/app/core/dependencies.py`
- Modify: `app/backend/app/core/jwt.py`
- Modify: `app/backend/app/migrate.py`
- Modify: `app/backend/app/models/users.py`
- Modify: `app/backend/tests/test_browser_session_security.py`
- Modify: `app/backend/tests/test_incidents_auth.py`
- Modify: `app/backend/tests/test_oidc_session_lifecycle.py`

**Interfaces:** Logout incrementa `token_version` no banco e invalida imediatamente cópias de JWT. HTTP e SSE rejeitam versões antigas; o stream revalida expiração, estado, papel e tenant em intervalo limitado e encerra com evento de autenticação antes de desconectar.

- [x] Criar testes para expiração durante stream, revogação, troca de papel e mudança de tenant.
- [x] Executar os dois arquivos de teste; esperado: novos casos falham.
- [x] Implementar revalidação periódica usando a mesma política de `auth.py`, sem confiar no papel capturado na conexão inicial.
- [x] Repetir os testes; esperado: stream autorizado continua e cada alteração de segurança encerra o stream.
- [x] Commit: `git add app/backend/app/api/routers/auth.py app/backend/app/api/routers/incidents.py app/backend/app/core/dependencies.py app/backend/app/core/jwt.py app/backend/app/migrate.py app/backend/app/models/users.py app/backend/tests/test_browser_session_security.py app/backend/tests/test_incidents_auth.py app/backend/tests/test_oidc_session_lifecycle.py && git commit -m "feat(auth): revoke local sessions globally"` (`f4e88d6`).

### Task 3: Fechar MFA e recuperação no Psono e Authentik

**Files:**
- Modify: `infra/psono/scripts/f2-readiness-report.sh`
- Create: `infra/psono/scripts/mfa-readiness.sh` (testable fail-closed readiness rules)
- Modify: `infra/scripts/authentik-readiness-report.sh`
- Create: `infra/scripts/authentik_mfa_readiness.py` (read-only per-admin enrollment inventory)
- Test: `infra/tests/test-psono-tooling.sh`
- Test: `infra/tests/test-authentik-readiness.sh`
- Create: `docs/runbooks/identity-break-glass.md`

**Interfaces:** Readiness falha quando contas administrativas exigidas não têm MFA ou quando não existe mecanismo de recuperação testado; relatório exibe contagens, nunca códigos.

- [x] Criar casos de teste para administrador sem MFA, recovery codes ausentes e somente uma conta recuperável.
- [x] Executar os dois testes; esperado: falha inicial; casos implementados antes do check fail-closed.
- [x] Implementar os checks e repetir; esperado: aprovado com fixtures conformes.
- [ ] Habilitar MFA nas contas administrativas atuais, gerar recovery codes e armazená-los no cofre seguindo dupla custódia.
- [ ] Criar uma conta break-glass sem uso cotidiano, testar acesso e rotação e registrar apenas a evidência.
- [x] Documentar gatilho, autorização, auditoria e revogação do break-glass.
- [x] Commit: `git add infra/psono/scripts/f2-readiness-report.sh infra/psono/scripts/mfa-readiness.sh infra/scripts/authentik-readiness-report.sh infra/scripts/authentik_mfa_readiness.py infra/tests/test-psono-tooling.sh infra/tests/test-authentik-readiness.sh docs/runbooks/identity-break-glass.md && git commit -m "feat(identity): enforce MFA recovery readiness"`.

### Task 4: Executar UAT de identidade em todas as aplicações

**Files:**
- Modify: `infra/scripts/authentik-public-precheck.sh`
- Modify: `infra/scripts/hub-session-readiness.sh`
- Create: `docs/execution/evidence/phase-1-identity-uat.md`
- Test: `infra/tests/test-authentik-public-precheck.sh`
- Test: `infra/tests/test-hub-session-readiness.sh`

**Interfaces:** Matriz UAT cobre Hub, GLPI, n8n e Zabbix para login, logout, expiração, revogação, MFA, acesso direto e headers de identidade forjados.

- [x] Estender o probe local do Hub para verificar que logout invalida também uma cópia do bearer JWT; adicionar evidência UAT sem credenciais ou tokens.
- [x] Evitar expor senha UAT nos argumentos do processo `jq`; limpar variáveis após criar arquivo temporário restrito.
- [x] Testar o precheck público com `curl` simulado: fluxo anônimo esperado passa; resposta autenticada ao header forjado falha; nenhuma rede real é acessada.
- [x] Automatizar os checks sem armazenar cookies ou tokens na evidência; precheck público e teste estático do Hub passaram, com resultados registrados em `docs/execution/evidence/phase-1-identity-uat.md`.
- [ ] Executar contas `admin`, `operator` e `viewer` em dois tenants e uma conta desabilitada.
- [ ] Confirmar que headers forjados não alteram identidade e que acesso entre tenants retorna 403 ou coleção vazia conforme o contrato.
- [ ] Confirmar logout global, expiração e revogação em até o intervalo definido no runbook.
- [ ] Registrar cada célula da matriz como `PASS` ou `FAIL`.
- [ ] Commit: `git add infra/scripts/authentik-public-precheck.sh infra/scripts/hub-session-readiness.sh docs/execution/evidence/phase-1-identity-uat.md && git commit -m "test(identity): record cross application access UAT"`.

### Task 5: Validar identidades técnicas e n8n

**Files:**
- Modify: `infra/scripts/aiops-secret-consumer-report.sh`
- Modify: `infra/tests/test-secrets-plumbing.sh`
- Create: `docs/runbooks/service-identities-and-secret-rotation.md`
- Create: `docs/execution/evidence/phase-1-service-identities.md`

**Interfaces:** Cada integração possui identidade técnica própria, escopo mínimo, consumidor conhecido, data de rotação e teste de revogação; n8n não compartilha credencial administrativa humana.

- [x] Criar fixtures para segredo ausente, compartilhado entre serviços, vencido e presente em arquivo versionado.
- [x] Executar `bash infra/tests/test-secrets-plumbing.sh`; esperado: novos casos falham.
- [x] Estender o relatório para mapear consumidor, origem segura, escopo e idade sem revelar valores.
- [x] Repetir o teste; esperado: aprovado.
- [ ] Inventariar identidades de Zabbix, GLPI, Authentik, Psono, n8n, Contabo e Object Storage.
- [ ] Rotacionar uma credencial técnica não crítica, validar o consumidor e comprovar que a credencial anterior deixou de funcionar.
- [ ] Validar no n8n que editor, executor e webhook respeitam SSO/RBAC e que workflows não expõem credenciais em exportações ou logs.
- [ ] Commit: `git add infra/scripts/aiops-secret-consumer-report.sh infra/tests/test-secrets-plumbing.sh docs/runbooks/service-identities-and-secret-rotation.md docs/execution/evidence/phase-1-service-identities.md && git commit -m "feat(identity): audit service identities and secret rotation"`.

### Task 6: Aprovar o gate da Fase 1

**Files:**
- Create: `docs/execution/gates/phase-1-identity-tenants.md`

- [ ] Confirmar 100% das rotas protegidas na matriz.
- [ ] Confirmar MFA e recuperação para todas as contas administrativas exigidas.
- [ ] Confirmar revogação em HTTP e SSE.
- [ ] Confirmar zero vazamento entre tenants nos testes positivos e negativos.
- [ ] Confirmar identidades técnicas exclusivas, n8n protegido e rotação ensaiada.
- [ ] Executar `python -m pytest app/backend/tests/test_authentik_rbac.py app/backend/tests/test_incidents_auth.py app/backend/tests/test_oidc_session_lifecycle.py -q` e os testes shell desta fase; esperado: todos aprovados.
- [ ] Registrar o gate e commit: `git add docs/execution/gates/phase-1-identity-tenants.md && git commit -m "docs(gate): approve identity and tenant controls"`.
