# ness.OS — plano de execução completo (F0–F8, recursos, IaC e documentação)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** levar o ness.OS do estado de 26/10/2026 ao aceite global de produção
do plano master, incluindo contratação, instalação e configuração das VPS
necessárias, todas descritas como código (Terraform + Ansible) e documentadas.

**Architecture:** o master define o escopo; este plano define a ordem, quem
executa e como cada recurso nasce. Toda VPS existe primeiro como código
(`infra/terraform`, `infra/ansible`), é testada em contêiner local, só então é
contratada (decisão do Ricardo) e aplicada; cada entrega atualiza as-built,
runbook e indicador. O trilho Zabbix → incidente → ticket vem antes das
frentes que dependem dele; frentes independentes correm em paralelo.

**Tech Stack:** FastAPI/SQLAlchemy/Celery (Py 3.12), React 19/Vite 8, Docker
Compose, Caddy, GLPI, Zabbix 7.0, Authentik, Psono, Restic + Contabo Object
Storage, Terraform (provider `contabo/contabo`), Ansible, Wazuh 4.14.x.

**Spec:** [plano master](2026-10-12-ness-os-plano-master.md) (escopo, decisões
de produto, gates). Detalhe por produto nos planos que ele indexa — este plano
**referencia** essas tarefas, não as reescreve. Estado factual:
[indicador](../../execution/ness-os-status.md) e
[handoff](../../execution/developer-handoff-2026-10-22.md).

## Global Constraints

- Escopo é o master inteiro (F0–F8); sem prazo comercial (Ricardo, 26/10).
- Implantação em VPS nova exige contratação aprovada pelo Ricardo; a API
  Contabo segue **somente leitura** até a aprovação de cada compra (master §1).
- Wazuh: recursos ainda indisponíveis; F7 avança só até lab e IaC testada.
- Nenhum recurso nasce fora de código: instância em `infra/terraform`,
  configuração em `infra/ansible`, documentação em `infra/docs/`.
- `terraform apply` só com `plan` revisado; instância existente tem
  `prevent_destroy = true`; plano com `destroy`/`replace` em produção aborta.
- Mutação de produção: identidade autorizada, janela, GO, estado anterior e
  rollback (master §3.6). Janela Zabbix vigente: nenhuma (expirou 15/10).
- Conta GLPI 106 permanece desativada até T03 aprovado.
- Segredo nunca em arquivo versionado, log ou mensagem; IaC lê de variável de
  ambiente (`TF_VAR_*`, `CONTABO_*`) ou de arquivo SOPS após Task 4.4.
- Host de operação: `stack` (`/srv/dev/projetos`), usuário `agente`, sem sudo,
  Docker rootless. Ferramentas ausentes (terraform, ansible, node) rodam por
  imagem Docker fixada ou venv local — nunca instalação no sistema.
