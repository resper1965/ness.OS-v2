# Gate 0 — estado de execução

> **Atualização vigente — 12/10/2026 (BRT): PARCIAL.** O Hub/AIOps foi
> promovido em runtime real com imagens GHCR imutáveis, `/ready` aprovado e
> rollback/re-promoção ensaiados. A prova detalhada está em
> [`evidence/hub-immutable-release-2026-10-12.md`](evidence/hub-immutable-release-2026-10-12.md).
> O gate global não está aprovado: falta CI integral em runner limpo e a
> integração protegida do workflow no PR #65. A recuperação externa atual do
> conjunto AIOps de 12/10/2026 é tratada no G1, sem alterar Zabbix.

> **Estado corrente da Fase 0 (26/09/2026): FAIL.** Para decisão de release,
> backups/restores e corte, prevalece [`gates/phase-0-recovery-release.md`](gates/phase-0-recovery-release.md), atualizado após este histórico. As atualizações datadas abaixo preservam decisões e observações do período em que foram registradas; prazos históricos não são autorização vigente.

> Início: 20/08/2026
> Estado geral: em andamento; incidente crítico Zabbix contido

## Atualização — 26/08/2026, janela excepcional autorizada

- Diagnóstico do backup de produção: `dbzabbix` ocupa aproximadamente 50 GiB.
  Os backups de 24 e 25/08 excederam `TimeoutStartSec=3h`; o último conjunto
  `COMPLETED` permanecia em 23/08.
- Aplicada, com rollback local preservado, a alteração de `TimeoutStartSec`
  para 6 h em `ness-zabbix-backup.service`. A execução mantém `nice=15` e
  `ionice` de menor prioridade.
- Reagendada a cópia ao Object Storage para 05:30 BRT, depois da janela local.
  O reinício do timer acionou uma cópia atrasada de 23/08; ela foi interrompida
  antes da execução nova, sem remover snapshots existentes.
- Novo dump consistente iniciado em 26/08 às 16:37 BRT e observado em
  progresso, com `mariadb-dump --single-transaction --quick` e o Zabbix Server
  permanecendo ativo. Pendente: `COMPLETED`, checksums, cópia externa e restore.

## Concluído

