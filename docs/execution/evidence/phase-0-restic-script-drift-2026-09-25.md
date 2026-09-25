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
- Units do serviço e timer Zabbix já conferidas anteriormente e correspondem ao repositório.

## Diferenças funcionais relevantes

O script no Zabbix canônico ainda valida apenas os checksums listados e envia o backup com `--skip-if-unchanged`, sem a tag `ness-backup-set-<backup_set_id>`. A versão atual em `HEAD` também valida presença e sintaxe do ID, correspondência com o diretório e inclusão do manifesto em `SHA256SUMS`; a cópia recebe uma tag única do conjunto. Isso dá ao processo de restauração uma referência inequívoca ao backup local que originou o snapshot.

A versão AIOps já grava a tag por conjunto e validava seu manifesto, mas a versão corrente unifica e exige essas validações para ambos os datasets. As versões instaladas também executam retenção `forget --keep-last 14 --prune`; isso pode remover snapshots antigos quando a cópia for executada. O repositório/destino e o histórico de snapshots devem ser confirmados antes de iniciar a operação.

## Decisão operacional

1. Não substituir o script em produção às cegas nem executar a cópia enquanto o delta e o destino Restic não forem conciliados.
2. Na janela registrada de 22:00–00:00 BRT, validar o repositório exato e o estado do último snapshot; instalar a versão de `HEAD` somente após conferir que o caminho do repositório preserva o histórico esperado.
3. Executar uma única cópia correspondente ao conjunto local Zabbix vigente; verificar tag e `backup_set_id`, executar `restic check` e restauração isolada com checksums.
4. Só então habilitar o timer persistente, considerando o catch-up do `Persistent=true` e seu horário de calendário 05:30 BRT.

A credencial não foi lida nem exibida; nenhum valor secreto foi registrado. Nenhum arquivo em produção foi alterado.
