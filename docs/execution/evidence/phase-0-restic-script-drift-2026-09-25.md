# Restic em produção — comparação de scripts (2026-09-25)

## Resultado

**Gate de cópia externa Zabbix: permanece FAIL.** Nenhum comando Restic foi executado nesta verificação. A comparação foi feita lendo os scripts em disco e confrontando seus SHA-256 com o histórico Git.

## Hosts no escopo

- Zabbix canônico: `144.91.72.202` (`ness_admin`, SSH 2222).
- AIOps: `144.91.115.242` (`root`, SSH 22).
- `npentest` permanece fora do escopo.

## Proveniência dos scripts

- `infra/scripts/ness-object-storage-restic.sh` em `HEAD` tem SHA-256 `afa3f1df214df849b35fe9dbf9a945415d8138083da845596c34e5be49c6727c`.
- Zabbix instalado `/usr/local/sbin/ness-object-storage-restic`: `1fe4ddf226084fc7817fe0f57da32a024466c9d5f7f3a3356adbb4da85efc3de`, idêntico ao pai do commit `78b365a` (mesmo blob de script presente em `bfe3d6d`).
- AIOps instalado no mesmo caminho: `2e968b34b5afed771566d8576544adf0bf05a9fdd7df44e248073f16a016a200`, idêntico ao script do commit `78b365a`.
- O commit `fdb4442` alterou o script após esses deploys, mas essa versão ainda não está instalada em nenhuma das duas VPS.
- Units do serviço e timer Zabbix já conferidas anteriormente e correspondem ao repositório.- As units e timers de produção correspondem ao repositório. O script instalado no Zabbix está `root:root/0755`; no AIOps, `root:root/0700`. O instalador de UAT versionado define `root:root/0750`. Na reconciliação do Zabbix, instalar com `0750` para remover leitura/execução por outros usuários e manter execução para root/grupo; manter AIOps em `0700`.

## Último histórico externo encontrado no journal

Leitura somente do journal do Zabbix canônico, sem executar Restic: em 30/08/2026 o serviço concluiu com sucesso, `restic check` reportou nenhum erro e a listagem continha cinco snapshots `ness-dataset-zabbix` do host `zabbix-prod`. O mais recente era `30c8f2d8`, criado em 30/08 05:31:25 BRT, ligado ao conjunto local `20260829T220005-0300` (5,609 GiB). Portanto o repositório já existe e o comando `init` não deve ser usado; a cópia atual ainda não está comprovada.

O arquivo `stamp-ness-zabbix-object-storage-backup.timer` tinha mtime de 30/08 05:30 BRT. O timer usa `Persistent=true`; a página man local de systemd 252 confirma que ativar um timer com execuções calendarizadas perdidas inicia o serviço imediatamente. Na janela, esperar esse catch-up; o serviço fará lock/wait pelo backup local de 22:00. Não iniciar o serviço manualmente em paralelo.
## Revalidação em 19:14 BRT

- Conjunto local mais recente do Zabbix: `20260925T162305-0300`; todos os arquivos de `SHA256SUMS`, incluindo `db/dbzabbix.sql.gz` (5,1 GB), passaram em nova validação. O manifesto corresponde ao ID do diretório.
- O EnvironmentFile define `NESS_BACKUP_HOST_ID=zabbix-prod`, `RESTIC_KEEP_LAST=14` e `RESTIC_CHECK_PERCENT=5`.
- AIOps define `NESS_BACKUP_HOST_ID=aiops-prod` e a mesma política de retenção/check. Os namespaces por host são distintos; `npentest` não foi consultada.
- O timer externo Zabbix segue `disabled/inactive`; não houve consulta nem operação Restic antes da janela.
## Diferenças funcionais relevantes

O script no Zabbix canônico ainda valida apenas os checksums listados e envia o backup com `--skip-if-unchanged`, sem a tag `ness-backup-set-<backup_set_id>`. A versão atual em `HEAD` também valida presença e sintaxe do ID, correspondência com o diretório e inclusão do manifesto em `SHA256SUMS`; a cópia recebe uma tag única do conjunto. Isso dá ao processo de restauração uma referência inequívoca ao backup local que originou o snapshot.

A versão AIOps já grava a tag por conjunto e validava seu manifesto, mas a versão corrente unifica e exige essas validações para ambos os datasets. As versões instaladas também executam retenção `forget --keep-last 14 --prune`; isso pode remover snapshots antigos quando a cópia for executada. O repositório/destino e o histórico de snapshots devem ser confirmados antes de iniciar a operação.

## Decisão operacional

1. Na janela registrada de 22:00–00:00 BRT, confirmar o repositório exato e ler o inventário de snapshots; anotar quantidade, snapshot mais recente, tags e host antes de qualquer escrita. Executar `forget --dry-run` com os mesmos filtros e política de 14; revisar a lista `remove` antes de permitir que o serviço aplique retenção/prune.
2. Instalar a versão atual de `HEAD` somente depois de confirmar que o caminho corresponde ao repositório Zabbix esperado e preserva o histórico existente.
3. Habilitar o timer persistente uma única vez para o catch-up. Não iniciar o serviço manualmente em paralelo. A execução espera o lock do backup local e então seleciona o conjunto concluído mais recente.
4. Verificar snapshot, tag e `backup_set_id`; executar `restic check` e restauração isolada com checksums. Manter o gate FAIL até todos passarem.
A credencial não foi lida nem exibida; nenhum valor secreto foi registrado. Nenhum arquivo em produção foi alterado.