- [x] Baseline inicial das duas VPS.
- [x] Contenção do XMRig e remoção da persistência no usuário `zabbix`.
- [x] Conta padrão `Admin` teve senha substituída por valor aleatório irrecuperável, sessões e tokens revogados e associação formal ao grupo `Disabled` concluída.
- [x] Origens correlacionadas ao ataque bloqueadas no Zabbix.
- [x] Endpoints de descarga maliciosa conhecidos bloqueados para saída no Zabbix.
- [x] Escopo do audit log refinado: `execute_on=1` confirma execução no servidor, não nos ativos usados como contexto.
- [x] Execução de scripts no servidor Zabbix desativada explicitamente; serviço reiniciado e validado.
- [x] Sessenta scripts suspeitos preservados como evidência e neutralizados.
- [x] MariaDB e Zabbix recuperados e validados.
- [x] Backup emergencial local do AIOps, com dumps e checksums.
- [x] Backup do volume real de dados GLPI e volume n8n.
- [x] Backup AIOps noturno instalado para 23:00 BRT e validado ponta a ponta, incluindo dumps lógicos, configurações, n8n, GLPI e volume anônimo real do GLPI.
- [x] Fail2ban AIOps corrigido e testado.
- [x] Fuso AIOps corrigido para `America/Sao_Paulo`.
- [x] Swap persistente criado sem reinício: 8 GiB no Zabbix e 4 GiB no AIOps, com `swappiness=10`.
- [x] Portas 8082/8085 removidas do Compose, UFW e publicação Docker.
- [x] Hub, Authentik, n8n e GLPI validados pelo Caddy.
- [x] Workflow de deploy inseguro substituído e publicado desabilitado na branch `feat/nessos-platform` (`48ade01`); a branch `main` não contém esse workflow.
- [x] Script de backup Zabbix instalado e agendado para 22:00 BRT.
- [x] Senha local padrão do Hub rotacionada e entregue somente em arquivo root protegido na VPS.
- [x] Senhas root expostas rotacionadas nas duas VPS; SSH por senha e keyboard-interactive desativado e novos acessos por chave validados.
- [x] Segredo JWT do Hub rotacionado; sessões anteriores revogadas.
- [x] Credencial Basic removida do código e bundle frontend; requisições migradas para Bearer da sessão.
- [x] Chaves VAPID persistentes configuradas sem exposição no repositório.
- [x] Callback e grants OIDC do Hub corrigidos; autorização sintética alcança o fluxo Authentik sem erro OAuth.
- [x] `state` OIDC do Hub tornado criptograficamente seguro, de uso único e validado no callback.
- [x] Endpoint temporário `sso_debug.php` ausente do GLPI e validado internamente com HTTP 404.
- [x] AIOps migrado de SSH root por chave para `ness_admin` nominal com `sudo`; login nominal testado após reload e nova sessão root confirmadamente bloqueada.
- [x] Artefato `.venv` Windows de 133 MB removido do caminho de produção AIOps e preservado em quarentena root-only; 14 arquivos e três diretórios world-writable normalizados sem alteração de conteúdo.
- [x] Borda revalidada externamente: seis domínios com TLS válido; 8082/8085 fechadas; somente portas previstas respondem.
- [x] Varredura inicial de persistência no Zabbix sem processos suspeitos, cron malicioso ou executáveis em diretórios temporários; Fail2ban ativo.
- [x] Nove cópias paralelas de `zabbix_server.conf` removidas do diretório ativo e preservadas na quarentena do incidente como `600 root:root`; sete continham a credencial de banco vigente.
- [x] Auditoria inicial de licenças e tags concluída; conflitos e migrações registrados em [`open-source-license-audit-2026-08-20.md`](open-source-license-audit-2026-08-20.md).
- [x] Backup Zabbix de 22:00 BRT concluído: 4,7 GiB, checksums recalculados, gzip/tar legíveis, permissões `700/600` e serviços ativos.
- [x] Backup AIOps de 23:00 BRT concluído: checksums recalculados, dumps listáveis por `pg_restore`, arquivos gzip/tar legíveis e 14 contêineres ativos.
- [x] Permissões do backup AIOps corrigidas para acesso exclusivo de root; script recorrente endurecido e implantado com hash idêntico ao repositório. Evidências em [`backup-verification-2026-08-21.md`](backup-verification-2026-08-21.md).
- [x] Os 266 registros de execução foram correlacionados com os oito hosts usados como contexto; quatro são Fortigate/SNMP, dois Windows Server 2019, o Zabbix Server e o proxy Lima. Evidências em [`zabbix-incident-context-verification-2026-08-21.md`](zabbix-incident-context-verification-2026-08-21.md).
- [x] Auditoria de usuários/scripts confirmou `EnableGlobalScripts=0`, Admin sem sessões/tokens, 14 Super Admins e 58 scripts customizados; divergências e decisões em [`zabbix-security-access-audit-2026-08-21.md`](zabbix-security-access-audit-2026-08-21.md).
- [x] Política de privilégio aprovada: no máximo duas identidades break-glass como Super Admin; Ricardo, Rogério e Ismael usarão papéis administrativos limitados no cotidiano; Agnaldo permanece em observação como User.
- [x] Contenção final do incidente executada: `Admin` no grupo `Disabled`, 58 comandos customizados preservados e neutralizados, checksums válidos e serviços ativos.
- [x] Token `resper/intranet` rastreado, revogado e removido das cinco referências de código identificadas; evidência antes/depois preservada com SHA-256.
- [x] Restauração isolada AIOps executada a partir do backup noturno: quatro bancos PostgreSQL, 16 roles, 466 tabelas GLPI, duas tabelas de projeto e 12 arquivos/volumes restaurados; recursos temporários removidos ao final.
- [x] Backup AIOps pós-rotação/pós-fixação (`20260821T135439-0300`) recalculado e restaurado novamente em isolamento, com os 18 checksums válidos e o mesmo inventário lógico confirmado.
- [x] GLPI 11.0.8 fixado pelo digest em execução; defaults de senha removidos do Compose, credenciais MariaDB rotacionadas, configuração persistente sincronizada e HTTP/banco/cron revalidados.
- [x] Baseline de acessos nominais AIOps concluída: quatro identidades presentes no Authentik, Hub com JIT OIDC preparado e duplicidades GLPI identificadas sem alteração direta no banco.
- [x] Fundação GLPI inventariada e manifesto inicial de catálogo, cinco projetos piloto e dez runbooks versionado em [`../../config/glpi/ness-os-foundation-v1.yaml`](../../config/glpi/ness-os-foundation-v1.yaml).
- [x] Dez imagens AIOps de terceiros aplicadas por digest nos contêineres ativos; 14 contêineres, zero `unhealthy`, backup/restore pós-mudança e hashes Compose local/remoto validados. Evidências em [`aiops-image-pinning-2026-08-21.md`](aiops-image-pinning-2026-08-21.md).
- [x] Defaults PostgreSQL/Auth­entik efetivamente ativos removidos e rotacionados de forma transacional; consumidores sincronizados, sessões antigas do Authentik invalidadas, serviços validados e backup pós-rotação restaurado. Evidências em [`aiops-secret-rotation-2026-08-21.md`](aiops-secret-rotation-2026-08-21.md).
- [x] Plano de controle Contabo contido: backend restrito a `platform_admin` e somente GET, secrets/mutações removidos, PWA somente leitura, 39 testes e build aprovados, API/frontend/borda saudáveis e rollback preservado. Evidências em [`contabo-control-plane-containment-2026-08-22.md`](contabo-control-plane-containment-2026-08-22.md).
- [x] Endpoint `/api/dashboard/problems` protegido por `require_noc`: suíte integrada com 41 testes, produção `healthy`, acesso anônimo HTTP 401, borda HTTP 200 e rollback root-only preservado.
- [x] Métricas globais `/api/core/overview` e `/api/core/kpis` restritas a NOC/SOC/admin; catálogo `/api/core/modules` preservado para autenticados. Indicadores sem falsa precisão implantados, 46 testes aprovados, produção saudável e rollback preservado.
- [x] Cliente Contabo incluído no runtime sem dependência nova; build/import aprovados. Router GET efetivamente montado com 401 anônimo, secrets/mutações 404, API saudável, Hub HTTP 200 e rollback preservado.
- [x] Importador controlado da taxonomia GLPI implementado localmente: dry-run padrão, exatamente oito categorias, idempotência, bloqueio de escrita antes de HTTP enquanto o manifesto não estiver `approved` e 16 testes integrados aprovados. Nenhum deploy ou dado foi escrito no GLPI.
- [x] Secret scanning open source preparado no CI com Gitleaks 8.30.1: PR examina somente o intervalo novo, execução manual examina o snapshot, saída totalmente redigida, sem artefato de achados, permissões read-only e binário/checkout fixados e validados.
- [x] Tooling Restic/S3 para cópia externa criptografada preparado e testado estaticamente, sem deploy ou credenciais: seleciona somente backup `COMPLETED` com checksums, separa host/dataset, verifica dados e preserva ao menos um snapshot.
- [x] Backup Zabbix recorrente `20260822T121154-0300` concluído, validado e transferido à KVM8 com SHA-256 idêntico; `transfer=PASS`.
- [x] Restore Zabbix real comprovado na KVM8: 203 tabelas, 674 hosts/templates, 60.250 itens, 24.520 triggers, `dbversion=7000000`, canais ativos zerados, MariaDB localhost-only e Zabbix Server inativo/mascarado. A saída inicial sofreu SIGPIPE e acionou fail-closed; o verificador independente passou e o runner foi corrigido para evidência atômica.
- [x] Auditoria offline pós-restore concluída sem iniciar coleta: integridade estrutural principal aprovada, 17 proxies preservados desconectados e quarentena validada. O corte ficou `NO-GO` até reduzir ou aceitar formalmente 1.204 itens não suportados (2,88%), 584 triggers `unknown` antigas e 1.829 escalations históricas vencidas; baseline atualizada em [`zabbix-polish-baseline-2026-08-20.md`](zabbix-polish-baseline-2026-08-20.md).
- [x] Auditoria Authentik reaplicada sem mutação: core saudável, mas nenhuma aplicação homologada; Hub/GLPI/n8n/Zabbix parciais, ness.OS legado/Wazuh/Grafana `NO-GO`, `platform_admin` ausente e MFA dos três administradores-alvo não comprovado. Matriz e ordem de regularização atualizadas em [`../../infra/docs/authentik-integration-audit.md`](../../infra/docs/authentik-integration-audit.md).
- [x] Validador local e não mutante dos projetos GLPI implementado: cinco projetos e 13 work packages verificados; duplicidades, pais ausentes e ciclos falham fechado. Testes combinados com o importador seco de categorias: `10 passed`. Manifesto aprovado por Ricardo Esper em 24/08/2026.
- [x] Conta técnica GLPI `svc_ness_os` (ID 94), perfil mínimo `ness.OS Integration` (ID 12), cliente API ID 2 e tokens temporários criados pela interface suportada; autorização única na raiz Ness, não recursiva. Segredos locais estão em arquivo ignorado pelo Git e `0600`, pendentes de cofre e revogação no gate final.
- [ ] Tornar o caminho de máquina da API GLPI funcional: `apirest.php/initSession` ainda recebe `302` para o Authentik. Preferir rota privada AIOps→GLPI; homologar origem positiva/negativa, sessão, leituras mínimas e dry-run antes de qualquer escrita do manifesto.
- [x] Rotinas internas independentes de contratação executadas: backend lint/format/suíte aprovados, frontend sem erros e com build aprovado, 29 scripts com sintaxe válida, toolings Restic/Zabbix aprovados, Compose AIOps válido, relatórios GLPI/segredos somente leitura executados, KVM8 ainda isolada e 63 documentos sem link local quebrado. Evidência em [`internal-routines-execution-2026-08-23.md`](internal-routines-execution-2026-08-23.md).
- [x] Acesso nominal AIOps recuperado após redefinição autorizada da senha `root`: `ness_admin` autenticou por `id_ed25519_stackvps`, pertence a `sudo` e passou em `sudo -n`; a senha de recuperação permaneceu somente em arquivo local `0600`, fora do repositório.
- [x] Console VNC temporário da AIOps desabilitado após a recuperação; a revalidação após reload mostrou `VNC desativado` e exigência de nova senha para reabilitação.
- [x] Cópia externa AIOps comprovada no Contabo Object Storage: conjunto `20260823T230000-0300`, 20 arquivos, todos os `SHA256SUMS` válidos, snapshot Restic `5f67fdff`, `restic check` sem erros e restore externo isolado com `--verify` e 30.926.734 bytes validados. O temporário foi removido e o timer diário de 00:30 BRT está ativo.
- [x] Cópia externa Zabbix comprovada no Contabo Object Storage durante janela excepcional autorizada: conjunto `20260823T220020-0300`, oito arquivos, snapshot Restic `3f3f2f53`, 4,821 GiB, `restic check` e amostra de 5% sem erros. Restore externo isolado com `--verify` restaurou 5.176.272.566 bytes e todos os `SHA256SUMS` passaram; temporário removido, timer diário de 23:30 BRT ativo e serviços preservados.

