# Verificação dos backups noturnos — 21/08/2026

## Resultado

Os dois backups locais agendados em 20/08/2026 terminaram com código 0 e tiveram seus checksums recalculados com sucesso em 21/08/2026. A estrutura dos dumps e arquivos compactados também foi lida sem erro. A restauração isolada AIOps foi concluída posteriormente; a do Zabbix permanece reservada para a janela de manutenção. A Hostinger KVM8 descartável já foi preparada com Debian 12, Zabbix 7.0.27 e MariaDB 10.11.18 para receber o dump com as mesmas versões da origem.

## Zabbix — 22:00 BRT

- Unit: `ness-zabbix-emergency-backup.service`.
- Execução: 20/08/2026 22:00:25 a 23:11:40 BRT.
- Resultado systemd: `success`, `ExecMainStatus=0`.
- Artefato: `/var/backups/zabbix/emergency/20260820T220025-0300`.
- Tamanho: 4,7 GiB; dump comprimido do banco: 5.004.030.320 bytes.
- `sha256sum -c`: todos os arquivos listados retornaram `OK`.
- `gzip -t`: dump do MariaDB legível.
- `tar -tzf`: configuração e pacote de evidências legíveis.
- Permissões: diretórios `700` e arquivos `600`, sem exceções de grupo/outros.
- Serviços antes/depois e na verificação: Zabbix Server, MariaDB, Apache, Zabbix Agent 2 e Fail2ban ativos.
- Capacidade após o backup: aproximadamente 1,1 TiB livre, 5% utilizado.
- O backup acima veio da unit emergencial transitória. A rotina recorrente `ness-zabbix-backup.timer` foi posteriormente instalada, está `enabled/active` e tem a primeira execução prevista para 21/08/2026 às 22:00 BRT; a unit usa baixa prioridade de CPU/I/O e timeout de três horas.

### Primeira execução recorrente e correção — 22/08/2026

A primeira execução do timer ocorreu em 21/08/2026 às 22:00:19 BRT, mas falhou antes de iniciar o script: `status=226/NAMESPACE`. O journal mostrou que `ProtectSystem=strict`/`ReadWritePaths` não conseguiu montar `/var/backups/zabbix/nightly` porque o diretório ainda não existia. Em 22/08, dentro da janela excepcional de dia inteiro autorizada, foi aplicada a correção mínima: criação prévia do diretório como `0700 root:root`, preservando o hardening e o script. A sintaxe e a executabilidade do script foram validadas.

A unit foi reiniciada às 12:11:54 BRT e concluiu às 13:08:22 BRT com `Result=success` e `ExecMainStatus=0`. O conjunto `/var/backups/zabbix/nightly/20260822T121154-0300` contém `COMPLETED`; o dump tem 5.109.690.574 bytes. O manifesto e a verificação independente `gzip -t` passaram, com SHA-256 `6c4a9ce636d0adb54747dea675f7c2d502f6f42b003365eeff4308237e552f6c`. Zabbix Server, MariaDB, Apache, Agent 2 e Fail2ban permaneceram ativos e não havia units falhas.

### Transferência e restauração isolada — 22/08/2026

O dump foi transferido para `/var/lib/ness-os/restore-input/dbzabbix-20260822T121154-0300.sql.gz`. O transferidor recalculou origem e destino e registrou `transfer=PASS`, ambos com o SHA-256 acima. A cópia parcial foi renomeada somente depois da validação.

O restore nativo carregou aproximadamente 35 GB em MariaDB 10.11.18. No encerramento, a saída por `tee` perdeu o consumidor SSH e retornou `141` (SIGPIPE); o trap fail-closed interrompeu qualquer processo eventual, manteve o server mascarado e neutralizou novamente actions/media/connectors. O banco não foi descartado. Esse evento deixou uma evidência de sucesso vazia e `restore=FAIL_CLOSED`, portanto não foi tratado como PASS por inferência.

Foi então executado o verificador independente, em modo somente leitura e com base direta no banco após fail-closed. Resultado `post_restore_verification=PASS` às 15:42:32 BRT:

- 203 tabelas, 674 hosts/templates, 60.250 itens e 24.520 triggers;
- `dbversion=7000000`;
- zero actions, media types e connectors ativos;
- MariaDB ativa e somente `127.0.0.1:3306`;
- Zabbix Server `inactive/masked`, sem processo e sem listener 10051;
- Apache e Agent 2 inativos, NTP sincronizado, zero unit falha;
- nenhuma conexão estabelecida com agentes/proxies/portas 10050/10051;
- banco restaurado com cerca de 35 GB, dump preservado com 4,8 GB e 327 GB livres;
- evidência root-only `/var/lib/ness-os/restore-evidence/post-restore-verification-20260822T154232-0300.txt`, SHA-256 `c88745e36f9af8441c3dd64559e69f859f645f167402421b40c791aa69d66460`.

O runner foi corrigido para gravar a evidência em arquivo temporário, aplicar permissão e fazer `mv` atômico antes de qualquer saída ao SSH. Seu hash local/remoto passou a `83bc4b519b41bad84e3d345d9afe8bdeaaa036ad54e10e0abcbfbc6f9ca82ecb`; o verificador independente local/remoto ficou em `424e42e4d0b3cb51646055e06ef63d52464153b3a02d9d430890ec2eed324d1c`. A perda do relatório impediu medir um RTO automatizado confiável nesta execução; a próxima prova recorrente deve confirmar a gravação atômica e registrar o tempo sem depender do canal SSH.

## AIOps — 23:00 BRT

- Unit: `ness-aiops-backup.service`; timer recorrente permanece ativo para 23:00 BRT.
- Execução: 20/08/2026 23:00:03 a 23:03:04 BRT.
- Resultado systemd: `success`, `ExecMainStatus=0`.
- Artefato: `/opt/n-infraops/backups/nightly/20260820T230004-0300`.
- Tamanho: 30 MiB.
- Conteúdo: globals PostgreSQL, quatro bancos em formato custom, dump completo MariaDB/GLPI, configuração e volumes persistentes.
- `sha256sum -c`: todos os arquivos listados retornaram `OK`.
- `gzip -t`, `tar -tzf` e `pg_restore -l`: passaram para todos os artefatos correspondentes.
- Marcador `COMPLETED` presente.
- Docker, SSH e Fail2ban ativos; 14 contêineres em execução, incluindo todos os que possuem healthcheck como `healthy`.
- Capacidade após o backup: aproximadamente 339 GiB livre, 11% utilizado.

### Ressalvas e correção aplicada

O `pg_dump` alertou sobre constraint circular na tabela interna `continuous_agg` do TimescaleDB. O dump é estruturalmente legível, mas a restauração completa deve prever `--disable-triggers`/ordem adequada ou, preferencialmente, confirmar a migração já planejada para PostgreSQL 16 + pgvector sem TimescaleDB Community.

Os arquivos gerados por contêiner auxiliar ficaram inicialmente `644` dentro de diretório `755`. Em 21/08/2026:

- o backup foi normalizado recursivamente para retirar permissões de grupo/outros;
- o diretório `nightly` e o diretório da execução ficaram `700 root:root`;
- o script passou a criar o diretório raiz como `700` e executar `chmod -R go-rwx` antes do marcador `COMPLETED`;
- o script instalado e o versionado ficaram com o mesmo SHA-256: `2dd159d36158c75067d7cbe2cba4e2692bd843ab669eac3abcefb7ff573cd49d`;
- a sintaxe Bash foi validada antes da instalação.

### Restauração isolada AIOps

O conjunto `/opt/n-infraops/backups/nightly/20260820T230004-0300` foi restaurado em contêineres e volumes temporários, sem conexão com os serviços de produção. O teste confirmou:

- Authentik: 366 relações;
- Evolution: 63 relações;
- ness.OS/Hub: 87 relações;
- banco `postgres`: 26 relações;
- 16 roles PostgreSQL;
- GLPI: 466 tabelas MariaDB;
- duas tabelas relacionadas a projetos;
- 12 arquivos/volumes persistentes restaurados;
- remoção dos recursos temporários ao final.

