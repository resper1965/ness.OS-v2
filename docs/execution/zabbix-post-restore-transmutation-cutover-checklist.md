# Checklist executável — Zabbix pós-restore, transmutação e corte Contabo

> Escopo: Zabbix 7.0 LTS restaurado na KVM8 isolada, saneamento e polimento lógico antes da migração, corte para Contabo limpa e estabilização posterior.
> Regra Ponytail: reutilizar scripts, Ansible e relatórios existentes; não criar automação paralela enquanto estes cobrirem o passo.
> Segurança: não registrar valores de segredos, tokens, sessões ou comandos preservados do incidente nas evidências.

## Resultado e responsáveis

- [ ] Responsável técnico, operador da janela, aprovador e canal de comunicação registrados.
- [ ] Origem, KVM8, destino Contabo, DNS/IP, início, prazo de rollback e janela aprovados.
- [ ] Evidências guardadas fora da KVM8, com data/hora, executor, comando/ação, resultado e SHA-256 quando aplicável.
- [ ] Mudanças em lotes reversíveis; um lote só avança depois de medir o anterior.

## 1. Antes da migração — restore isolado e quarentena

### 1.1 Aceitar o restore

- [x] Confirmar dump sob `/var/lib/ness-os/restore-input`, SHA-256 igual à origem e `gzip -t` aprovado.
- [x] Executar o restore nativo existente:

```bash
sudo /usr/local/sbin/ness-zabbix-kvm8-native-restore restore DUMP EXPECTED_SHA256
```

- [ ] Registrar duração, espaço usado e pico de CPU/RAM/I/O do restore.
- [x] Conferir no relatório root-only: tabelas, hosts, itens, triggers e `dbversion=7000000`.
- [x] Confirmar `mariadb=active`, bind somente em `127.0.0.1`, `zabbix-server=inactive/masked` e ausência de porta 10051 pública.
- [x] Confirmar actions, media types e connectors ativos iguais a zero.
- [x] Confirmar ausência de coleta, conexão com agentes/proxies e envio de notificações.
- [x] Preservar o banco restaurado e o dump íntegro; remover apenas cópias parciais redundantes.

**Saída:** restore íntegro e isolado, sem efeito em produção. Falha em hash, gzip, schema, contagens ou isolamento é `NO-GO`.

### 1.2 Baseline antes de alterar

- [x] Exportar/configurar evidência das versões de Debian, MariaDB, Zabbix, pacotes fixados, portas, serviços e relógio.
- [x] Capturar contagens atuais de hosts, itens, triggers, proxies, actions, media types, connectors, scripts, usuários, sessões e tokens sem seus valores.
- [ ] Executar o relatório existente de segurança:

```bash
sudo ./infra/scripts/zabbix-security-state-report.sh > EVIDENCIA_ROOT_ONLY
```

- [ ] Registrar baseline de itens ativos não suportados, triggers `unknown`, escalations vencidas, NVPS, filas, processos busy, preprocessamento, housekeeping, crescimento do banco e I/O.
- [ ] Exportar templates, macros sem valores secretos, ações, media types, manutenções, mapas e dashboards antes de cada onda.

**Saída:** baseline comparável antes/depois e rollback de configuração possível.

## 2. Antes da migração — saneamento e hardening lógico

### 2.1 Identidade, RBAC, scripts e segredos

- [ ] Manter `EnableGlobalScripts=0`; não reativar scripts globais durante transmutação ou corte.
- [ ] Confirmar os 58 scripts ligados ao incidente neutralizados e seus hashes preservados; não copiar comandos históricos para arquivos novos.
- [ ] Manter `Admin` no grupo `Disabled`, sem sessão ou token.
- [ ] Limitar `Super admin` a duas identidades break-glass com MFA, segredo no cofre e teste periódico.
- [ ] Criar papéis diários administrativos limitados para Ricardo, Rogério e Ismael.
- [ ] Manter Agnaldo em `User role` durante a observação aprovada.
- [ ] Tornar `zbxgrafana` uma identidade API somente leitura, limitada aos host groups necessários; rotacionar a credencial após o teste.
- [ ] Definir `akadmin` como bootstrap, break-glass ou conta cotidiana antes do corte.
- [ ] Confirmar owner e necessidade das demais contas privilegiadas; revogar sessões/tokens órfãos.
- [ ] Rotacionar todos os segredos que tocaram origem comprometida ou KVM8; humanos no Psono Community e automação em SOPS/age.
- [ ] **Bloqueio:** não aplicar `infra/ansible/inventory/group_vars/all.yml` em produção enquanto houver valores sensíveis não cifrados e divergências entre variáveis/templates.