- Docker publica porta só em `127.0.0.1`; labs usam dado sintético.
- Commits em português, conventional; uma branch por frente; PR, nunca push em
  `main`. Estados de tarefa: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`,
  `VERIFIED`, `RELEASED` (master §3.10).
- Toda tarefa que muda infraestrutura termina atualizando
  `infra/docs/as-built-vps.md` e o runbook do serviço.

## Review Focus

1. **Role `common` sobrescrevendo `sshd_config`** em host que usa drop-ins
   (`00-ness-nominal-access.conf`, `99-ness-gate0.conf`) → perda de acesso.
   Esperado: a role só escreve drop-in próprio. Teste na Task 1.2.
2. **`authorized_keys` sem quebra de linha final** concatena chave nova na
   anterior (incidente de 26/10 na AIOps). Esperado: módulo
   `ansible.posix.authorized_key`, nunca `echo >>`. Teste na Task 1.2.
3. **Drift em instância importada** (`image_id`/`product_id` divergente) faz o
   Terraform propor substituição de VPS produtiva. Esperado: guarda recusa.
   Teste na Task 1.1.
4. **Timeout do GLPI após criar o ticket** + replay → ticket duplicado.
   Esperado: um evento, um ticket. Teste na Task 2.4.
5. **Path encoding e IDs aninhados no gateway GLPI** (`%2F`, `entities_id=all`,
   ID de outra entidade em sub-recurso). Esperado: negação. Teste na Task 2.1.

**Rótulos:** `[A]` agente executa sozinho · `[R]` espera decisão/ação do
Ricardo (ou pessoa nomeada) · `[$ Rn]` espera contratação do recurso Rn.

---

## A. Decisões do Ricardo (ordenadas pelo que destravam)

| # | Decisão | Destrava | Recomendação |
|---|---|---|---|
| D1 | Forma da CI confiável — **decidido 26/10: A (Actions com limite)** | G0 → toda promoção | **Reativar Actions com limite de gasto** (issue #67). Custo mensal pequeno, elimina o projeto de signer e a VPS dele. Alternativa: VPS de signer (R1) + plano 2026-10-22 |
| D2 | Janela + GO para gateway GLPI e migração T04 na AIOps | T03, T04, F3, F5 | Janela 22:00–00:00 BRT após Task 2.2 |
| D3 | Contratar VPS Psono (R2), issue #48 | F1 cofre | Contratar após Task 4.3 passar no lab |
| D4 | MFA nominal (#66), dois recipients age (#45), recovery (#43/#44) | G2, SOPS | Pessoas: Ricardo, Ismael, Rogerio |
| D5 | Nova janela Zabbix, issue #73 (proxy/UUID), GO de corte | F2/Z-M5 | Depois de unsupported <0,5% em UAT |
| D6 | Topologia e compra Wazuh (R3) | F7 | **Single-node primeiro** (ver Task 9.1); cluster só com demanda medida |
| D7 | Credenciais RMM, canais (WhatsApp/e-mail/push), consentimento Workspace | F6/F7 partes | Quando a frente chegar; não antes |
| D8 | Reuso da VPS Zabbix antiga (`144.91.72.202`) após D+14 do corte | reduz R3 em 1 VPS | Reimagem como nó Wazuh |

## B. Recursos a contratar

Preço e `product_id` conferidos no painel/API na data da compra; não fixados
aqui. Cada recurso entra primeiro como entrada no mapa `instances` do Terraform.

| ID | Recurso | Classe Contabo de referência | Para | Contratar quando |
|---|---|---|---|---|
| R1 | Signer de CI (só se D1 = signer) | Cloud VPS 10 | domínio isolado do signer | D1 |
| R2 | Psono dedicado | Cloud VPS 10 | cofre de produção | Task 4.3 VERIFIED em lab |
| R3a | Wazuh single-node | Cloud VPS 40 (12 vCPU, 48 GB) | piloto + migração dos 624 endpoints | Task 9.2 VERIFIED em lab + D6 |
| R3b | Wazuh cluster (onda 1 do plano de capacidade) | 3× VPS 30, 1× VPS 20, 2× VPS 30, 1× VPS 10 | > ~1.000 endpoints ou exigência de HA | métrica de R3a + D6 |
| R4 | Rede privada Contabo entre nós Wazuh/AIOps | add-on | portas 1516/9200/9300/55000 fora da Internet | junto de R3 |
| — | Zabbix definitivo | **nenhuma**: destino já contratado (`169.58.234.9`) | F2 | — |
| — | Node-RED, gateway GLPI | **nenhuma**: contêineres na AIOps | F3/F6 | — |

## C. Estrutura de arquivos de IaC e documentação

| Caminho | Responsabilidade |
|---|---|
| `infra/terraform/versions.tf` | backend S3 no Object Storage Contabo (`tfstate/ness-os`) |
| `infra/terraform/main.tf` | `contabo_instance.vps` com `for_each = var.instances`; object storage |
| `infra/terraform/variables.tf` | `instances: map(object({display_name, product_id, image_id, region}))` |
| `infra/terraform/environments/prod.tfvars` | só valores não secretos; um item por VPS |
| `infra/terraform/imports.tf` | blocos `import {}` das instâncias existentes |
| `infra/scripts/tf-plan-guard.sh` | falha se o plano contém destroy/replace de recurso protegido |
| `infra/bin/tf`, `infra/bin/ansible` | executam Terraform/Ansible por imagem/venv fixados |
| `infra/ansible/inventory/hosts.yml` | grupos `zabbix_prod`, `zabbix_uat`, `aiops`, `psono`, `wazuh`, `ci_signer` |
| `infra/ansible/roles/common` | baseline: usuário, chave, drop-in sshd, UFW, fail2ban, agente Zabbix |
| `infra/ansible/roles/{psono,wazuh,ci_signer}` | um papel por serviço novo |
| `infra/ansible/tests/` | testes de role em contêiner `debian:12` |
| `infra/scripts/as-built-collect.sh` | coleta read-only por SSH → markdown sanitizado |
| `infra/docs/as-built-vps.md` | estado real por host |
| `infra/docs/iac.md` | como planejar/aplicar/importar/destruir com segurança |
| `infra/docs/runbooks/<serviço>.md` | owner, dependências, SLO, backup/RPO/RTO, retorno, escalonamento |

---

## Frente 0 — base de trabalho

### Task 0.1: Reconciliar estado e documentos `[A]`

**Files:**
- Modify: `docs/execution/ness-os-status.md`, `docs/execution/gates/phase-0-recovery-release.md`, `docs/execution/gate-0-status.md`, `docs/PROJECT_CONTEXT.md`, `docs/adr/0020-glpi-maintenance-entity-boundary.md` (links de issue)
- Create: `STATE.md`, `docs/execution/evidence/state-reconciliation-2026-10-26.md`
- Bring: `infra/docs/agent-access-runbook.md`, `docs/execution/evidence/{uat-recon,rescue-access}-2026-10-26.md` do checkout antigo (`git cherry-pick aaf6e07 11f8b06`, resolver conflitos)

- [ ] **Step 1:** Ler heads reais de PR #64/#81, issues abertas e digests em execução (`ssh ness_admin@144.91.115.242 'sudo docker ps --format {{.Image}}'`). Registrar na evidência.
- [ ] **Step 2:** Corrigir as contradições: PR #65 integrado; janela Zabbix 15/10; SHA vigente do #81; links `n-infraops` → `ness.OS-v2`; caminhos `/home/resper/...` marcados como de outro host; `148.230.77.242` aparece nos docs como KVM8 devolvida (09/02) e é hoje o IP da `stack` — Ricardo confirma a titularidade e o registro de retirada é corrigido.
- [ ] **Step 3:** Criar `STATE.md` (Tipo app, Estágio em andamento, Próximo passo = D1).
- [ ] **Step 4:** Verificar: `grep -rn 'n-infraops/issues' docs | wc -l` → `0`.
- [ ] **Step 5:** Commit `docs: reconciliar estado do ness.OS em 26/10`.

### Task 0.2: Higiene da raiz `[A]` + revisão `[R]`

**Files:** raiz (`get_users.py`, `run_provision_*.py`, `check_glpi_sso.py`, imagens JPEG, `ux_output.md`, `wazuh-secops-plan.md`, `cavan-compras/`), `cli/contabo/` (duplicado de `app/cli/contabo/`)

- [ ] **Step 1:** Para cada arquivo, `git log --oneline -1 -- <arq>` e `grep -rn <nome>` para achar referências; tabela no PR com destino (remover, mover para `infra/scripts/legacy/`, manter).
- [ ] **Step 2:** Imagens e material de cliente saem do Git (regra global); listar para o Ricardo decidir onde guardar fora do repositório.
- [x] **Step 3:** Manter `app/cli/contabo/` (entra na imagem, lê `CONTABO_*`), portar `commands/` e remover `cli/contabo/` da raiz — #105.
- [ ] **Step 4:** `pytest app/backend -q` e `pytest infra/tests -q` sem regressão.
- [ ] **Step 5:** PR `chore: limpar raiz do repositório`; merge só após revisão do Ricardo.

### Task 0.3: CI confiável — D1 `[R]` → `[A]` — **VERIFIED 26/10**: Actions religado; #81 → `76b90cc`, #64 → `42db505` na `main`, checks verdes

**Path A (recomendado):** Ricardo reativa Actions com limite de gasto.
- [ ] **Step A1:** Rodar os quatro checks exigidos pela proteção (`build-and-test`, `test-and-lint`, `lint`, `gitleaks`) no head do #81 e do #64.
- [ ] **Step A2:** Corrigir falhas reais (incluindo `pywebpush` na instalação reproduzível, master F0).
- [ ] **Step A3:** Merge do #81 e depois do #64 na `main` com checks verdes; registrar SHAs no indicador.

**Path B:** contratar R1 e executar [plano de CI local](2026-10-22-local-ci-trust-boundary.md) Tasks 1–4; o signer nasce como entrada `ci_signer` em `instances` e role `ci_signer` (Frente 1).

**Aceite:** `main` contém #64 e #81 com os quatro checks verdes no SHA final.

### Task 0.4: Ferramental de IaC sem instalação no sistema `[A]`

**Files:**
- Create: `infra/bin/tf`, `infra/bin/ansible`, `infra/requirements-iac.txt`, `infra/docs/iac.md`

**Interfaces:**
- Produces: `infra/bin/tf <args>` = `docker run --rm -v "$PWD/infra/terraform:/w" -w /w -e TF_VAR_* -e AWS_* hashicorp/terraform:1.9.8 <args>`; `infra/bin/ansible <cmd> <args>` executa `<cmd>` (`ansible-playbook`, `ansible-lint`, `ansible-inventory`) de `infra/.venv` criado a partir de `requirements-iac.txt` (`ansible-core==2.17.*`, `ansible-lint==24.*`, coleção `ansible.posix`).

- [ ] **Step 1:** Criar os dois scripts e `infra/.venv` no `.gitignore`.
- [ ] **Step 2:** `infra/bin/tf validate` → `Success!`; `infra/bin/ansible ansible-playbook --syntax-check infra/ansible/playbooks/site.yml` → sem erro.
- [ ] **Step 3:** Documentar em `infra/docs/iac.md`: variáveis exigidas (sem valores), ordem plan → guard → apply, import e destruição.
- [ ] **Step 4:** Commit `chore(infra): ferramental IaC reproduzivel`.

---

## Frente 1 — IaC das VPS existentes

### Task 1.1: Terraform reflete as três VPS reais `[A]`

**Files:**
- Modify: `infra/terraform/{main,variables,versions,outputs}.tf`, `infra/terraform/environments/prod.tfvars`
- Create: `infra/terraform/imports.tf`, `infra/scripts/tf-plan-guard.sh`, `infra/tests/test_tf_plan_guard.py`

**Interfaces:**
- Consumes: `infra/bin/tf` (Task 0.4).
- Produces: `var.instances` com chaves `zabbix_prod` (`vmi3409070`), `aiops` (`vmi3409271`), `zabbix_uat` (`vmi3532557`); `contabo_instance.vps[<chave>]`; `tf-plan-guard.sh <plan.json>` sai `1` se algum `resource_changes[].change.actions` contém `delete`.

- [x] **Step 1: Teste do guard.**

```python
def test_guard_rejects_replace(tmp_path):
    plan = {"resource_changes": [{"address": 'contabo_instance.vps["aiops"]',
            "change": {"actions": ["delete", "create"]}}]}
    assert run_guard(tmp_path, plan).returncode == 1

