# Local CI Trust Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir os quatro checks Actions obrigatórios por resultados de CI local vinculados ao SHA do PR, sem permitir que código de PR forje sucesso ou leia a chave da GitHub App.

**Architecture:** Um builder confiável instala fora do checkout o launcher já candidato no PR #81 e executa código de PR somente em contêineres sem rede, socket ou chave. Um signer em outro domínio de segurança inicia a execução por canal autenticado, verifica resultado e `head.sha` remoto antes/depois, e só então usa a GitHub App para emitir checks. O builder e seu administrador são parte explícita da base de confiança; JSON enviado pelo PR não é evidência.

**Tech Stack:** Python 3.12, Docker/Buildx, Gitleaks, GitHub App Checks/Pulls API, `httpx` já usado no backend, pytest; usar dependência de assinatura JWT somente se a implementação escolhida realmente precisar dela.

**Spec:** [handoff de desenvolvimento](../../execution/developer-handoff-2026-10-22.md), [plano master](2026-10-12-ness-os-plano-master.md) e `infra/docs/github-app-local-ci.md` **na branch do PR #81**. O ADR/contrato deste plano é a fronteira de confiança descrita em Architecture; não presumir host de signer já aprovado.

## Global Constraints

- Repositório `resper1965/ness.OS-v2` privado; Actions desativado após a janela temporária. Não tornar público como rotina de CI.
- Nomes exigidos: `build-and-test`, `test-and-lint`, `lint`, `gitleaks`; hoje `app_id=15368`, `strict=true`, zero aprovações obrigatórias, administradores cobertos, force-push desligado.
- App `ness-os-local-ci` ID 5307771, instalação 171160625; chave nova fora do Git; primeira chave ainda ativa e precisa de revogação antes da ativação.
- Nenhum check, alteração da proteção, merge ou deploy por prova parcial; manter PRs #64/#81 draft até gates próprios.
- Não confiar em runner, política de scan ou evidência fornecidos pelo checkout do PR. Não imprimir segredo, token, payload sensível ou stdout de scanner potencialmente sensível.
- A distro WSL atual não serve como fronteira entre builder e signer: `nobody` obteve root via `wsl.exe -u root`. Não instalar signer co-localizado nela apenas mudando UID ou usando Docker rootless.
- Provisionamento/custo de host adicional exige aprovação específica; sem host isolado disponível, registrar `BLOCKED` e seguir tarefas GLPI independentes.

## Review Focus

1. PR recebe novo commit durante a execução: Task 3 testa que o segundo `head.sha` diverge e nenhum sucesso é emitido.
2. PR de fork ou base diferente de `main`: Task 3 reutiliza e amplia negativos de `verify_pr_head`.
3. Um dos quatro passos falta, falha ou retorna stderr apesar de exit 0: Task 2 testa que a execução não produz evidência de sucesso.
4. PR muda launcher, `.gitleaksignore` ou `.gitleaks.toml`: Task 2 testa que a cópia/política controladas prevalecem ou a execução falha fechada.
5. Builder tenta acessar a identidade do signer: Task 1 prova negativa com arquivo sentinela não secreto e rota/credencial inexistentes para o builder, sem ler a chave real.

---

## File map

- PR #81 `infra/scripts/local-ci-backend-sandbox.py`: launcher existente; manter isolamento e saída fail-closed.
- PR #81 `infra/scripts/local_ci_check_gate.py`: `verify_pr_head(pr: dict, number: int, repo: str, sha: str) -> None` existente; ampliar o gate sem mudar sua semântica.
- PR #81 `infra/scripts/local_ci_check_gate.py`: produzir também `verify_run_evidence(evidence: dict, sha: str) -> None`, exigindo exatamente os quatro nomes e `schema=1`, `sha` igual e cada `exit_code=0`; ausência/campo extra/falha rejeita.
- PR #81 `infra/scripts/local_ci_emitter.py`: criar somente após Task 1; orquestra leitura do PR, invocação do runner confiável e emissão dos quatro checks.
- PR #81 `infra/tests/test_local_ci_backend_sandbox.py`, `infra/tests/test_local_ci_check_gate.py`: ampliar negativos do runner e do vínculo ao PR.
- PR #81 `infra/tests/test_local_ci_emitter.py`: criar com transporte/runner falsos, sem rede, chave ou GitHub real.
- PR #81 `infra/docs/github-app-local-ci.md`: atualizar instalação, operação, retorno e resultados; não guardar caminho de segredo público além da classe de permissão.
- `docs/execution/ness-os-status.md`: atualizar apenas quando o gate/bloqueio realmente mudar.

