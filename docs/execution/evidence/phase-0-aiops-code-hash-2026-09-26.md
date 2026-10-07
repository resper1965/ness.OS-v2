# Comparação atual de hashes do backend AIOps — Fase 0

Coleta somente leitura em 2026-09-26 às 19:28:42 UTC, na VPS AIOps
`144.91.115.242` (`vmi3409271`), por `ness_admin` com elevação `sudo -n`.
O escopo é somente `/opt/n-infraops/app/backend/app`, comparado ao diretório
local `app/backend/app` do worktree `feat/incidents-rbac-local`, HEAD
`04b432d`. Arquivos `.pyc`, `.pyo` e diretórios `__pycache__` foram excluídos.

| Resultado | Quantidade |
|---|---:|
| Arquivos no AIOps | 75 |
| Arquivos locais | 77 |
| SHA-256 idênticos | 36 |
| SHA-256 diferentes | 39 |
| Somente no worktree local | 2 |
| Somente no AIOps | 0 |

A divergência confirma que o backend em execução não corresponde integralmente
ao código atual do worktree. Esta coleta cobre somente a árvore Python do
backend; não substitui a reconciliação de Compose, frontend, configuração,
dependências, imagens ou demais arquivos montados/instalados. Nenhum arquivo,
container ou serviço remoto foi alterado.

## Imagens dos containers em execução

Às 19:29 UTC, `docker inspect` consultou os 17 containers em execução. Os
quatro containers próprios (`ninf-api`, `ninf-frontend`, `ninf-worker-alerts`
e `ninf-worker-ml`) usam referências locais `app-*`, têm Image ID observado,
mas não têm `RepoDigests`; portanto não há digest de registry que vincule essas
imagens a um artefato publicável e reproduzível. Os outros 13 containers exibem
referências com digest SHA-256, inclusive imagens com tags mutáveis como
`latest` acompanhadas do digest no `Config.Image` observado.

Esta é evidência do runtime no instante da coleta. Não demonstra que as
referências persistidas no Compose estejam imutáveis, que as imagens locais
tenham sido reconstruídas do HEAD `04b432d`, nem que exista rollback ensaiado.

## Compose efetivamente associado ao API

Às 19:31 UTC, os labels do container `ninf-api` identificaram o projeto Compose
`app`, serviço `api`, arquivo `/opt/n-infraops/app/docker-compose.yml` e
diretório de trabalho `/opt/n-infraops/app`. O SHA-256 remoto do Compose foi
`7371b66eca657ebef78679228a544ca2a4f66b3dcc025f0f0cb2c4c0acab9f33`; o arquivo
local `app/docker-compose.yml` teve
`e57d315554310f83245f10820ffac91f6a3cebda4ae9025a1f0f5af59b2977fe`. Os hashes
diferem. Nenhum conteúdo foi coletado para a evidência.

## Autenticação da API Contabo

Às 19:33 UTC, uma tentativa de autenticação a partir do container `ninf-api`
usou OAuth `client_credentials` com os valores de `CONTABO_CLIENT_ID` e
`CONTABO_CLIENT_SECRET` configurados; os valores não foram impressos nem
persistidos. O servidor retornou HTTP 401 `unauthorized_client` com a descrição
`Client not enabled to retrieve service account`. Essa tentativa não validou
o fluxo correto da integração. A implementação local em
`app/backend/app/integrations/contabo_firewall.py` usa `grant_type=password` e
requer também `CONTABO_USERNAME` e `CONTABO_PASSWORD`; os dois últimos estavam
ausentes do ambiente do container. Nenhuma chamada ao endpoint de instâncias
ocorreu. O inventário da API segue pendente até que a identidade completa seja
provisionada no ambiente de forma segura; não colocar credenciais no Git.

Uma checagem de nomes de chaves nos arquivos `.env` do AIOps confirmou que
`.env.pre-gate0-20260820T163730-0300` continha valores não vazios para
`CONTABO_CLIENT_ID` e `CONTABO_CLIENT_SECRET`, sem exibi-los. O arquivo estava
`0644` e não havia referência literal a seu nome em `/etc/systemd/system` ou
nos arquivos da aplicação fora de `.env*`. Para reduzir leitura por usuários
locais, seu modo foi alterado para `0600` e verificado. Nenhum conteúdo foi
alterado e nenhum serviço foi reiniciado.

## Método

Um Python remoto calculou SHA-256 dos arquivos sob a árvore indicada e emitiu
somente caminhos relativos e hashes. O PowerShell calculou os hashes locais e
comparou os mapas em memória. Nenhum conteúdo de arquivo foi lido para a saída,
e os hashes individuais não foram registrados neste relatório.