Resultado: `isolated_restore=PASS`. Arquivos de cache GLPI apresentaram timestamps futuros durante a extração; isso não impediu a restauração e deve ser tratado no polimento, preferencialmente excluindo ou regenerando cache.

Antes da fixação e rotação do GLPI, foi produzido ainda o backup `/opt/n-infraops/backups/nightly/20260821T122917-0300`, com marcador `COMPLETED` e unit concluída com sucesso.

Após a rotação GLPI e a aplicação dos digests em todos os serviços de terceiros, foi produzido o conjunto `/opt/n-infraops/backups/nightly/20260821T135439-0300`. A unit retornou `success`/status 0; os 18 artefatos listados em `SHA256SUMS` retornaram `OK`. Uma nova restauração isolada desse conjunto confirmou novamente 366/63/87/26 relações nos quatro bancos PostgreSQL, 16 roles, 466 tabelas GLPI, duas tabelas de projeto e 12 arquivos/volumes. Resultado final: `isolated_restore=PASS`, com remoção dos recursos temporários.

Após remover e rotacionar os defaults PostgreSQL/Auth­entik, foi criado o conjunto final `/opt/n-infraops/backups/nightly/20260821T142635-0300`. A unit retornou `success`/status 0, os checksums passaram e a restauração isolada confirmou 366/63/87/26 relações, 16 roles, 466 tabelas GLPI, duas tabelas de projeto e 12 arquivos/volumes. Resultado: `isolated_restore=PASS`.

## Pendências para caracterizar backup recuperável

1. **Concluído em 24/08/2026:** conjuntos AIOps e Zabbix copiados de forma criptografada para Object Storage, com `check` e restore externo comprovados.
2. Medir RTO/RPO automatizado em uma prova futura com a evidência atômica; a restauração Zabbix e a validação independente do conteúdo já passaram.
3. Registrar dependências/ordem de subida para o cutover; nenhuma subida do Zabbix ocorreu neste Gate.
4. Definir retenção e expurgo automático com proteção contra remoção do último backup válido.
5. Definir retenção/expurgo dos conjuntos locais Zabbix sem remover o último válido. A retenção externa já usa `--keep-last 14` e preserva ao menos um snapshot.

### Tooling de Object Storage preparado — 22/08/2026

O pipeline local de cópia externa foi preparado, mas **não implantado**, em [`../../infra/scripts/ness-object-storage-restic.sh`](../../infra/scripts/ness-object-storage-restic.sh) e nas units `ness-*-object-storage-backup.*`. Ele usa Restic/S3, repositórios isolados por host/dataset, exige conjunto `COMPLETED` com `SHA256SUMS` válido, criptografa antes do envio, verifica uma amostra de dados, mantém ao menos um snapshot e falha fechado sem configuração. As opções foram conferidas contra a documentação Restic atual e os testes estáticos passaram.

Naquele momento, a ativação estava bloqueada até contratar o Object Storage, obter endpoint/bucket/chaves, gerar a senha Restic no cofre, instalar Restic nos dois hosts, inicializar deliberadamente cada prefixo e provar upload/check/restore. Nenhuma credencial foi inventada ou incluída nos arquivos.

### Revalidação do bloqueio — 23/08/2026 00:16 BRT

Uma verificação somente de presença na VPS AIOps confirmou que `/etc/ness-os/backup-s3.env` continua ausente e que Restic ainda não está instalado. Nenhum valor secreto foi lido ou exibido. A VPS Zabbix não foi consultada porque a janela de 22/08/2026 já havia encerrado; o restore e a transferência aprovados não foram repetidos. O Gate permanece bloqueado até o provedor disponibilizar endpoint HTTPS, bucket, access key, secret key e até a criação segura da senha Restic.

### Revalidação do bloqueio — 24/08/2026 14:32 BRT