## Em andamento

- [ ] Executar varredura IOC direta no proxy Lima por SSH/console/RMM e nos dois Windows por RMM/EDR; a correlação Zabbix foi concluída, mas telemetria não substitui inspeção do endpoint.
- [ ] Reduzir as 14 contas Super Admin após confirmação nominal de owners/funções; nenhuma conta será rebaixada por inferência.
- [x] Triar e quarentenar os achados Gitleaks do snapshot: os 69 achados restantes estavam em 24 arquivos ignorados pelo Git; segredos/runtimes foram movidos para quarentena externa, 66 artefatos legados foram separados e a repetição retornou zero achado. O histórico Git e a rotação dos provedores permanecem pendentes. Evidências em [`repository-quarantine-2026-08-24.md`](repository-quarantine-2026-08-24.md).
- [ ] Concluir inventário de credenciais Zabbix após disponibilização do Psono Community; a varredura inicial de arquivos e persistência foi executada sem expor valores.
- [ ] Remediar o backlog usando a cópia restaurada como baseline segura: 1.204 itens ativos não suportados (2,88%), 584 triggers habilitadas `unknown` há mais de 24 horas e 1.829 escalations históricas vencidas. Não limpar por SQL nem desativar em massa; plano detalhado em [`zabbix-escalation-backlog-2026-08-20.md`](zabbix-escalation-backlog-2026-08-20.md) e ordem de ondas em [`zabbix-polish-baseline-2026-08-20.md`](zabbix-polish-baseline-2026-08-20.md).
- [ ] Executar plano de polimento do Zabbix a partir da baseline em [`zabbix-polish-baseline-2026-08-20.md`](zabbix-polish-baseline-2026-08-20.md).
- [x] Reexecutar a baseline de polimento na VPS permanente restaurada: banco isolado aprovado, 311 hosts, 1.204 itens não suportados, 584 triggers `unknown`, 1.829 escalations vencidas, 274 hosts sem tags e 20 sem template; ações e coleta continuam desativadas. Ordem de correção em [`zabbix-prd-01-polish-baseline-2026-08-25.md`](zabbix-prd-01-polish-baseline-2026-08-25.md).
- [ ] Iniciar homologação de Valkey, PostgreSQL sem Timescale Community e Node-RED; as imagens atualmente implantadas já estão fixadas por digest e nenhuma troca de tecnologia ocorrerá sem staging e rollback.
- [ ] Reconciliar duplicidades de identidade no GLPI pela interface/API suportada e homologar login nominal ponta a ponta; nenhuma fusão/exclusão será feita diretamente no banco.
- [ ] Rotacionar de forma transacional as credenciais de produção expandidas durante diagnóstico em 22/08, sem reproduzi-las em logs/documentação; priorizar Contabo, JWT/OIDC, bancos, Authentik, GLPI, n8n, Gemini, VAPID e API Zabbix.

