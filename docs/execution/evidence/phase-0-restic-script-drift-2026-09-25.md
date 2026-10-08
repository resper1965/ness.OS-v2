# Restic em produção — comparação de scripts (2026-09-25)

## Resultado

**Estado inicial em 2026-09-25: FAIL. Estado atualizado em 2026-09-26: cópia externa e restore isolado PASS para `20260925T220022-0300`.** A evidência abaixo preserva a análise de drift e o histórico das ações executadas; o resultado final está na seção “Execução autorizada”.

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

## Defeito na política de retenção, reproduzido em 26/09

O primeiro `restic forget --dry-run` com a política do script vigente (`--host zabbix-prod --tag ness-dataset-zabbix --group-by host,paths --keep-last 14`) separou cada snapshot porque cada caminho contém um `backup_set_id` diferente; o resultado marcou todos os seis como `last snapshot`, tornando a retenção ineficaz.

Corrigi `infra/scripts/ness-object-storage-restic.sh` para agrupar somente por host. O filtro explícito de host e a tag `ness-dataset-zabbix` mantêm a política restrita ao dataset Zabbix. A nova prévia agrupou os seis snapshots juntos e manteve os seis sob `keep 14`; nenhum seria removido nesta execução. Após o upload do conjunto atual serão sete, ainda sem remoções. Essa correção passa a limitar o histórico aos últimos 14 snapshots quando o limite for alcançado.

