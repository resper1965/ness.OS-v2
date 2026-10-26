# Recuperação — evidências de 08/09/2026

Objetivo integral permanece ativo. Esta execução prova a restauração descrita
abaixo; não declara concluído o DR de todos os sistemas ou a recuperação dos
usuários do cofre.

## AIOps, Authentik, Evolution e GLPI

Backup usado: `/opt/n-infraops/backups/nightly/20260907T230010-0300`.
Checksums aprovados antes da importação. Teste em containers e volumes novos,
sem rede e sem portas publicadas, usando as imagens das bases de produção.
Containers/volumes de produção não foram montados nos testes.

O verificador anterior descartava proprietários com `--no-owner` e ignorava
erros de restauração dos papéis. Foi corrigido para criar administrador
temporário de nome único, restaurar papéis com `ON_ERROR_STOP=1` antes das bases
e usar `pg_restore --create --exit-on-error`, preservando proprietários.
Também passou a resolver o caminho canônico do backup e a impedir concorrência.

Resultado do teste rigoroso, **174 segundos**:

| Base | Tabelas/relações de usuário | Proprietário |
| --- | ---: | --- |
| authentik | 340 | nessops |
| evolution | 37 | nessops |
| nessops | 87 | nessops |
| postgres | 0 | nessops |
| glpi (MariaDB) | 466 tabelas | restauração do dump completo |

Papéis PostgreSQL: 16 após restauração. GLPI contém as duas tabelas esperadas
de projetos e tarefas. Doze arquivos de configuração/volumes foram extraídos.
O resultado anterior tinha 26 relações adicionais em algumas bases porque o
método criava bancos com extensões do template de inicialização; a nova prova
usa a criação registrada no próprio dump.

Log protegido: `/var/lib/ness-os/hub-integration/restore-strict-20260908.log`.
Script: `infra/scripts/aiops-isolated-restore-test.sh`, instalado em
`/usr/local/sbin/ness-aiops-isolated-restore-test`.

Limites: essas aplicações não foram iniciadas sobre todas as bases restauradas;
não foi simulada reconstrução de servidor, DNS, TLS ou acesso de usuário.
O backup é anterior às alterações hub/GLPI de 08/09; a prova não elimina a
necessidade de nova cópia consistente da implantação atual.

## Psono: backup remoto, base e aplicação

Backup recuperado do repositório Restic remoto existente:
`20260908T125709-0300`. Arquivos e checksums validados.

O verificador anterior fazia apenas `pg_restore --list`. Agora carrega o dump
em PostgreSQL isolado, preserva a configuração criptográfica do backup e inicia
a imagem real do Psono. A aplicação compartilha somente o namespace de rede
do banco descartável (`network=none`), sem acesso a SMTP, serviços externos ou
produção. Apenas endereço/credenciais do banco e hosts permitidos são adaptados
à execução isolada.

Resultado em **65 segundos**, incluindo download, restauração e inicialização:

- 51 tabelas carregadas e consultadas;
- 2 usuários, 6 datastores e 6 registros de segredo presentes no backup;
- `/server/info/` retornou HTTP 200 na aplicação restaurada;
- assinatura da resposta validada;
- chave pública anunciada corresponde à configuração criptográfica do backup;
- containers, volumes e arquivos temporários removidos ao término.

Log: `/var/lib/ness-os/hub-integration/psono-restore-app-20260908.log`.
Script: `infra/psono/scripts/restore-verify.sh`, instalado em
`/opt/ness-os-psono/scripts/restore-verify.sh`.

Limite: não houve login de usuário nem descriptografia de um segredo pessoal na
instância restaurada. Contagens e inicialização não substituem essa prova.
Os tempos medidos são tempos deste ensaio, não compromissos de RTO contratual.

## Rotina e rollback

Verificações semanais instaladas, habilitadas e validadas por
`systemd-analyze verify`:

- `ness-aiops-restore-verify.timer`: domingo, 04:30, atraso aleatório até 10 min;
- `ness-psono-restore-verify.timer`: domingo, 05:15, atraso aleatório até 10 min.

Horário local do servidor: America/Sao_Paulo. Próximas execuções confirmadas
para 13/09/2026, 04:33 e 05:21. Ambas têm lock contra concorrência, timeout de
30 minutos e diagnóstico via journal da unit. Execuções manuais dos scripts
foram aprovadas; o disparo futuro dos timers ainda não ocorreu.