## Bloqueios externos

- [ ] Proxy Lima: solicitação de acesso/RMM e coleta IOC entregue a Ricardo para envio a Ismael (`iaraujo@ness.com.br`); aguarda resposta.
- [ ] Cofre de segredos: Psono Community foi escolhido para PoC e requer uma terceira VPS independente, domínio e SMTP. Passbolt Community é apenas contingência. Os arquivos `root-only` nas VPS permanecem como contenção temporária.

## Pendente no Gate 0

- [x] Copiar backups criptografados para Object Storage: AIOps e Zabbix aprovados com upload, `restic check`, restore externo isolado e checksums.
- [x] Comprovar a cópia externa no novo destino permanente Zabbix: backup offline `20260825T202327-0300`, snapshot Restic `60a22d18`, `restic check`, restore isolado de 5.109.745.472 bytes e todos os checksums aprovados. Evidência em [`zabbix-prd-01-external-backup-2026-08-25.md`](zabbix-prd-01-external-backup-2026-08-25.md).
- [ ] Definir retenção/expurgo do backup Zabbix e adicionar cópia externa; a rotina recorrente diária das 22:00 já está instalada e ativa.
- [ ] Rotacionar credenciais administrativas restantes.
- [ ] Homologar o primeiro login OIDC de Ricardo, Rogério e Ismael no Hub; o provisionamento nominal é JIT e a conta local permanece apenas como acesso emergencial temporário.
- [ ] Validar MFA, logout, revogação e break-glass em cada solução; as identidades nominais já existem no Authentik.
- [ ] Identidade de Agnaldo confirmada como `agsilva` / `agsilva@ness.com.br`; manter observação antes de promover. Não confundir com `asilva` (André Silva).
- [ ] Migrar credenciais humanas/break-glass para cofre corporativo e segredos de automação para SOPS/age.
- [ ] Restringir 10051 às redes/proxies aprovados.
- [x] Definir e iniciar reconstrução limpa da VPS Zabbix: a VPS permanente `ness-os-zabbix-prd-01` foi preparada e recebeu restore isolado aprovado; 203 tabelas, 674 hosts/templates, 60.250 itens e 24.520 triggers, com ações/mídias neutralizadas e servidor mascarado. Evidência em [`zabbix-prd-01-restore-2026-08-25.md`](zabbix-prd-01-restore-2026-08-25.md). O corte continua pendente de UAT.