Base documental do agrupamento e do `--dry-run`: [Restic `forget`](https://github.com/restic/restic/blob/master/doc/060_forget.rst).
## Seleção de parent incremental

A execução aprovada em 26/09 registrou `no parent snapshot found`, processou 4,981 GiB e armazenou 4,907 GiB porque o caminho de origem contém um diretório diferente por `backup_set_id`, enquanto o `backup` usava o agrupamento padrão `host,paths`. A documentação do Restic confirma que esse agrupamento seleciona o parent por host e caminhos.

Atualizei o script versionado para passar `--group-by host` também ao `restic backup`, coerente com `forget`; o repositório e `NESS_BACKUP_HOST_ID` são dedicados ao dataset, e as tags preservam a identificação da execução. Essa revisão ainda precisa ser instalada e confirmada no próximo backup. Referência: [Restic file change detection](https://github.com/restic/restic/blob/master/doc/040_backup.rst).
## Falha e correção do verificador isolado em 26/09

`restic restore --verify` concluiu o snapshot `15a5ef41` com 11 entradas e 4,981 GiB verificados. Em seguida, o validador falhou porque o snapshot guarda os arquivos na raiz (`restic ls` mostra `/COMPLETED` e `/backup-set-manifest.json`); a restauração os colocou diretamente em `.../restored`, cujo basename não corresponde ao `backup_set_id`. O manifesto lido diretamente do snapshot (`restic dump`) contém o ID correto `20260925T220022-0300`. O cleanup automático removeu todo o staging; `/` manteve mais de 970 GiB livres.

Corrigi `infra/scripts/verify-zabbix-restic-restore.sh` para restaurar em `.../restored/<backup_set_id>`, satisfazendo também a validação do nome do conjunto. O restore completo e o teste isolado de MariaDB ainda precisam ser repetidos antes de aprovar o Gate.
## Decisão operacional inicial (superada)

1. Na janela registrada de 22:00–00:00 BRT, confirmar o repositório exato e ler o inventário de snapshots; anotar quantidade, snapshot mais recente, tags e host antes de qualquer escrita. Executar `forget --dry-run` com os mesmos filtros e política de 14; revisar a lista `remove` antes de permitir que o serviço aplique retenção/prune.
2. Instalar a versão atual de `HEAD` somente depois de confirmar que o caminho corresponde ao repositório Zabbix esperado e preserva o histórico existente.
3. Habilitar o timer persistente uma única vez para o catch-up. Não iniciar o serviço manualmente em paralelo. A execução espera o lock do backup local e então seleciona o conjunto concluído mais recente.
4. Verificar snapshot, tag e `backup_set_id`; executar `restic check` e restauração isolada com checksums. Manter o gate FAIL até todos passarem.
A credencial não foi lida nem exibida; nenhum valor secreto foi registrado. Na verificação inicial de 25/09, nenhum arquivo em produção foi alterado. A decisão foi superada pela execução autorizada abaixo.

## Execução autorizada em 26/09/2026

Na janela de sábado, o conjunto local `20260925T220022-0300` passou novamente
pela verificação de checksums. O timer persistente iniciou um único catch-up às
08:38 BRT. A cópia externa terminou com sucesso às 08:41:52 BRT, código zero,
snapshot `15a5ef41`, tags `ness-dataset-zabbix` e
`ness-backup-set-20260925T220022-0300`. Foram processados 4,981 GiB e
armazenados 4,907 GiB; a checagem de 5% e a checagem completa do repositório
terminaram sem erros. A prévia de retenção manteve os sete snapshots; nenhum foi
removido. O timer permanece habilitado/ativo, com próxima execução em
27/09/2026 às 05:30 BRT. O serviço não está executando uma segunda cópia.

A cópia inicial não encontrou parent porque o caminho muda a cada conjunto.
Instalei no Zabbix canônico a versão do script com `--group-by host` também no
`restic backup`, SHA-256
`5ab9f0c6057957766fd672575088229ad4db1be2c163264a0ab5492f15328a26`, modo
`root:root/0750`. A versão anterior foi preservada em
`/root/ness-object-storage-restic.20260926.preparent`, modo `root:root/0750`.
O reaproveitamento do parent só será comprovado no próximo backup agendado.

O verificador de restauração isolada foi corrigido para restaurar em
`restored/<backup_set_id>`, hash instalado
`df00e16f…`, modo `root:root/0750`. A segunda restauração Restic verificou 11
entradas e 4,981 GiB sem erro e selecionou o conjunto e snapshot esperados.
A importação do dump no MariaDB temporário sem rede terminou após cerca de
1h54m. Os processos temporários e os diretórios `run-*` foram removidos pelo
cleanup; `/` ficou com 977 GiB livres, e MariaDB/Zabbix de produção permaneceram
ativos. Contudo, o cliente SSH deixou de entregar a saída do verificador e o
código final após o término dos processos. Sem a saída com as contagens das
tabelas/hosts/itens/triggers/templates e `dbversion`, não é possível afirmar
`isolated_restore=PASS` ou `external_restore=PASS`; essa evidência continua
pendente e a execução não será repetida automaticamente.

Por isso, iniciei uma única repetição controlada às 11:06 BRT. Ela roda
desacoplada da sessão SSH, grava a saída em
`/var/log/ness-zabbix-restic-restore-verify-20260926-rerun.log` e grava o código
de término em `/run/ness-zabbix-restic-restore-verify-20260926-rerun.status`.
No início, o log/status ainda não continham resultado; MariaDB e Zabbix de
produção estavam ativos. A cópia externa continua aprovada; a restauração fica
pendente até ler o status zero e as contagens desse log.

O token/segredos do EnvironmentFile não foram exibidos nem registrados.

## Resultado final da repetição desacoplada em 26/09

A repetição terminou com status `0`. O verificador confirmou `isolated_restore=PASS`
e `external_restore=PASS` para o conjunto `20260925T220022-0300` e o snapshot
Restic completo `15a5ef41be82e65eda4fc5be285d948a1daeccd0c68f0a46ceb9090b168c190e`.
O banco temporário identificou Zabbix `7.0.27`, MariaDB
`10.11.18-MariaDB-deb12`, 203 tabelas, 685 hosts, 64.226 itens, 26.697 triggers,
362 templates e `dbversion.mandatory=7000000`.

Depois da conclusão, o diretório do banco de teste e o staging Restic estavam
ausentes; MariaDB e Zabbix de produção continuaram ativos, e o volume tinha
977 GiB livres. O timer externo continuou habilitado/ativo. A cópia e a
restauração externa do Zabbix estão aprovadas para este conjunto. O reaproveitamento
do parent incremental permanece pendente até a próxima execução agendada.