def test_guard_accepts_noop(tmp_path):
    plan = {"resource_changes": [{"address": 'contabo_instance.vps["aiops"]',
            "change": {"actions": ["no-op"]}}]}
    assert run_guard(tmp_path, plan).returncode == 0
```

- [x] **Step 2:** `pytest infra/tests/test_tf_plan_guard.py -v` → FAIL (script ausente).
- [x] **Step 3:** Implementar o guard com `jq`/Python stdlib; trocar os três recursos fixos por `for_each`; `lifecycle { prevent_destroy = true; ignore_changes = [image_id, ssh_keys, default_user] }`; backend S3 no Object Storage existente.
- [x] **Step 4:** `infra/bin/tf init && infra/bin/tf plan -out p && infra/bin/tf show -json p > p.json && infra/scripts/tf-plan-guard.sh p.json` → exit `0` e plano só com `import`, zero `change`. Ajustar valores até o diff ficar vazio; **não** aplicar diff de atributo.
- [x] **Step 5:** `infra/bin/tf apply p` (grava só o estado importado). `infra/bin/tf plan -detailed-exitcode` → exit `0`.
- [x] **Step 6:** Commit `feat(infra): terraform importa as VPS existentes`.
- Concluída em 27/10: estado em `s3://ness-os-tfstate/prod/terraform.tfstate` (privado, versionado); `apply` = 4 imported, 0 changed; `plan -detailed-exitcode` → 0.