**Saída:** menor privilégio comprovado; nenhuma identidade, token ou script sem owner e finalidade.

### 2.2 Sistema, rede e frontend

- [ ] Reproduzir Debian 12, Zabbix 7.0 e MariaDB 10.11 com versões fixadas e configuração versionada.
- [ ] Usar acesso nominal `ness_admin`, chave SSH, `sudo`, sem login root e sem senha; SSH na porta definida e Fail2ban ativo.
- [ ] Manter MariaDB local-only; expor apenas portas indispensáveis no firewall.
- [ ] Restringir 10051 às origens aprovadas; não publicar banco, APIs administrativas ou portas de cluster.
- [ ] Validar HTTPS, certificado, redirect HTTP→HTTPS, headers e proteção dos diretórios do frontend.
- [ ] Manter relógio sincronizado, logs persistentes e rotação configurada.
- [ ] Confirmar backup inicial, SHA-256 e restore isolado antes de qualquer promoção.

**Saída:** baseline mínima de produção atendida; vulnerabilidade crítica conhecida bloqueia o corte.

## 3. Antes da migração — qualidade da coleta e polimento

### 3.1 Backlog `unsupported`, `unknown` e escalations

- [ ] Classificar os itens não suportados por template/causa: chave/OID/cálculo, autenticação, timeout, conectividade/DNS, preprocessamento, tipo de valor e outros.
- [ ] Corrigir primeiro templates/chaves/cálculos compartilhados; depois credenciais/macros, timeouts, conectividade e casos isolados.
- [ ] Tratar em lotes os FortiGate e VMware destacados no diagnóstico; não desabilitar hosts/templates inteiros em massa.
- [ ] Corrigir ou desabilitar somente item comprovadamente inválido, com export/diff e rollback.
- [ ] Restringir ações internas 3–6 aos grupos/objetos operacionais relevantes; preservar eventos e deixar escalations fecharem por recuperação normal.
- [ ] Não limpar `escalations` por SQL e não aumentar pollers/escalators antes de eliminar a causa.
- [ ] Após cada lote medir: itens não suportados, triggers `unknown`, escalations vencidas, CPU MariaDB, fila e `zabbix[process,escalator,avg,busy]`.

**Metas de saída:** itens ativos não suportados `<0,5%`; nenhuma trigger `unknown` por mais de 24 h sem exceção; nenhum host com dezenas/centenas de falhas sem justificativa; escalations vencidas caindo; escalator médio `<75% busy` por 15 min.

### 3.2 Inventário, tags, localização e mapas

- [ ] Selecionar um cliente e dois sites representativos como piloto.
- [ ] No GLPI, normalizar entidades/localizações, instalar/validar GLPI Agent, reconciliar serial/UUID/última coleta e homologar coordenadas.
- [ ] Não sincronizar GLPI→Zabbix antes do piloto reconciliado; GLPI é canônico para cliente, ativo, site, endereço, coordenadas, criticidade e owner.
- [ ] Propor e homologar, sem renomeação em massa, as tags `cliente`, `site`, `servico`, `ambiente`, `tecnologia`, `scope` e `owner`.
- [ ] Usar inventário automático apenas para atributos técnicos coletáveis; não sobrescrever dados de negócio do GLPI.
- [ ] Criar Geomap executivo por cliente/site e mapa lógico separado por cliente/site; cada elemento aponta para host, problema, gráfico ou runbook.
- [ ] Criar dashboards para NOC geral, cliente, disponibilidade, capacidade, proxies/coleta e qualidade da monitoração.

**Saída do piloto:** GLPI reconciliado, agentes ativos, tags homologadas, Geomap, mapa lógico, dashboard operacional e redução mensurada de itens não suportados. Só então replicar.

### 3.3 Proxies

- [ ] Inventariar nome, cliente/site, IP, `proxyid`, modo, versão, último acesso, TLS, hosts atendidos e owner de cada proxy.
- [ ] Manter server e proxies na major 7.0; configurar TLS PSK/certificado e allowlist da porta 10051.
- [ ] **Bloqueio:** substituir todos os `PLACEHOLDER_IP`, `proxyid: 0`, acesso root e caminho de chave compartilhada em `infra/ansible/inventory/proxies.yml` antes de executar o playbook.
- [ ] Validar conectividade primeiro e aplicar por proxy/lote pequeno; o playbook existente aceita `--limit` e usa token via ambiente:

```bash
ansible -i infra/ansible/inventory/proxies.yml zabbix_proxies -m ping
ansible-playbook -i infra/ansible/inventory/proxies.yml infra/ansible/playbooks/reconnect-proxies.yml --limit PROXY
```

- [ ] Não apontar proxies reais para a KVM8 durante ensaio; no corte, reconectar em ondas e medir fila/último acesso entre ondas.

**Saída:** inventário sem placeholders, TLS/allowlist aprovados e todos os proxies reportando sem duplicar ingestão.

### 3.4 Notificações e retenção

- [ ] Manter actions, media types, connectors e webhooks desabilitados no staging.
- [ ] Exportar e revisar destinatário, severidade, tags, período e recovery de cada ação; remover integração sem owner.
- [ ] No UAT, ativar somente canal de teste, disparar evento sintético e validar problema, reconhecimento, recovery, deduplicação e runbook; depois desativá-lo.
- [ ] Habilitar canais reais somente após go/no-go, por lote, observando flood e falhas de entrega.
- [ ] Definir history/trends/events a partir do crescimento diário, RTO/RPO, housekeeping e I/O medidos; não importar cegamente retenções antigas.
- [x] Validar backup com manifesto `COMPLETED`, SHA-256, cópia externa privada e restore isolado. Object Storage Contabo foi aprovado para Zabbix e AIOps; política semanal/mensal local permanece a definir.

**Saída:** notificação útil e recuperável, retenção compatível com capacidade e backup restaurável.

### 3.5 Observabilidade operacional

- [ ] Monitorar o próprio Zabbix: NVPS, filas, processos busy, cache, preprocessamento, LLD, escalations, housekeeping e último acesso dos proxies.
- [ ] Monitorar MariaDB: CPU, conexões, buffer pool, temporárias em disco, slow queries, crescimento e I/O.
- [ ] Monitorar SO/frontend: CPU, RAM, disco, relógio, serviços, HTTP/API, certificado, logs e unidades falhas.
- [ ] Vincular cada alerta operacional a owner, severidade, runbook e escalação; provar ao menos um evento sintético.

**Saída:** falha de coleta, capacidade, banco, frontend, proxy ou backup é detectável antes do usuário.

## 4. Qualificação antes do corte

- [ ] Testar em isolamento: login/logout, usuário comum, administrador limitado, usuário desativado, MFA, duas contas break-glass e Grafana read-only.
- [ ] Testar com host/proxy de laboratório: coleta, item, trigger, evento, incidente, TLS e ausência de ingestão duplicada.
- [ ] Confirmar frontend/API, gráficos históricos, mapas, dashboards e dados recentes.
- [ ] Executar teste de carga representativo e registrar NVPS, filas, busy processes, preprocessamento, housekeeping, MariaDB e I/O.
- [ ] Provar backup/restore integral duas vezes, sem passo manual secreto.
- [ ] Provar rollback da configuração endurecida.
- [ ] Gerar pacote externo à KVM8: infraestrutura/configuração como código, versões/digests, exportações saneadas, checksums, inventário de segredos sem valores, backup validado e runbooks.

**GO para Contabo somente se:** nenhum achado crítico/alto sem correção ou exceção; UAT funcional e de segurança aprovado; scripts/notificações reais bloqueados; RTO/RPO medidos; capacidade por 12 meses registrada; pacote reproduzível fora da KVM8; backup e rollback comprovados.

## 5. Corte para Contabo

- [x] Estratégia aprovada: nova VPS Contabo limpa e permanente para o Zabbix; preservar a atual como rollback por 7–14 dias e depois reutilizá-la, após reimage, no piloto Wazuh.
- [ ] Provisionar destino pelo código saneado; não copiar configuração histórica cegamente.
- [ ] Reduzir TTL, congelar mudanças, comunicar início e registrar hora-limite do rollback.
- [ ] Parar a coleta na origem aprovada, gerar dump final, validar gzip/SHA-256 e transferir por canal autenticado.
- [ ] Restaurar no destino, repetir contagens/schema/UAT e confirmar actions/media/connectors no estado aprovado.
- [ ] Alterar DNS/IP e reconectar proxies/agentes em ondas, sem dupla ingestão.
- [ ] Habilitar notificações reais somente após confirmar coleta estável e ausência de flood.
- [ ] Observar por duas horas: hosts recentes, fila, proxies, CPU/RAM/disco/I/O, banco, frontend/API, logs e notificações.