O host de execução continua sem `/etc/ness-os/backup-s3.env`. Foi tentada uma consulta somente leitura à API Contabo usando as credenciais OAuth preservadas, sem imprimir valores; a autenticação foi recusada e, por isso, a existência de Object Storage contratado não pôde ser comprovada. Nenhuma consulta intensiva foi feita no Zabbix fora da janela, e transferência/restore já aprovados não foram repetidos. O bloqueio permanece explícito até disponibilização de credenciais Contabo válidas e dos cinco parâmetros do repositório externo: endpoint HTTPS, bucket, access key, secret key e senha Restic.

Revalidação em 24/08/2026 15:32 BRT: nenhum `/etc/ness-os/backup-s3.env` nem configuração temporária equivalente foi encontrado no host de execução. Upload, `restic check` e restore externo permanecem bloqueados; nenhuma credencial foi inventada e os restores locais aprovados não foram repetidos.

Na sequência, a inspeção autenticada do painel Contabo comprovou que o produto já está contratado: `ninfraops - Zabbix Store`, região EU, estado `READY`, 250 GB e autoscaling desativado. O único bucket, `zabbix-storage`, está vazio, mas aparece com acesso público ativo. O novo gerenciamento de usuários não possui usuário cadastrado; portanto ainda não há credencial S3 dedicada aprovada para o Restic. Nenhum bucket, usuário ou permissão foi alterado durante a inspeção.

Com autorização explícita posterior, foi criado o bucket privado `ness-os-backup-eu-2026`, desativado o compartilhamento público do bucket vazio `zabbix-storage` e registrado `resper@bekaa.eu` com somente `S3 Read and Write` e 2FA. A conta já existia e agora aparece habilitada. Em seguida, foi criado o usuário nominal `iaraujo@ness.com.br`, também somente com `S3 Read and Write`, sem privilégios administrativos ou de faturamento, ativo e com 2FA obrigatório. Ambos os buckets terminaram com acesso público `Inativo`. O usuário de Ismael está com convite pendente; nenhuma credencial S3 foi copiada ou inventada, e nenhum upload foi iniciado.

Na continuação de 24/08/2026, o painel confirmou o reenvio do e-mail de definição de senha para Ismael. O script `ness-object-storage-restic.sh` passou novamente na validação de sintaxe e o conjunto `infra/tests/test-object-storage-restic-tooling.sh` retornou `PASS`. A validação local das units apontou somente a ausência esperada do executável de destino `/usr/local/sbin/ness-object-storage-restic`, que será instalado nos hosts durante a ativação; nenhuma unit foi implantada prematuramente.

Ismael concluiu a ativação: `iaraujo@ness.com.br` aparece **Habilitado**, com 2FA **Habilitado** e somente `S3 Read and Write`. A sessão de inspeção permanece autenticada como Ricardo e mostra a credencial S3 do próprio usuário logado. Para manter segregação e rastreabilidade, essa credencial administrativa não será usada; a continuidade exige uma sessão separada como Ismael para obter e instalar a credencial nominal sem exibição em logs ou documentação.

Em sessão isolada como Ismael, o segredo S3 foi regenerado após autorização explícita; o painel confirmou sucesso. Chave e segredo foram copiados sem exibição, a área de transferência foi limpa e uma senha Restic independente foi gerada. Os arquivos host-specific de staging foram gravados fora do repositório em `/home/resper/.config/ness-os/`, modo `0600`, e sua estrutura foi validada sem imprimir valores. A implantação no Zabbix aguarda a janela 22:00–00:00 BRT. Na AIOps, tentativas somente de autenticação com as chaves nominais locais falharam; não foi usado acesso `root` ou senha como atalho.

### Cópia externa AIOps comprovada — 24/08/2026 14:49 BRT

Após autorização explícita, a senha `root` da instância AIOps `vmi3409271` (`144.91.115.242`) foi redefinida no painel Contabo e mantida somente em arquivo local `0600`, fora do repositório. O console confirmou a sessão `root`; a chave já autorizada no host correspondeu ao fingerprint da `id_ed25519_stackvps`. O acesso nominal voltou a funcionar como `ness_admin`, membro de `sudo`, com `sudo -n` aprovado. Nenhuma senha ou chave privada foi registrada nesta evidência.