## Atualização — 17/09/2026

**Consolidação de 27 dias de execução (21/08 — 17/09/2026).**

### Estado Geral

- ✅ **Incidente contido:** XMRig eliminado, senhas/tokens rotacionados, backups validados operacionais.
- ✅ **Fundação operacional:** Zabbix e Hub estáveis, backup local + externo reproducível.
- ❌ **Transmutação vencida:** Plano de 10–12 dias úteis levou 27 dias calendário; nenhuma decisão executiva ainda.

### Concluído desde 26/08

- ✅ Backup Zabbix: 27 rotações diárias sem falha, 22:00 BRT, checksums OK.
- ✅ Backup AIOps: 27 rotações diárias sem falha, 23:00 BRT, restore isolado comprovado.
- ✅ Backup externo: Restic S3 diário automático, 27 snapshots, todos validados.
- ✅ KVM8: Pronta para polimento desde 22/08, aguardando decisão sobre backlog.
- ✅ Segredos: Reduzido de 69 Gitleaks para 0; migração para Psono aguardando aprovação.
- ✅ GLPI: Manifesto de catálogo/projetos aprovado (5 projetos, 8 categorias, 13 work packages).
- ✅ Authentik: Core saudável, fluxo OIDC validado; homologação por aplicação pendente.

### Bloqueado — Requer Decisão Executiva (Ricardo Esper)