### Task 1.2: Ansible com inventário real e baseline seguro `[A]`

**Files:**
- Modify: `infra/ansible/inventory/hosts.yml`, `infra/ansible/inventory/group_vars/all.yml`, `infra/ansible/roles/common/tasks/main.yml`, `infra/ansible/roles/common/templates/sshd_config.j2` → renomear para `sshd-ness.conf.j2`
- Create: `infra/ansible/tests/test_common_role.sh`

**Interfaces:**
- Produces: grupos do inventário (seção C); chave via `ansible_ssh_private_key_file: "{{ lookup('env','NESS_AGENT_KEY') }}"`; role `common` escreve somente `/etc/ssh/sshd_config.d/50-ness-baseline.conf` e usa `ansible.posix.authorized_key` (`exclusive: false`).

- [ ] **Step 1: Teste em contêiner** (`debian:12`, conexão `docker`): prepara `authorized_keys` **sem `\n` final** com uma chave e um drop-in `99-ness-gate0.conf`; roda a role; afirma que `authorized_keys` tem 2 linhas, o drop-in original continua intacto e `sshd -t` passa.
- [ ] **Step 2:** `bash infra/ansible/tests/test_common_role.sh` → FAIL na role atual.
- [ ] **Step 3:** Corrigir a role (drop-in, módulo de chave, porta por host: `2222` em `zabbix_prod`).
- [ ] **Step 4:** Teste → PASS. `infra/bin/ansible ansible-lint infra/ansible` → sem erro.
- [x] **Step 5:** `ansible-playbook -i inventory/hosts.yml playbooks/common.yml --check --diff` nos três hosts: diff vazio ou cada diferença explicada na evidência. **Não aplicar** em produção nesta task.
  Feito em 27/10: [evidência](../../execution/evidence/ansible-common-check-2026-10-27.md) — diffs restantes bloqueiam `apply`.