O VNC foi desabilitado ao final da recuperação. A revalidação após reload do painel mostrou `VNC desativado` e informou que uma nova senha será obrigatória para eventual reabilitação.

O Restic oficial foi instalado por `restic self-update --output /usr/local/bin/restic`; a assinatura GPG da distribuição foi validada pelo próprio updater. Versão efetiva: `0.19.1`, com suporte a `--retry-lock`. O script versionado foi ajustado para criar o cache root-only e usar `flock -w 14400`, compatível com Debian 12; sintaxe e testes estáticos passaram antes do redeploy.

Resultado da cópia:

- origem: conjunto local `20260823T230000-0300`, com marcador `COMPLETED`;
- 20 artefatos listados em `SHA256SUMS`: todos `OK` antes do upload;
- destino: prefixo isolado `ness-os/aiops-prod/aiops` no bucket privado;
- snapshot Restic: `5f67fdff`, 29,482 MiB;
- `restic check --read-data-subset=5%`: sem erros;
- `forget --keep-last 14 --prune` preservou o snapshot válido;
- `restic check` final: sem erros.

A prova de recuperação restaurou o snapshot externo mais recente em `/var/tmp/ness-aiops-restic-restore.*`, usando `restic restore --verify`. Foram restaurados e verificados 20 arquivos, totalizando 30.926.734 bytes; todos os checksums internos retornaram `OK`. O caminho temporário foi validado antes da remoção e não restou diretório de restore. O timer `ness-aiops-object-storage-backup.timer` foi habilitado e ficou agendado diariamente para 00:30 BRT, após o backup local das 23:00.

O fluxo externo da AIOps foi encerrado sem repetir o restore local já aprovado.

### Cópia externa Zabbix comprovada — 24/08/2026 15:29 BRT

Ricardo autorizou uma janela excepcional imediata. O conjunto `20260823T220020-0300`, produzido com sucesso pela rotina recorrente, foi selecionado por ser o `COMPLETED` mais recente. Zabbix Server, MariaDB e Apache permaneceram ativos durante toda a operação; nenhum serviço de produção foi reiniciado ou pausado.

O Restic oficial foi instalado e atualizado para `0.19.1` com assinatura GPG verificada pelo updater. O ambiente S3 foi instalado como `/etc/ness-os/backup-s3.env`, `root:root`, modo `0600`, sem exibir valores. O tooling e as units implantados são os arquivos versionados e já testados.

Resultado da cópia:

- origem: `/var/backups/zabbix/nightly/20260823T220020-0300`;
- oito artefatos listados em `SHA256SUMS`: todos `OK` antes do envio;
- destino: prefixo isolado `ness-os/zabbix-prod/zabbix` no bucket privado;
- snapshot Restic: `3f3f2f53`;
- volume lógico: 4,821 GiB; 4,748 GiB armazenados;
- `restic check --read-data-subset=5%`: 14/14 packs, sem erros;
- `forget --keep-last 14 --prune` preservou o snapshot válido;
- `restic check` final: sem erros.

A prova de recuperação restaurou o snapshot externo mais recente em `/var/tmp/ness-zabbix-restic-restore.*`, usando `restic restore --verify`. O Restic restaurou oito arquivos/5.176.272.566 bytes e verificou os oito arquivos; o `sha256sum -c SHA256SUMS` aprovou inclusive `db/dbzabbix.sql.gz`. O caminho temporário foi validado e removido ao final, sem alterar o conjunto local ou o snapshot remoto.

O timer `ness-zabbix-object-storage-backup.timer` foi habilitado para 23:30 BRT. Caso o backup local das 22:00 ainda esteja em execução, ambos compartilham o lock `/run/lock/ness-zabbix-backup.lock` e a cópia espera até 14.400 segundos, evitando leitura parcial. Ao final, Zabbix Server, MariaDB e Apache estavam `active`; SSH root, senha e keyboard-interactive continuavam desabilitados.

Resultado do Gate 0 de backup externo: **PASS para AIOps e Zabbix**. Transferência e restores locais anteriormente aprovados não foram repetidos.