### Task 1: Provar o domínio do signer antes de conectar a App

**Files:** Modify: `infra/docs/github-app-local-ci.md` (PR #81). Create: `docs/execution/local-ci-isolation-evidence.md` (PR #81, sem segredos).

**Interfaces:** Consumes: launcher root-owned candidato e contrato da App existentes. Produces: identidade de host/owner e canal autenticado signer→builder com comando fixo, host key pinada e nenhuma capacidade builder→signer; estes são pré-requisitos da Task 3.

- [ ] **Step 1: Registrar a topologia candidata.** Escolher host ou domínio do signer sem Docker/socket e fora da distro WSL escalável; registrar owner, caminho de retorno e aprovação de custo se houver. Se indisponível, registrar `BLOCKED` e parar este plano sem improvisar permissão.
- [ ] **Step 2: Ensaiar uma sentinela não secreta.** Instalar sentinela no domínio do signer com a mesma classe de permissão da chave; verificar que o processo do builder não a lê nem obtém shell/UID privilegiado no signer. Não tocar o PEM real no teste negativo.
- [ ] **Step 3: Verificar grants da App.** Solicitar somente `Pull requests: Read-only`, aceitar atualização da instalação e conferir readback; confirmar Checks write/Contents read e instalação limitada ao repo. Verificar a revogação da primeira chave; se não for possível, manter `BLOCKED`.
- [ ] **Step 4: Registrar resultado/retorno.** Evidência sanitizada inclui comandos, exit codes, identidade de host, permissões e readback, sem token/PEM/IP privado desnecessário. Revisar e commitar somente essa prova.

### Task 2: Fechar o contrato do runner confiável

**Files:** Modify: `infra/scripts/local-ci-backend-sandbox.py`, `infra/tests/test_local_ci_backend_sandbox.py`, `infra/docs/github-app-local-ci.md` (PR #81).

**Interfaces:** Consumes: SHA40 do PR e IDs imutáveis das imagens locais, política de scan root-owned fora do checkout. Produces: `{"schema":1,"sha":"<sha40>","checks":{"build-and-test":{"exit_code":0},"test-and-lint":{"exit_code":0},"lint":{"exit_code":0},"gitleaks":{"exit_code":0}}}` somente após todos os comandos terminarem. A Task 3 obtém esse resultado exclusivamente da execução remota que ela iniciou; nunca de arquivo enviado pelo PR.

- [ ] **Step 1: Escrever testes RED.** Em `test_local_ci_backend_sandbox.py`, cobrir SHA divergente, árvore suja, symlink para fora, ausência de uma etapa, exit não zero, stderr do scan com exit zero e tentativa de política de scan no PR. Cada caso exige exit não zero ou zero evidência de quatro sucessos. Em `test_local_ci_check_gate.py`, `test_evidence_requires_exact_sha_and_four_successes` aceita somente o schema acima; variantes com chave ausente/extra, SHA errado ou `exit_code != 0` levantam `ValueError`.
- [ ] **Step 2: Rodar `python -m pytest -q infra/tests/test_local_ci_backend_sandbox.py`.** Esperado: novos negativos falham pela lacuna concreta, não por import/dependência.
- [ ] **Step 3: Implementar o mínimo no launcher instalado fora do checkout.** As quatro etapas obrigatórias são backend/build, frontend/test-and-lint, qualidade Python/lint e Gitleaks; usar apenas imagens por ID, política externa e código fonte limitado ao necessário. Instalar cópia revisada root-owned no builder e comparar hash antes da execução.
- [ ] **Step 4: Reexecutar testes e ensaio descartável no SHA exato.** Esperado: suíte focada PASS; execução real completa PASS sem rede/socket/chave dentro dos contêineres; injetar uma falha e confirmar que não há quatro sucessos. Não repetir backup/restore ou publicação de imagens sem mudança relacionada.
- [ ] **Step 5: Commit.** Stage explícito dos três arquivos do PR #81; registrar SHA, IDs das imagens e resultado sanitizado no runbook.

### Task 3: Emitir somente para o head remoto comprovado

**Files:** Create: `infra/scripts/local_ci_emitter.py`, `infra/tests/test_local_ci_emitter.py` (PR #81). Modify: `infra/scripts/local_ci_check_gate.py`, `infra/tests/test_local_ci_check_gate.py`, `infra/docs/github-app-local-ci.md` (PR #81).

**Interfaces:** Consumes: `verify_pr_head(pr: dict, number: int, repo: str, sha: str) -> None`, `verify_run_evidence(evidence: dict, sha: str) -> None` e resultado da Task 2 obtido pelo canal autenticado da Task 1. Produces: `run_emitter(pr_number: int, sha: str, github: GitHubClient, runner: TrustedRunner) -> None`. `GitHubClient` provê `get_pr(number: int) -> dict`, `create_check_run(name: str, sha: str) -> int` e `finish_check_run(run_id: int, conclusion: str) -> None`; `TrustedRunner.run(sha: str) -> dict` executa comando fixo no builder e retorna o schema da Task 2, nunca entrada do PR. Os quatro runs começam `in_progress` antes da execução; falha/crash os mantém não verdes ou os conclui como `failure`/`cancelled`. Não reutilizar verde antigo do mesmo SHA.

- [ ] **Step 1: Escrever testes RED com cliente/runner falsos.** `test_exact_head_and_complete_runner_finish_four_successes` exige quatro nomes e SHA idênticos. `test_head_moves_before_finish_cancels_old_runs`, `test_missing_check_never_succeeds`, `test_transport_failure_leaves_no_green`, `test_fork_or_wrong_base_stops_before_runner` e `test_second_run_cannot_reuse_old_green` exigem zero sucessos novos; PR não fornece evidência como parâmetro do emissor.
- [ ] **Step 2: Rodar `python -m pytest -q infra/tests/test_local_ci_check_gate.py infra/tests/test_local_ci_emitter.py`.** Esperado: testes novos falham pelo módulo/fluxo ausente.
- [ ] **Step 3: Implementar emissor fora do checkout submetido.** Obter token de instalação efêmero por mecanismo da App, consultar `GET /pulls/{number}`, validar com `verify_pr_head`, criar quatro runs `in_progress` no SHA, invocar runner confiável, validar schema e consultar o PR novamente antes de concluí-los. Concluir `success` somente se as quatro provas e o head ainda coincidirem; nas exceções, concluir runs existentes como `failure`/`cancelled` quando possível, sem fallback para verde. Não aceitar resultados entregues por arquivo/endpoint do PR; logs só registram IDs, SHA e estados sanitizados.
- [ ] **Step 4: Rodar suíte focada e negativos ponta a ponta.** Esperado: PASS local sem rede/chave; no ambiente isolado, provar que SHA divergente, check ausente e runner falho não produzem sucesso; confirmar readback dos check runs apenas após todos os gates e revogação da chave anterior.
- [ ] **Step 5: Commit e registrar retorno.** Descrever como desativar o emissor/reverter a origem dos checks sem apagar histórico de resultados. Nenhum merge ou deploy por esta task.

### Task 4: Trocar a origem dos checks somente após aceite separado

**Files:** Modify: `infra/docs/github-app-local-ci.md` (PR #81), `docs/execution/ness-os-status.md` (branch de entrega).

**Interfaces:** Consumes: provas das Tasks 1–3, quatro check runs reais no SHA testado e proteção atual lida imediatamente antes. Produces: proteção da `main` com mesmos quatro contextos e `app_id=5307771`, ou estado anterior restaurado se readback/rollback falhar.

- [ ] **Step 1: Obter GO explícito para mudar a proteção.** Confirmar que App antiga não é mais a fonte executável desejada, que #81 está revisável e que o rollback documentado é aplicável.
- [ ] **Step 2: Capturar proteção anterior e testar rollback em configuração descartável quando possível.** Conferir strict=true, zero aprovações, admin=true e force-push=false, sem alterar esses campos.
- [ ] **Step 3: Alterar somente os quatro `app_id` exigidos e ler de volta.** Esperado: nomes idênticos, app nova vinculada, demais proteções iguais; se falhar, restaurar configuração capturada e verificar novamente.
- [ ] **Step 4: Provar PR com commit novo e falha deliberada.** Novo SHA deve exigir novos checks; falha não pode virar verde. Registrar evidência e atualizar indicador/ledger; só então avaliar retirada de draft/merge por revisão técnica normal, nunca deploy automático.

**Handoff:** implementar este plano na branch do PR #81. Tarefas 2–4 não começam como gate enquanto Task 1 estiver BLOCKED. O plano não concede autorização de compra, mudança de proteção, merge ou deploy por si só.