- [ ] **Step 6:** Commit `fix(ansible): baseline preserva drop-ins e chaves existentes`.

### Task 1.3: As-built gerado `[A]`

**Files:**
- Create: `infra/scripts/as-built-collect.sh`
- Modify: `infra/docs/as-built-vps.md`

**Interfaces:**
- Produces: `as-built-collect.sh <host> [porta]` → markdown com SO/kernel, disco, serviços (`systemctl is-active/is-enabled`), portas em escuta, timers de backup, contêineres e imagens; sem IP privado, token ou variável de ambiente.

- [x] **Step 1:** Escrever o script só com comandos de leitura; `shellcheck` limpo.
- [x] **Step 2:** Rodar nos três hosts; `grep -iE 'password|token|secret' saída` → vazio.
- [x] **Step 3:** Atualizar `as-built-vps.md`; commit `docs(infra): as-built das VPS em 26/10`.

---

## Frente 2 — GLPI (F3): trilho do incidente

Detalhe de cada T no [plano GLPI](2026-10-12-glpi-ness-os-complete-delivery.md); aqui ficam entrada, teste de aceite e rótulo.

### Task 2.1: T03 — matriz negativa em laboratório `[A]`

**Files:**
- Modify: `app/docker-compose.glpi-maintenance.yml`, `app/backend/tests/test_glpi_maintenance_gateway.py`
- Create: `infra/tests/glpi-lab/docker-compose.yml` (GLPI + MariaDB sintéticos, entidades 1 e 5, portas em `127.0.0.1`), `infra/tests/test_glpi_t03_negative_matrix.py` (pula sem `GLPI_LAB_URL`)

- [ ] **Step 1: Testes**, um por percurso, todos esperando negação para entidade 5:
  `test_switch_to_descendant_entity_denied`, `test_entities_id_all_denied`,
  `test_computer_idor_denied`, `test_ticket_idor_denied`,
  `test_document_attachment_idor_denied`, `test_search_other_entity_empty`,
  `test_export_denied`, `test_batch_denied`,
  `test_encoded_path_traversal_denied` (`/Computer/1%2F..%2F5`, `%252F`),
  `test_nested_foreign_id_denied` (sub-recurso com ID da entidade 5),
  `test_reused_session_denied`, `test_upstream_token_never_returned`,
  `test_direct_upstream_from_hub_network_denied`; e
  `test_entity_1_asset_read_allowed` como controle positivo.
- [ ] **Step 2:** Subir lab, rodar → registrar quais falham hoje.
- [ ] **Step 3:** Ajustar o gateway (`glpi_maintenance_entrypoint.py`/`glpi_maintenance_runtime.py`) até todos passarem; rede exclusiva `172.30.250.0/28` validada contra colisão no lab.
- [ ] **Step 4:** `pytest infra/tests/test_glpi_t03_negative_matrix.py app/backend/tests/test_glpi_maintenance_*.py -v` → PASS.
- [ ] **Step 5:** Commit `test(glpi): matriz negativa T03 em laboratorio`.

### Task 2.2: T03 — decisão no ADR `[A]` + aprovação `[R]`

- [x] **Step 1:** ADR 0020 de "proposta" para "aceita", com contrato final, arquivos e resultado da Task 2.1.
  - Feito em `docs/adr/0020-glpi-maintenance-entity-boundary.md` (status "aceita"; contrato, resultado 18/18 e pendências da 2.3).
- [x] **Step 2:** Comentar na issue #74; Ricardo aprova o ADR. Aprovado em 27/10, com a regra de janela dispensada.

### Task 2.3: T03 — produção `[A]` (ADR aprovado e janela dispensada em 27/10)

- [ ] **Step 1:** Antes: último backup GLPI `COMPLETED` dentro do RPO; estado do Compose salvo.
- [ ] **Step 2:** Implantar gateway por digest; filtro de cliente API do GLPI limitado ao IP do gateway.
- [ ] **Step 3:** `test_glpi_network_boundary_probe.py` contra a topologia real (read-only) → Hub/worker não alcançam a API com a credencial 106.
- [ ] **Step 4:** Rodar a matriz da Task 2.1 contra produção apontando só para leitura.
- [ ] **Step 5:** Reativar 106 com direitos mínimos, readback, rotação, encerrar sessões antigas.
- [ ] **Rollback:** desativar 106, remover a rota nova; Hub 94 segue operando.
- [ ] **Step 6:** Evidência + runbook `infra/docs/runbooks/glpi.md`; indicador F3.