Scripts anteriores guardados em `/opt/n-infraops/rollback/recovery-20260908/`.
Rollback: desabilitar os dois timers e restaurar os dois scripts anteriores.
Nenhuma restauração de dados de produção é necessária para reverter a mudança.

## Recuperação de identidades ainda aberta

Relatório Psono em 08/09, 18:11 BRT:

| Responsável já cadastrado | Ativo / já acessou | MFA | Códigos de recuperação |
| --- | --- | --- | ---: |
| resper | sim | não | 0 |
| iaraujo | sim | sim | 0 |

Nenhum código de emergência registrado. Não foram alteradas senhas nem gerados
autenticadores em nome desses usuários. Cada responsável precisa manter seu
próprio fator e guardar sua recuperação fora do ambiente principal.

Para gerar recuperação no Psono: entrar em `https://cofre.ness.com.br`, abrir
**Account → Generate Password Recovery → Generate** e guardar o código/palavras
offline. Não enviar esses valores no chat. Uma nova geração invalida a anterior.
Referência: [documentação de recuperação do Psono](https://doc.psono.com/user/other/recovery-codes.html).

## Próximos critérios a fechar

1. Verificar cobertura do backup para código implantado e arquivos externos
   `/etc/ness-os/*` referenciados pelo Compose; o arquivo `app-config.tar.gz`
   atual lista apenas `.env`, Caddy e os dois arquivos Compose.
2. Capturar a implantação atual e testar reconstrução das aplicações sobre as
   bases restauradas, com dependências contidas.
3. Completar recuperação/MFA dos responsáveis com posse individual dos fatores.
4. Estender a prova aos demais sistemas canônicos do programa.

Saúde produtiva às 21:12:23 UTC: Zabbix/GLPI e dois workers OK; filas vazias,
zero falhas/retries registrados e zero entregas/resoluções pendentes.

## Continuação — cobertura da implantação, 21:19 UTC

Corrigida a lacuna de código/configuração no produtor noturno. O novo
`infra/scripts/aiops-deployment-backup.sh`, instalado como
`/usr/local/sbin/ness-aiops-deployment-backup`, é chamado antes da etapa que
interrompe n8n/GLPI no backup já existente. Esta execução não disparou essa etapa
nem interrompeu serviços.

Arquivos adicionais:

- `deployment-app.tar.gz`: backend, frontend, arquivos de build, conteúdo público,
  Compose, Caddy e `.env`; exclui dependências locais, caches e arquivos tar antigos.
- `deployment-runtime.tar.gz`: `/etc/ness-os`, rota específica já existente,
  units `ness-*` e scripts `/usr/local/sbin/ness-*`.
- `deployment-images.json`: referências, IDs, digests disponíveis e mounts de
  14 containers AIOps; não contém o ambiente completo do Docker. É um inventário,
  não uma exportação das imagens locais.

Cópia atual, protegida por permissões root e umask 077:
`/opt/n-infraops/backups/deployment/20260908T181913-0300`.
O marcador `DEPLOYMENT_COMPLETED` distingue esta cópia de código/configuração de
um backup completo com bases e volumes. Ela não substitui o backup noturno.

Verificações aprovadas:

- comparação de todo o conteúdo dos dois arquivos tar com as fontes;
- checksums dos três artefatos;
- extração isolada: 133 arquivos da aplicação;
- comparação dos módulos OIDC/alerts, interface, Dockerfiles, configurações de
  integração e scripts instalados após extração;
- sintaxe Bash dos scripts recuperados;
- rejeição de destino fora das raízes permitidas e de sobrescrita do snapshot;
- saúde produtiva às 21:19:24 UTC: filas vazias, dois workers, zero falhas/retries,
  zero tickets/resoluções pendentes.

O verificador de restauração noturna agora extrai todos os arquivos `*.tar.gz`
do conjunto, incluindo os novos. A mudança foi validada sintaticamente; o ciclo
noturno completo com a cobertura nova ainda precisa executar. A cópia adicional
acima ainda não foi transferida ao repositório remoto. O produtor remoto existente
seleciona conjuntos noturnos `COMPLETED`; portanto não confundir esta cópia local
com prova de recuperação externa da implantação atual.

Rollback do produtor: versão anterior em
`/opt/n-infraops/rollback/recovery-20260908/nightly-before-coverage.sh`.
Permanece pendente reconstruir as aplicações, resolver a disponibilidade das
imagens locais em DR e comprovar cópia remota/restauração do conjunto atualizado.

## Continuação — recuperação remota da implantação, 21:22 UTC

A rotina de captura também passou a exportar as quatro imagens locais `app-*`
com `docker image save`. Os RepoDigests dessas imagens existem localmente, mas
isso não comprova publicação em registry. O arquivo exportado evita depender
dessa suposição durante a recuperação. Foram conferidos os hashes SHA-256 de
45 blobs do arquivo e a presença dos quatro IDs de imagem esperados.

Conjunto novo:
`/opt/n-infraops/backups/deployment/20260908T182121-0300` (273 MiB).
Enviado ao repositório Restic AIOps já existente, criptografado, com tag separada
`ness-deployment-recovery`, sem alteração de retenção ou remoção de snapshots.

Snapshot recuperado por ID exato:
`138b4a8495fa15469e4582e9b926200a303971198d68c026c62dcd300cc18f34`.

`restic restore --verify` recuperou seis arquivos/entradas, 272,605 MiB, e
verificou seu conteúdo. Em seguida, o `SHA256SUMS` recuperado validou os quatro
artefatos: aplicação, configuração externa, inventário e exportação de imagens.
Diretório temporário removido ao término. Log protegido:
`/var/lib/ness-os/hub-integration/deployment-remote-restore-20260908.log`.

Verificador reproduzível:
`infra/scripts/aiops-deployment-remote-verify.sh`, instalado em
`/usr/local/sbin/ness-aiops-deployment-remote-verify`.
Recebe um conjunto local marcado `DEPLOYMENT_COMPLETED`, confere checksums,
envia ao repositório e recupera o snapshot exato para uma pasta descartável.
O script não apaga cópias remotas nem restaura sobre caminhos produtivos.

A prova acima substitui a pendência de transferência remota da cópia adicional
anterior. Ainda não é prova de DR completo: falta carregar as imagens em um
ambiente limpo e iniciar as aplicações com bases/volumes coerentes e atualizados.
O arquivo de configuração conserva credenciais para recuperação; a posse externa
da chave do repositório continua necessária para evitar dependência circular.

Também corrigida a seleção automática no ensaio noturno: escolhe o conjunto mais
recente com marcador `COMPLETED`, ignorando diretórios incompletos. Sintaxe validada
e script instalado; nenhum novo ensaio completo de bases foi disparado nesta etapa.

## Ensaio de Docker limpo — método e correções

Novo script `infra/scripts/hub-clean-engine-restore.sh` prepara um daemon Docker
descartável, com socket, diretórios, PID e namespaces containerd próprios, sem
bridge, regras de firewall, portas publicadas ou acesso externo dos containers.
O diretório de imagens é conferido vazio antes da importação.

O ensaio baixa o snapshot remoto exato e usa suas imagens e código da aplicação.
Captura adicionalmente um dump lógico atual do banco `nessops`, seus papéis e
as imagens PostgreSQL/Redis da produção. Esses dois últimos componentes não são
baixados de backup remoto neste ensaio: essa limitação permanece explícita.
As credenciais da base são adaptadas somente dentro do PostgreSQL descartável.

Correções durante a preparação:

- o daemon secundário inicialmente se conectou ao namespace containerd padrão;
  foi interrompido e recebeu namespaces exclusivos antes da repetição;
- a carga das imagens funcionou, mas seus IDs diferem entre o armazenamento
  containerd/OCI e o armazenamento clássico vfs; o verificador passou a resolver
  índice → manifesto Linux/amd64 → configuração pelos blobs SHA-256 exportados;
- o Dockerfile inclui `COPY cli/ ./cli/`; adicionada essa pasta à captura de
  código, além de backend/frontend/public.

Os primeiros ensaios não constituem aceite. A execução completa exige HTTP do
frontend/API, leitura de incidentes/ativos/usuários pela aplicação restaurada,
resposta dos dois workers e limpeza do ambiente descartável.

A captura atualizada com `cli` também foi recuperada do repositório remoto:
conjunto local `20260908T183215-0300`, snapshot
`0d22b1ce904b994a96a4d61979b0e179537770aeec2cf420c0d3b7b39d0364ee`.
Quatro artefatos passaram nos checksums após `restic restore --verify` (272,611
MiB). Log: `/var/lib/ness-os/hub-integration/deployment-with-cli-20260908.log`.

## Aceite do ensaio do hub — 21:36 UTC

A terceira execução de `hub-clean-engine-restore.sh` terminou com código zero e
`hub_clean_engine_restore=PASS`, após corrigir o isolamento e a identificação das
imagens. Evidências do log
`/var/lib/ness-os/hub-integration/hub-clean-engine-restore-20260908.log`:

- Docker iniciou sem imagens; quatro imagens do hub foram carregadas do snapshot
  remoto `138b4a84…`, além de PostgreSQL/Redis exportados da produção;
- identidades de seis imagens conferidas pelos metadados de plataforma;
- PostgreSQL inicializado isoladamente, papéis e dump atual `nessops` restaurados;
- frontend e API responderam HTTP, com conteúdo esperado;
- o backend acessou o banco restaurado: 380 incidentes, 256 ativos e 2 usuários;
- dois workers Celery responderam ao ping pelo Redis isolado;
- daemon de teste encerrado, containers e diretório descartável removidos.

Saúde produtiva conferida às 21:36:42 UTC: Zabbix/GLPI OK, dois workers, filas
vazias, zero falhas/retries e zero entregas/resoluções pendentes. Os serviços de
produção mantiveram seus tempos de execução durante o ensaio.

Limites deste aceite: não recompila imagens, não simula perda do servidor inteiro,
não restaura a base atual do hub do repositório remoto e não testa a jornada SSO
no ambiente recuperado. O dump foi capturado diretamente da produção para esta
prova. SMTP, WhatsApp, push e integrações externas ficaram indisponíveis/desligados.
O aviso de VAPID temporário é esperado porque o ensaio não injeta segredos reais
na aplicação; não comprova recuperação de push ou de sessões autenticadas.
GLPI/Authentik/Evolution e demais sistemas ainda precisam de suas próprias
provas completas de aplicação, além das restaurações de base já registradas.

## Aceite do hub com origem exclusivamente remota — 08/09, 18:45 BRT

A captura passou a incluir `deployment-hub-database.tar.gz` com papéis e dump
consistente de `nessops`, além das imagens PostgreSQL/Redis no arquivo de imagens.
No backup noturno reutiliza os dumps já gerados pelo produtor; na captura avulsa
gera o dump sem parar a aplicação. A consistência do dump é por banco, não entre
hub, GLPI e sistemas externos.

Conjunto: `/opt/n-infraops/backups/deployment/20260908T183826-0300`.
Snapshot remoto:
`7f1ea8f51ea29e05c91c2e682213f5fa09b786c2b7588438bc84ce7942eeaadc`.
Foram recuperados 785,347 MiB e conferidos os cinco artefatos por checksum.

O verificador de Docker limpo agora exige o banco presente no snapshot e não
possui fallback para `docker exec`, `docker inspect` ou exportação de imagens da
produção. Resultado: **PASS**, código de saída zero.

- imagens iniciais no Docker descartável: zero;
- seis imagens importadas e identificadas por configuração/plataforma;
- papéis e banco recuperados do arquivo remoto;
- HTTP do frontend/API aprovado;
- conexão do backend com dados restaurados: 387 incidentes, 256 ativos, 2 usuários;
- dois workers respondendo pelo Redis isolado;
- confirmação adicional dentro da API: somente interface loopback;
- processo encerrou e executou a limpeza do ambiente descartável.

Logs:
`/var/lib/ness-os/hub-integration/hub-clean-engine-remote-only-20260908.log`,
`deployment-full-hub-remote-20260908.log` e `hub-restore-network-proof-20260908.log`
no mesmo diretório. A confirmação de loopback foi incorporada ao verificador.

Este aceite substitui a limitação anterior de buscar a base diretamente da
produção durante o restore. Continuam abertos: reconstrução do servidor/DNS/TLS,
login SSO no ambiente recuperado, configuração criptográfica real da aplicação,
estado de tarefas pendentes do Redis e integração entre os sistemas restaurados.
O Redis do ensaio é novo; ping dos workers não prova recuperação da fila antiga.
RPO/RTO contratual e DR de todos os sistemas não estão declarados concluídos.