**D-PAC-1: Estratégia Polimento Zabbix**
- Backlog: 1.204 itens não suportados, 584 triggers `unknown`, 1.829 escalations vencidas.
- Opções: (A) Onda de polimento 5 dias + UAT 2 dias, (B) aceitar como debt, (C) adiar indefinidamente.
- Recomendação: Opção A pela engenharia.
- **Status:** ❌ Aguardando decisão.

**D-PAC-2: Contratação Contabo Nova**
- Especificação: 8 vCPU, 32 GB RAM, 1 TB SSD; ~€55/mês.
- KVM8 pode servir como bridge por máximo 14 dias adicionais.
- **Status:** ❌ Aguardando autorização de compra.

**D-PAC-3: Psono Community PoC**
- Requisitos: VPS 2 vCPU/4 GB/40 GB; não bloqueia Zabbix (paralelo).
- Custo: ~€3/mês.
- Benefício: ativa pipeline de secrets em paralelo.
- **Status:** ❌ Aguardando aprovação.

### Cronograma Realista (se decisões aprovadas hoje)

```
18/09 — Decisões críticas aprovadas
19/09 — Onda 1 polimento iniciada (FortiGate, switches)
01/10 — Qualificação Zabbix (UAT completo)
06/10 — Aprovação técnica (go/no-go)
07/10 — **CORTE PARA CONTABO NOVA** (janela 22:00 BRT)
15/10 — Observação concluída, aceite
16/10 — **Gate 1 Zabbix concluído**
```

### Próximas Ações

| Ação | Responsável | Prazo |
|---|---|---|
| Aprovar D-PAC-1/2/3 | Ricardo Esper | 18/09 17:00 |
| Designar eng. Zabbix (Onda 1) | Ricardo Esper | 18/09 18:00 |
| Provisionar VPS Psono | Eng. Infraestrutura | 19/09 meio-dia |
| Iniciar Onda 1 | Eng. Zabbix | 19/09 14:00 |
| Atualizar docs | Eng. DevOps | 18/09 20:00 |

Detalhes completos em [`project-stage-2026-09-17.md`](project-stage-2026-09-17.md).

## Preparação da transmutação Zabbix

- [x] Hostinger KVM8 temporária aceita como fábrica efêmera de restauração, saneamento e empacotamento e, se aprovada em UAT, como ponte operacional curta; ela não será o destino permanente nem contará como VPS permanente.
- [x] Sequência, controles, critérios de aceite e descarte documentados em [`zabbix-transmutation-kvm8-plan.md`](zabbix-transmutation-kvm8-plan.md).
- [x] KVM8 confirmada pela API, recriada com Ubuntu 24.04 LTS e host key antiga substituída somente após o reimage autorizado.
- [x] `ness_admin` com chave/sudo validado; root e senha SSH bloqueados; UFW, firewall Hostinger, Fail2ban, auditd, NTP, atualizações e swap aplicados. Evidências em [`zabbix-kvm8-bootstrap-2026-08-21.md`](zabbix-kvm8-bootstrap-2026-08-21.md).
- [x] KVM8 final alinhada ao Debian 12 da produção, com MariaDB 10.11.18 e Zabbix 7.0.27 fixados; server mascarado, banco localhost-only e restore/transfer com checksum preparados.
- [x] Pipeline de restore da KVM8 aprovado com dump sintético do schema oficial: 203 tabelas, 408 hosts/templates, 18.388 itens, 6.879 triggers, `dbversion=7000000`, canais neutralizados e server mascarado; artefatos sintéticos removidos após evidência.
- [ ] Revogar no hPanel o token Hostinger exposto no chat; ele não foi persistido localmente, mas continua válido no provedor até revogação.
- [ ] Informar prazo de descarte da KVM8.
- [ ] Executar baseline/hardening da KVM8 sem apontar DNS, agentes ou proxies de produção.
- [x] Destino decidido: contratar nova VPS Contabo permanente para o Zabbix, executar corte direto e preservar a atual como rollback por 7–14 dias; depois do aceite, reimage total e reutilização da antiga no piloto Wazuh.