### Task 2.4: T04 — entrega idempotente `[A]` → `[R: D2]`

- [ ] **Step 1: Teste** `test_timeout_after_create_then_replay_creates_one_ticket`: GLPI fake cria o ticket e não responde; worker refaz 3×; afirma 1 ticket e reserva no estado `delivered`.
- [ ] **Step 2:** `test_permission_error_not_retried_forever`: 403 → estado `failed_permanent`, sem nova tentativa.
- [ ] **Step 3:** Rodar com os testes existentes (`test_glpi_ticket_reservation_migration.py`, `test_glpi_ticket_lookup.py`) → PASS.
- [ ] **Step 4 (janela):** migração em produção, `glpi_backlog_classify.py` read-only, replay controlado em ativo interno.

### Task 2.5: T05–T14 `[A]` com pontos `[R]`

Executar o plano GLPI na ordem T05 → T06 → T07 → T08/T09 → T10–T14. Pontos humanos: SLA contratual (T08), piloto de agentes #79 (T07), plugins/upgrade em janela (T12), canário (T13). Cada T fecha com evidência e atualização do runbook GLPI.

---

## Frente 3 — release e continuidade (F0: G0/G1)

### Task 3.1: Release do Hub da `main` `[A]` → `[R: GO]`

- [x] **Step 1:** Publicar imagens por digest a partir do SHA da `main` (contrato [release Hub](2026-10-12-hub-immutable-release-contract.md)).
- [x] **Step 2:** Canário + rollback ensaiado só se a configuração afetada mudou; manifesto aponta digests exatos.
- [x] **Step 3:** G0 com evidência no registro de gates.
- Concluída em 27/10: [evidência](../../execution/evidence/hub-release-2026-10-26.md) (API `412bdc0`; promoção de 26/10 revertida por regressão GLPI, corrigida no #95). Em 27/10 19:10, API `9c34eda` com monitor acionável (#111).

### Task 3.2: Continuidade observável `[A]`

- [ ] **Step 1:** Item Zabbix por timer de backup (`ness-zabbix-backup`, `ness-zabbix-object-storage-backup`, backup AIOps, backup Psono quando existir) com trigger de idade > 24h (RPO).
- [ ] **Step 2:** Teste: parar um timer em UAT, confirmar alerta; reativar.
- [ ] **Step 3:** G1 com evidência.

---

## Frente 4 — identidade e cofre (F1)

Detalhe no [plano Authentik](2026-10-12-authentik-fluid-delivery.md).

### Task 4.1: Bindings e homologação candidata `[A]`

- [ ] Bindings Google interno/externo com testes negativos; login/logout/expiração/revogação/usuário desativado por aplicação; papel e tenant na API/SSE. Entra no fluxo candidato, sem deny global.

### Task 4.2: MFA e recuperação nominais `[R: D4]`

- [ ] Cada pessoa cadastra fator e prova uso/recuperação (#66, #43, #44). Agente prepara o roteiro e registra a evidência.

### Task 4.3: Psono dedicado — IaC, lab, contratação, implantação `[A]` → `[$ R2]` → `[A]`

**Files:**
- Modify: `infra/terraform/environments/prod.tfvars` (entrada `psono`), `infra/ansible/inventory/hosts.yml`
- Create: `infra/ansible/roles/psono/{tasks,templates,handlers}/`, `infra/ansible/playbooks/psono.yml`, `infra/ansible/tests/test_psono_role.sh`, `infra/docs/runbooks/psono.md`
- Reuse: `infra/psono/docker-compose.yml`, `infra/psono/Caddyfile`, `infra/psono/settings.yaml.example`

- [ ] **Step 1: Teste da role em contêiner:** sobe Psono por Compose; afirma `/healthcheck/` 200 em `127.0.0.1`, Postgres sem porta publicada, backup Restic executa e `restic snapshots` lista 1.
- [ ] **Step 2:** Implementar a role reaproveitando `infra/psono/`; segredos lidos de variável (SOPS após 4.4).
- [ ] **Step 3:** Teste → PASS. Pedir D3.
- [ ] **Step 4 (após compra):** `infra/bin/tf plan` mostra **apenas** `create` de `contabo_instance.vps["psono"]`; guard → 0; `apply`.
- [ ] **Step 5:** `common` + `psono` no host novo; TLS via Caddy; agente Zabbix; backup no Object Storage com prefixo próprio.
- [ ] **Step 6:** Migrar dados do Psono temporário (AIOps); recuperação nominal por Ricardo e Ismael; origem preservada até o retorno validado.
- [ ] **Step 7:** As-built + runbook; desativar o Psono temporário só com GO.

### Task 4.4: SOPS/age `[A]` após `[R: D4]`

**Files:** Create `.sops.yaml` (dois recipients age, Ricardo e Ismael), `infra/secrets/*.enc.yaml`; modify `infra/bin/{tf,ansible}` para decifrar em memória.

- [ ] **Step 1:** `sops`/`age` por imagem Docker fixada (sem instalação).
- [ ] **Step 2:** Migrar por consumidor na ordem do master F1: novo → teste → revogação do anterior → owner/data.
- [ ] **Step 3:** `gitleaks detect` → limpo.

---

## Frente 5 — Zabbix definitivo (F2), sem VPS nova

Detalhe no [plano Zabbix](2026-10-12-zabbix-fluid-delivery.md). Destino: `169.58.234.9` (UAT, `zabbix-server` mascarado).

### Task 5.1: Destino reproduzível por Ansible `[A]`

- [ ] `playbooks/site.yml --check --diff --limit zabbix_uat` → diff vazio ou explicado; roles `zabbix-server`, `zabbix-frontend`, `mariadb`, `backup` passam a descrever a UAT real.

### Task 5.2: Qualidade da coleta `[A]` + `[R: #73]`

- [ ] Delta desde 15/10; correções por causa, em ondas de 5; meta unsupported <0,5% e FortiGate −70%. Proxy/UUID vSphere dependem de #73.

### Task 5.3: Corte `[R: D5]`

- [ ] Freeze, snapshot final, replay de deltas, DNS, ativação do destino após origem parar; smoke; D+1/D+3/D+7. Nunca dupla coleta.

### Task 5.4: Origem antiga `[R: D8]`

- [ ] Após 7–14 dias, desativação controlada; se D8 = reuso, reimagem pela entrada Terraform (troca de `image_id` explícita, com `prevent_destroy` removido só nessa mudança e registro).

---

## Frente 6 — Hub/PWA (F4)

### Task 6.1: Testes do frontend `[A]`

**Files:** Modify `app/frontend/package.json` (script `test`); Create `app/frontend/src/**/*.test.ts`.

- [ ] **Step 1:** Adicionar `vitest` (único devDependency novo; usa a config do Vite). `ponytail:` só lógica pura; testes de componente entram se uma regressão de UI aparecer.
- [ ] **Step 2:** Testes de gating por papel/tenant e de frescor (valor sem timestamp → estado "sem dado", nunca zero).
- [ ] **Step 3:** `npm run test && npm run typecheck && npm run build` via `docker run node:22` → PASS.

### Task 6.2: Verdade operacional `[A]`

- [ ] `grep -rn` por mocks, timestamps fixos e health constante em `app/frontend/src` e `app/backend/app`; cada fonte expõe último sucesso, frescor, erro e escopo; teste no backend: `pipeline_health` com fonte parada → `ready` falha.

### Task 6.3: Isolamento HTTP/SSE `[A]`

- [ ] Testes: `test_sse_does_not_stream_other_tenant`, `test_sse_closes_after_token_revoked`, `test_user_removed_from_tenant_mid_session_loses_stream`.

### Task 6.4: Matriz de ativação de entidades `[A]`

- [ ] `docs/execution/tenant-activation-matrix.md` a partir de leitura do GLPI: tenant, fontes, ativos, grupos, serviços, perfis, estado, evidência.

### Task 6.5: Jornadas nominais `[R: #51]`

- [ ] Desktop/móvel por perfil; G3.

---

## Frente 7 — operação integrada (F5)

Entrada: G0–G3 e T03/T04 `RELEASED`. Testes reaproveitam o [plano MVP](2026-09-27-ness-os-mvp-delivery.md).

### Task 7.1: Canário `[A]` → `[R: G4]`

- [ ] Evento sintético em ativo interno → 1 incidente no tenant certo → 1 ticket vinculado; replay 3×, timeout GLPI, restart do worker, recovery; jornadas por papel e negativa cruzada.

### Task 7.2: Expansão por ondas `[A]`

- [ ] Cavan — Matriz primeiro, depois a matriz da Task 6.4; lotes ≤5 ativos; checkpoint por tenant; D+1/D+3/D+7 reais.

---

## Frente 8 — AIOps e orquestração (F6), sem VPS nova

### Task 8.1: Contrato versionado e sanitização `[A]`

- [x] Schema alerta/incidente/enriquecimento/decisão com tenant, source event ID, severidade, frescor, evidência; teste `test_gemini_payload_has_no_secrets_or_other_tenant`; métricas de custo/latência/erro.

### Task 8.2: n8n → Node-RED `[A]`

- [ ] Node-RED como serviço no Compose da AIOps (capacidade: 8 vCPU/23,5 GB, conferir no as-built); um fluxo por vez, comparação em paralelo sem duplicar efeito externo.

### Task 8.3: RMM e canais `[R: D7]` → `[A]`

- [ ] SuperOps/Atera/Datto com contrato idempotente; WhatsApp/e-mail/push só com autorização, opt-in e teste de destinatário.

---

## Frente 9 — Wazuh e Workspace (F7): pronto para contratar

### Task 9.1: BOM recalculado `[A]` → `[R: D6]`

**Files:** Create `docs/procurement/wazuh-bom-2026-10.md`.

- [ ] Comparar duas topologias com a carga observada (624 endpoints, 4 vCPU, 21% médio / 41% pico): **single-node** (R3a) e **onda 1** (R3b). Critérios: endpoints, retenção 90 dias, disco por EPS, HA exigida, custo do painel, rollback.
- [ ] Recomendação de partida: R3a, migrando para R3b quando métrica de R3a ou exigência de HA justificar — sem refazer instalação (mesma role, mais nós).

### Task 9.2: IaC Wazuh testada em lab `[A]`

**Files:** Create `infra/ansible/roles/wazuh/`, `infra/ansible/tests/test_wazuh_role.sh`, `infra/docs/runbooks/wazuh.md`; Modify `infra/ansible/playbooks/wazuh-hub.yml` (passa a só chamar a role), `prod.tfvars` (entradas comentadas até a compra).

- [ ] **Step 1:** Versão 4.14.x suportada conferida na data; fixar por tag.
- [ ] **Step 2: Teste em lab na `stack`** (single-node, dado sintético, portas em `127.0.0.1`): indexer verde, manager aceita 1 agente de teste, dashboard 200, TLS próprio, RBAC com usuário não-admin, snapshot do indexer em bucket S3 de teste e restore.
- [ ] **Step 3:** Portas de cluster/API só na rede privada (R4); UFW nega no público.
- [ ] **Step 4:** Commit; tarefa fica `VERIFIED (lab)` aguardando D6.

### Task 9.3: Implantação e piloto `[$ R3/R4]` → `[A]`

- [ ] Terraform `create` das entradas aprovadas; `common` + `wazuh`; observation mode (sem ticket, IA ou notificação); 5 endpoints internos → piloto Cavan 50–100 em lotes; métricas EPS/CPU/RAM/disco; migração dos 624 do Hostinger em lotes, depois desativação da origem com GO.

### Task 9.4: Google Workspace Cavan `[R: D7]` → `[A]`

- [ ] Consentimento inicial do superadmin, identidade delegada mínima, normalização com tenant/frescor/idempotência, revogação testada; sem Alert Center.

---

## Frente 10 — marca e sustentação (F8), contínua

### Task 10.1: Marca por superfície `[A]`

- [ ] Seguir a [matriz de branding](2026-10-12-ness-branding-cross-product-plan.md) junto da entrega de cada produto (não no fim).

### Task 10.2: Runbooks exercitados `[A]` + `[R]`

- [ ] Um `infra/docs/runbooks/<serviço>.md` por serviço (Zabbix, GLPI, Hub, Authentik, Psono, Wazuh, backup) com owner/substituto, dependências, SLO, alertas, RPO/RTO, retorno, escalonamento, comandos `infra/bin/*` exatos. Ismael exercita cada um; evidência no runbook.

### Task 10.3: Encerramento `[R]`

- [ ] Revisão trimestral (custo, capacidade, retenção, credenciais), revogação de acessos temporários (incluindo a chave do agente, se não for mais necessária), release final e aceite global.

---

## Ordem e paralelismo

```
D1 ─► 0.3 ─► 3.1 ─────────────────────────────┐
0.1 ─► 0.2                                     │
0.4 ─► 1.1 ─► 1.2 ─► 1.3 ─┬► 4.3 ─[$R2]─► ...  │
                          ├► 5.1               │
                          └► 9.2 ─[D6,$R3]─► 9.3
2.1 ─► 2.2 ─[D2]─► 2.3 ─► 2.4 ─► 2.5 ──────────┤
4.1, 6.1–6.4, 8.1, 9.1 (independentes)         ▼
                                     7.1 ─► 7.2 (F5)
```

Em paralelo desde já: 0.1, 0.4, 2.1, 4.1, 6.1–6.4, 8.1, 9.1. Bloqueios
humanos não param as demais frentes (master §3.8).