**Abortar e fazer rollback se:** hash/schema/import falhar; houver perda de dados; serviço crítico falhar; mais de 20% dos hosts não reportarem após quatro horas; fila/backpressure crescer persistentemente; frontend, banco ou proxies degradarem; ou ocorrer execução/notificação não autorizada.

## 6. Rollback

- [ ] Congelar alterações no destino e preservar logs/evidência da falha.
- [ ] Parar `zabbix-server`, agent e frontend do destino; impedir coleta duplicada.
- [ ] Reapontar DNS/IP e proxies/agentes para a origem/ponte preservada.
- [ ] Iniciar e validar MariaDB, Zabbix Server, Agent 2 e frontend na origem/ponte.
- [ ] Confirmar frontend/API, hosts recentes, proxies, fila e notificações.
- [ ] Comunicar rollback, registrar causa e abrir plano para nova janela.

**Saída:** operação restaurada na origem/ponte sem duas instâncias coletando.

## 7. Depois da migração — ajuste dependente da Contabo

- [ ] Ajustar MariaDB somente com métricas reais: buffer pool, redo/log, flush, I/O, conexões, temporárias e slow queries.
- [ ] Ajustar Zabbix somente com busy/queue/NVPS: caches, pollers, unreachable, trappers, pingers, preprocessors, LLD, history syncers, alerters e escalators.
- [ ] Ajustar filesystem/I/O, housekeeping e retenção; medir novamente após cada mudança.
- [ ] Revalidar TLS/allowlist dos proxies, firewall, HTTPS/headers, logs, backup/restore e monitoração externa.
- [ ] Reexecutar o relatório de segurança e comparar com a baseline; confirmar RBAC, tokens, scripts e canais.
- [ ] Finalizar Geomap, mapas e dashboards sobre dados saneados; validar desktop/mobile com operadores.
- [ ] D+1: cobertura, unreachable, alertas das 24 h, backup e disco.
- [ ] D+3: performance, crescimento do banco, relatórios e tendências.
- [ ] D+7: estabilidade geral; manter observação por 7–14 dias antes de liberar a origem.
- [ ] Após aceite: rotacionar segredos que existiram na KVM8, comprovar cópias externas e só então revogar/destruir a KVM8 e eventual host antigo conforme o plano.

## Aceite final

- [ ] Coleta e proxies estáveis, sem backlog crescente ou ingestão duplicada.
- [ ] Metas de `unsupported`, `unknown` e escalator cumpridas ou exceções com owner/prazo.
- [ ] RBAC, MFA, scripts, tokens e notificações validados pelo owner e Segurança.
- [ ] Inventário/tags/localização do piloto e mapas/dashboards úteis aprovados pelo NOC.
- [ ] Backup, restore e rollback comprovados; RTO/RPO registrados.
- [ ] Contabo reproduzível a partir de código, backup e runbooks externos.
- [ ] Riscos residuais possuem severidade, owner, prazo e aceite formal.

## Fontes locais reutilizadas

- `docs/execution/zabbix-transmutation-kvm8-plan.md`
- `docs/execution/zabbix-polish-baseline-2026-08-20.md`
- `docs/execution/zabbix-escalation-backlog-2026-08-20.md`
- `docs/execution/zabbix-security-access-audit-2026-08-21.md`
- `docs/execution/application-post-go-live-hardening.md`
- `docs/vps-capacity-and-sequencing-plan.md`
- `infra/docs/migration-checklist.md`
- `infra/scripts/zabbix-kvm8-native-restore.sh`
- `infra/scripts/zabbix-security-state-report.sh`
- `infra/ansible/playbooks/reconnect-proxies.yml`
- `infra/ansible/inventory/proxies.yml`
- `infra/ansible/roles/{common,mariadb,zabbix-server,zabbix-frontend,zabbix-proxy}`

## Artefatos antigos que não são evidência de produção sem revisão

- `infra/scripts/05-validate-migration.sh` contém identidade/senha padrão e contagens da migração Azure; não executar com defaults nem usar seus números como aceite atual.
- `infra/docs/migration-checklist.md` e `infra/docs/runbook.md` preservam o roteiro Azure e a conta `Admin`; reutilizar apenas os testes ainda válidos, substituindo origem, contagens e identidade pelo baseline atual.
