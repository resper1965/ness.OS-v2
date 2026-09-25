# Fase 0 — evidência de recuperação do Zabbix

**Resultado: FAIL parcial** — o backup local e a restauração isolada passaram; a cópia externa atual e o login técnico somente leitura não foram comprovados.

## Identificação

- VPS canônica Zabbix/NOC: `infra-zabbix`, `144.91.72.202`, hostname `zabbix-srv01`.
- O destino `nes-os-zabbix-pr-01` (`169.58.234.9`) consta no plano de migração como destino de UAT/cutover pendente. A recuperação desta evidência ocorreu na origem canônica.
- A VPS `npentest` ficou fora do escopo.
- Conjunto local: `/var/backups/zabbix/nightly/20260925T131415-0300`.
- `backup_set_id`: `20260925T131415-0300`.
- SHA-256 de `backup-set-manifest.json`: `259a42bbdeac58fbdb730f834a75e785845868c5b01fb6e236fd3beca6432655`.
- Manifesto: Zabbix `7.0.27`, MariaDB `10.11.18`, schema obrigatório `7000000`, banco `dbzabbix`.

## Backup local e restauração

- Backup local iniciado em `2026-09-25T16:14:15Z` e concluído em `2026-09-25T17:10:43Z` (56 min 28 s); `ness-zabbix-backup.service` terminou com `Result=success`, `ExecMainStatus=0`.
- `COMPLETED` foi criado após gzip, tar, manifesto e SHA-256 serem validados. Os sete arquivos cobertos por `SHA256SUMS` passaram; tamanho total aproximado: `5.1 GiB`.
- Conjunto validado em modo isolado em `2026-09-25T17:28:49Z`–`2026-09-25T19:23:05Z` (aprox. 1 h 54 min). O dump foi importado em MariaDB `10.11.18` sob diretório e socket temporários privados, com `--skip-networking`.
- Resultado da restauração: `isolated_restore=PASS`, `backup_set_id=20260925T131415-0300`.
- Contagens: 203 tabelas, 685 hosts, 64.211 itens, 26.686 triggers, 362 templates; `dbversion_mandatory=7000000`.
- Limpeza: processo temporário encerrado e diretório `run-*` removido. MariaDB, Zabbix Server, Apache e Zabbix Agent 2 permaneceram ativos; `/` manteve mais de 950 GB livres.

## Agendamentos e itens pendentes

- Timer local: habilitado e ativo; `OnCalendar=*-*-* 22:00:00 America/Sao_Paulo`, `Persistent=true`, precisão de 1 minuto.
- Ao habilitá-lo às `2026-09-25 16:23:05 -03`, systemd iniciou uma captura imediata de recuperação porque havia execuções persistentes atrasadas. Essa segunda execução está em andamento nesta evidência; o conjunto manual acima já havia concluído e sido restaurado.
- Timer externo: instalado e recarregado, mas permanece desabilitado. A execução externa não foi iniciada porque uma execução anterior de diagnóstico imprimiu variáveis do EnvironmentFile Restic/S3 via xtrace. A rotação das credenciais e a preservação de acesso aos snapshots existentes aguardam resposta do usuário. Nenhum valor foi gravado neste arquivo.
- API técnica: o estado atual observado não prova login somente leitura. `svc_ninfraops_api` está associado ao papel `n.infraops Hub Integration`, com `readonly=0`; a whitelist inclui `event.acknowledge`. Isso diverge da documentação anterior que descrevia `n.infraops API Read Only`. Nenhuma permissão de produção foi alterada nesta tarefa.
- Portanto, backup externo dentro de 24 h e autenticação API somente leitura permanecem `FAIL / não comprovados`; não considerar o gate da Fase 0 aprovado.

## Versões implantadas e testes locais

- Script de backup, validador de restauração, verificador Restic e timers foram instalados no VPS; as units foram recarregadas.
- `bash infra/tests/test-zabbix-upgrade-safety.sh` → PASS (manifesto, versão, checksum, conjunto parcial e caminho de restauração local).
- `bash infra/tests/test-object-storage-restic-tooling.sh` → PASS.
- `bash -n` nos scripts Zabbix/Restic alterados → PASS.
- `git diff --check` no escopo da tarefa → PASS.

Nenhum valor secreto foi incluído nesta evidência.
