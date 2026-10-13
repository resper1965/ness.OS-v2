# ADR 0020 — fronteira de entidade para manutenção GLPI

- Status: proposta; acesso produtivo bloqueado até ensaio negativo completo
- Data: 13/10/2026
- Escopo: identidade `svc_ness_maintenance` (106), perfil 13, entidade Alupar (1)

## Estado produtivo em 13/10, 08:34 BRT

Em 13/10, ~09:08 BRT, um teste HTTP sintético adicional mostrou que
`/apirest%252Ephp/initSession` atravessava o matcher anterior e alcançava o
upstream **sintético**. Não foi demonstrado que o GLPI real interpretava essa
URL como API. O matcher público passou a negar também qualquer escape `%XX`
remanescente no path, cobrindo codificação dupla/tripla e letras codificadas;
query string codificada de `/front/central.php` continuou permitida no teste.
O Caddyfile novo foi validado, aplicado com cópia anterior root-only em
`/opt/n-infraops/rollback/glpi-api-guard-encoded-20261013/Caddyfile.before`
e reload sem recriação. Readback: hashes host/contêiner idênticos, Caddy
`running`/restart count 0; na rota pública, API normal e duas variantes
codificadas deram 403, GLPI/SSO 302 e Hub 200. Rollback: copiar o arquivo
anterior sobre `/opt/n-infraops/app/Caddyfile` e recarregar o Caddy. Isso
endurece apenas a borda pública: caminho interno Hub/worker→GLPI e seleção
indevida da entidade descendente continuam pendentes; 106 segue inativa.

A dependência de persistência da issue #76 foi migrada para o volume nomeado
`app_glpi-state`, com backup, comparação e guard aprovados; o volume original
permanece intacto. A issue fica aberta para smoke nominal/observação. O
`app/Caddyfile` candidato foi carregado no Caddy produtivo e passou na rota
real: quatro variantes públicas de `/apirest.php` retornaram 403, enquanto
UI GLPI=302 para SSO, Hub=200, SSO=302 e API interna GLPI=200. O bind mount
do Caddy reteve inicialmente o inode antigo após `install`; a configuração
foi carregada pelo admin endpoint e, em seguida, somente `ninf-caddy` foi
recriado com o mesmo hash de serviço Compose. Inodes e SHA-256 do Caddyfile
no host e no contêiner coincidem; as sete rotas reais foram novamente
verificadas após a recriação. Este bloqueio público não remove a
rede compartilhada Hub/worker↔GLPI nem limita a troca de entidade da conta
106. T03/G2 seguem bloqueados e 106 permanece inativa.

## Problema comprovado

A associação da conta 106 à entidade 1, marcada não recursiva, não impediu
`changeActiveEntities` para a descendente 5 seguido de leitura de Computer 5.
O teste direto falhou; a conta 106 foi desativada e deve permanecer assim.
Verificar a entidade efetiva no cliente Hub evita um erro do consumidor, mas
não restringe quem possui o token e chama a API GLPI diretamente. O perfil 13
não deve ganhar privilégios para contornar essa falha. A conta Hub 94 não muda.

## Opções a ensaiar, em ordem

A [documentação REST oficial do GLPI 11](https://github.com/glpi-project/glpi/blob/11.0/bugfixes/apirest.md)
prevê filtro de cliente API por faixa IPv4/IPv6 e App-Token. Primeiro testar
se um cliente exclusivo da manutenção pode aceitar apenas o IP do adaptador,
negando a mesma credencial pelo Hub e pela rota pública. Não presumir que o
filtro vale para toda combinação de `user_token`, sessão e reverse proxy: o
GLPI pode ver o IP do proxy, não o do chamador. Verificar no ambiente sintético
os caminhos permitidos e negados antes de escolher essa alternativa.

Leitura da versão **instalada** em 13/10/2026, sem mudar configuração:
`/var/www/glpi/src/Glpi/Api/API.php` seleciona clientes ativos cujo intervalo
IP contém `Toolbox::getRemoteIpAddress()` (linhas 202–249) e
`checkAppToken()` exige correspondência exata com o App-Token de um desses
clientes (linhas 2339–2363). `Toolbox.php:2812–2815` retorna
`$_SERVER["REMOTE_ADDR"]`; não usa `X-Forwarded-For` nesse percurso.
Isso confirma um controle nativo candidato, **não** a fronteira: se Hub,
adaptador ou rota pública chegarem ao GLPI com o mesmo IP percebido, o filtro
não os distingue. Também não restringe, por si só, a troca de entidade da
sessão autenticada observada no teste negativo.

Ensaio sintético **válido** de 13/10/2026: no mesmo host, GLPI 11.0.8 e MariaDB
descartáveis rodaram em rede Docker interna sem porta publicada e banco novo;
versão e hashes de `API.php`/`Toolbox.php` coincidem com a produção. Entidades
pai 1 e filha 2 foram criadas pelo modelo nativo em contexto CLI cron, e o
readback confirmou `entities_id=1` e `getAncestorsOf(2)` contendo 1. Havia um
Computer em cada entidade, perfil só com `computer=13`, usuário ligado apenas
à pai sem recursão e sem perfil padrão automático. Um cliente API com App-Token
foi restrito ao IP do adaptador sintético. Nenhum dado ou segredo produtivo
entrou no laboratório ou no relatório. O primeiro fixture, que não verificava
a hierarquia efetiva, foi **descartado**; seus resultados não são evidência de
isolamento.

| Verificação sintética | Resultado observado |
| --- | --- |
| Login pelo adaptador com App-Token e senha | HTTP 200 |
| Login do Hub simulado com o mesmo App-Token/senha | HTTP 400 |
| Hub com `X-Forwarded-For` forjado | HTTP 400 |
| Leitura do Computer pai no perfil mínimo | HTTP 200 |
| Leitura do Computer filho antes de `changeActiveEntities` | HTTP 403 |
| Seleção da filha e entidade efetiva | HTTP 200; entidade efetiva 2 |
| Leitura do Computer filho depois da seleção | HTTP 200 — isolamento nativo falhou |
| Mesmo fluxo por `user_token` | filho HTTP 403 → seleção HTTP 200 → filho HTTP 200 |
| Replay da sessão/token pelo Hub simulado | HTTP 400 pelo filtro IP/App-Token |

O ensaio **reproduziu** a falha de isolamento observada na produção: o grant
não recursivo não impede seleção da descendente. O filtro IP/App-Token barra
outro IP, mas não restringe troca de entidade dentro da sessão permitida. Por
isso, filtro IP isolado não aprova T03/G2 nem reativação de 106. A rota pública
autenticada não foi testada, pois nenhuma porta foi publicada; permanece aberta.
O laboratório não altera a configuração produtiva.

Segundo ensaio de rede, 13/10 04:01 UTC, testou uma variante **menos
disruptiva**: GLPI sintético em duas redes descartáveis; Hub só na frontal;
adaptador só na privada. O Hub alcançou `glpi-front` (HTTP 200) e não resolveu
`glpi-private`; o adaptador alcançou `glpi-private` (HTTP 200) e não resolveu
`glpi-front`. O servidor registrou origens distintas, `172.21.0.3` (Hub) e
`172.22.0.3` (adaptador), conferidas contra os endereços das redes. Três
containers sem mounts ou portas publicadas e as duas redes exclusivas foram
removidos; a listagem posterior ficou vazia. O teste usou somente um servidor
HTTP sintético, **não** GLPI, App-Token, SSO ou dados produtivos. Assim, é
viável preservar o caminho atual Hub/Caddy → GLPI enquanto uma credencial
de manutenção fica confinada à interface privada por filtro nativo de IP.
Ainda falta provar a restrição da credencial por todas as rotas, inclusive
a pública autenticada, com endereço estável e rollback. O caminho direto
Hub → GLPI permanece aberto para a integração atual; esta variante só
resolve T03 se o token da conta 106 for inacessível e inutilizável fora do
adaptador. Não confundir isolamento de credencial com isolamento total da API.

Ensaio de decisão, antes de ativar 106: em ambiente isolado, manter o mesmo
App-Token e testar `initSession`, `changeActiveEntities`, `getActiveEntities`
e `GET Computer` para entidade 1 e descendente 5, por três caminhos: adaptador,
Hub direto e rota pública autenticada. Registrar apenas status, entidade
efetiva e IP percebido, nunca credenciais ou payload. O resultado exigido é
permitir a operação contratada da entidade 1 **somente** pelo adaptador e
negar a descendente 5 e ambos os percursos diretos. Se qualquer rota direta
funcionar, descartar filtro IP isolado e implantar separação de rede/rota antes
de continuar. A conta produtiva 106 fica desativada durante o ensaio.

Como o filtro nativo não cobre a troca de entidade na sessão permitida,
**descartar o filtro IP isolado como solução T03** e prototipar a fronteira
privada abaixo. A solução completa ainda não está aprovada.

## Direção de protótipo da fronteira privada

Testar em ambiente isolado um adaptador privado com operações específicas de
inventário para a entidade 1. O adaptador guarda o token GLPI upstream e
estabelece a entidade no servidor; não expõe `initSession`, `Session-Token`,
`changeActiveEntities`, caminhos arbitrários, IDs globais ou proxy genérico.
Uma rede privada exclusiva deve ser o único caminho do adaptador ao GLPI.
Hub/operador não podem alcançar a rota nativa com a identidade 106. O cliente
continua validando readback e não envia segredos ao navegador.

O contrato inicial é pequeno: consultar identificador de ativo autorizado,
criar Computer/NetworkEquipment validado, ler por ID já associado à entidade
1 e excluir somente um ativo criado pela mesma operação com rollback. Outras
operações — busca livre, subitens, anexos, exportação, batch e mutação de
ticket — ficam negadas até contrato, testes e necessidade próprios. A
identidade upstream só recebe os direitos exatos comprovados para esse
contrato. Nenhum endpoint passa URL, método ou itemtype ao GLPI sem allowlist.

Primeira fatia de código, **não implantada**: `MaintenanceBoundary` em
`app/backend/app/integrations/glpi_boundary.py` aceita apenas leitura de
Computer com ID previamente aprovado pelo servidor, fixa a entidade no cliente
GLPI, confere ID e entidade do objeto retornado, reduz a resposta a três campos
e encerra a sessão. A segunda fatia adiciona uma aplicação FastAPI **não ligada
ao runtime** com uma única rota GET `/v1/computers/{id}`, bearer interno
obrigatório, lista de IDs aprovada em memória, 404 para ID não autorizado,
resposta mínima e `Cache-Control: no-store`. Falhas permanentes/transitórias
do upstream retornam 502/503 sem detalhes internos. Falha explícita no
encerramento da sessão impede devolver dados, mas ainda exige observabilidade
operacional quando houver serviço. Não há proxy genérico da API GLPI, rota de
escrita ou documentação interativa. Quinze testes da rota e treze da política
passaram; suíte backend 456 PASS, 1 SKIP, Black/Ruff PASS. Ainda faltam armazenamento/rotação do token
e da allowlist, isolamento de rede e rota pública, criação/exclusão,
deploy e matriz negativa ponta a ponta. Portanto essa fatia não autoriza
reativar o usuário 106 nem criar os três ativos.

Revisão local de 13/10: a política deixou de aceitar um `kill_session()` sem
confirmação explícita `True`. Teste RED mostrou que `None` ainda devolvia o
Computer; GREEN passou em 29 testes focados e 461 testes backend (1 pulado).
As fakes de teste agora retornam o booleano exigido do cliente real. Essa
falha fechada não equivale a isolamento de rede, deploy ou aceite T03.

Revisão local adicional de 13/10: a leitura no protótipo agora recusa URL
GLPI pública ou ausente **antes** de selecionar entidade/abrir sessão. O teste
RED demonstrou a tentativa anterior de contato com a URL pública; GREEN
passou em 30 testes focados e 462 testes backend (1 pulado) no ambiente de
dependências declarado. É somente uma precondição de configuração: hostname
privado não comprova rede exclusiva, sigilo do token, bloqueio de rota direta
nem autorização do objeto. Sem deploy; T03/G2 e conta 106 seguem bloqueados.

## Condições antes de implantar

Leitura do runtime em 13/10/2026: `ninf-api` e `ninf-glpi` usam ambos
`app_ninf-net`; de `ninf-api`, `ninf-glpi` resolve por DNS interno. GLPI não
publica porta Docker diretamente. Há, portanto, caminho direto entre Hub e
API GLPI; apenas adicionar um adaptador nessa rede **não** isola o token.
Readback de `docker inspect` em 13/10 confirmou que `ninf-api`, `ninf-glpi`,
`ninf-glpi-db`, `ninf-caddy` e os serviços Authentik compartilham essa rede.
O container GLPI foi criado pelo projeto Compose `app` com arquivos de
configuração em `/opt/n-infraops/app/docker-compose.yml` e
`/opt/n-infraops/app/docker-compose.tickets.yml`; já o container API tem
proveniência de uma release em `/opt/n-infraops/releases/...`. A fronteira
precisa ser aplicada à topologia efetiva, preservando UI/SSO, banco e demais
integrações; editar apenas o Compose histórico do repositório não basta.
Há também uma precondição de persistência: o Compose atual monta
`app_glpi-data` em `/var/www/html/glpi` (4 KiB observados), enquanto a imagem
declara `VOLUME /var/glpi`. O container produtivo usa ali um volume anônimo
separado, com configuração e 16 MiB de arquivos observados. Recriar `glpi`
com o Compose atual pode associar **outro** volume anônimo e perder o estado
visível, mesmo mantendo banco e `app_glpi-data`. Antes de qualquer mudança de
rede/recriação, identificar e preservar o volume atual, migrá-lo para volume
nomeado montado em `/var/glpi`, verificar conteúdo/permissões e ensaiar retorno
ao volume original. Não trocar só a linha do Compose nem executar `up
--force-recreate` com o estado ainda anônimo; manter o volume antigo até a
observação pós-mudança. Esta é uma dependência nova de T03, não prova de que
alguma recriação anterior perdeu dados. A correção está rastreada na
[issue #76](https://github.com/resper1965/n-infraops/issues/76).
O preflight versionado `infra/scripts/glpi_state_volume_preflight.py` agora
compara o volume efetivo de `/var/glpi` com o Compose resolvido antes de
recriar GLPI; a rotina `glpi-pin-and-rotate.sh` exige o teste tanto para o
Compose candidato quanto para o de rollback, antes de girar credenciais.
Cinco testes de unidade passaram. A execução somente leitura no host
produtivo retornou `BLOCKED` para o Compose atual, como esperado. O guard
não migra dados nem autoriza uma recriação: a migração reversível da issue
#76 continua necessária.
Para o ensaio offline, `infra/scripts/glpi_state_volume_compare.py` compara
árvore, conteúdo SHA-256, tipo, dono/grupo, modo, links e atributos estendidos
do volume original e do novo, sem imprimir nomes ou conteúdo. Nove testes de
infraestrutura passaram. A comparação só é evidência de cópia consistente com
GLPI parado e escrita bloqueada; ela não substitui o plano de tráfego,
snapshot, rollback do Compose e validação de banco/SSO. Não foi executada
cópia ou troca de volume em produção.
Ensaio descartável em 13/10 no host com dois volumes nomeados exclusivos e
imagem GLPI já presente: o primeiro comando falhou ao escrever no volume
porque a imagem executa com usuário sem privilégio; o trap removeu ambos os
volumes, confirmado por listagem. Repetido com `--user 0:0` apenas no
contêiner de teste, `cp -a` e o comparador retornaram PASS (1 arquivo,
15 bytes sintéticos), e o volume original foi reanexado em um segundo
contêiner somente leitura para simular retorno. Os dois contêineres, os
volumes exclusivos e o verificador temporário foram removidos, com ausência
confirmada. Isso valida somente mecânica de cópia/reattach, não captura
consistente com GLPI real ativo, rota pública, banco, SSO ou rollback de
escritas posteriores; ainda não há autorização para recriar `ninf-glpi`.
Ensaio seguinte de Caddy descartável: o host GLPI sintético respondeu 503
para GET e POST, enquanto hosts Hub e SSO sintéticos seguiram 200. O
contêiner e arquivo de teste foram removidos com ausência confirmada. O
Caddyfile runtime e o versionado tinham hash idêntico; o gerador
`glpi_caddy_maintenance.py` exige esse hash e troca somente o bloco GLPI.
O candidato completo passou em `caddy validate` com a imagem já instalada,
sem reload produtivo. O runbook
`docs/operations/glpi-state-volume-cutover-2026-10-13.md` explicita ordem,
aborto e limite do rollback após reabrir escrita. Isso prepara a janela,
mas não comprova rota pública/SSO real nem autoriza T03/G2.
Um ensaio Compose descartável com serviço sem rede confirmou por `docker
inspect` a sequência de mount `/var/glpi`: volume original → candidato →
original mediante override explícito e `--force-recreate`. Os dois volumes
de teste, o contêiner e arquivos temporários foram removidos com ausência
verificada. Não envolveu GLPI real, banco, estado produtivo ou escrita após
reabertura; permanece uma prova da mecânica de handoff, não do corte.
Uma requisição pública não autenticada a `n-ticket.ness.com.br/apirest.php`
foi encaminhada ao fluxo Authentik. Isso não prova bloqueio para usuário
autenticado ou portador de token; a rota pública exige teste negativo próprio.
Ensaio adicional em 13/10, com a **imagem Caddy efetiva** em contêiner
descartável `--network none`, sem porta publicada, segredo ou GLPI real:
`forward_auth` sintético retornou 200 e a configuração equivalente à rota
atual encaminhou `/apirest.php/initSession` ao upstream sintético (200).
Portanto autenticação pública bem-sucedida não bloqueia, por si só, a API.
Uma primeira candidata com `path /apirest.php /apirest.php/*` negou o caminho
normal (403), mas deixou `/apirest.php%252FinitSession` chegar ao upstream
(200). Uma segunda candidata com matcher `path_regexp (?i)apirest\.php`
negou os caminhos normal, uma vez codificado, duas vezes codificado e com
maiúsculas (403), mantendo `/front/central.php` encaminhado (200). O
contêiner e os três arquivos de teste foram removidos, com ausência
verificada. A resposta 200 do upstream foi **sintética**: não demonstra que
o GLPI interpretaria o caminho duas vezes codificado, nem que Authentik,
sessões reais ou todas as variantes de URL foram homologadas. Não houve
reload do Caddy produtivo. Qualquer bloqueio público futuro requer teste
negativo autenticado de método, codificação e rota real, além de rollback;
ele não substitui o isolamento da rota direta Hub/worker → GLPI nem resolve
a seleção indevida da entidade descendente.

Em 13/10 07:16 UTC, o Caddyfile versionado recebeu uma **candidata não
implantada**: `respond 403` para `path_regexp (?i)apirest\.php`, dentro de
`route` que preserva a ordem antes de `forward_auth` e `reverse_proxy`. O
teste do JSON compilado pelo Caddy real falhou primeiro sem o guard e também
quando `respond` ficou fora de `route`: nessa forma o `forward_auth` era
ordenado antes da negação. Com `route`, o 403 aparece primeiro e os quatro
caminhos sintéticos normal/case/encoding combinam com o matcher, enquanto a
UI não combina. O ensaio anterior de HTTP sintético testou o mesmo matcher,
mas esta mudança do Caddyfile completo **ainda não passou por HTTP real com
SSO e GLPI**. Não há reload produtivo; nem a rota pública candidata resolve
o caminho interno ou autoriza a conta 106.

Ensaio complementar de 13/10 07:27 UTC, reproduzível por
`infra/tests/test_glpi_public_api_http.py`: o bloco GLPI do Caddyfile
versionado foi executado em Caddy descartável com `--network none`, Authentik
sintético respondendo 200 e upstream GLPI sintético. URLs API normal, com
maiúsculas e codificadas uma ou duas vezes receberam 403 e não alcançaram o
upstream; `/front/central.php` alcançou o upstream. O contêiner usou `--rm`
e nenhum arquivo/rede/porta produtiva foi alterado. Isso valida o
comportamento HTTP **da candidata com serviços sintéticos**, não SSO/GLPI
produtivos, sessão real ou a rota direta interna.

O diagnóstico sem credenciais `infra/scripts/glpi_network_boundary_probe.py`
retornou `BLOCKED_DIRECT_PATH`, com uma rede compartilhada. O comando não
emite `PASS`, mesmo que as redes venham a ser separadas; a fronteira requer
prova de rotas, identidade e objetos. Três testes locais passaram.
O diagnóstico foi ampliado para incluir `ninf-worker-alerts`, que também
recebe a configuração GLPI. Readback em 13/10 retornou
`BLOCKED_DIRECT_PATH` para API **e** worker, com uma rede compartilhada;
cinco testes da sonda passaram. Isolar apenas `ninf-api` deixaria o caminho
direto do worker aberto. A sonda permanece somente leitura e nunca aprova
T03 por topologia isolada.

Ensaio reversível da **topologia candidata** em 13/10: duas redes Docker
descartáveis, quatro containers sintéticos da imagem API já presente no host,
sem mounts, credenciais ou portas publicadas. Hub somente na rede frontal;
GLPI somente na privada; adaptador e proxy nas duas. A matriz HTTP observada:
Hub → GLPI negado; Hub → adaptador permitido; adaptador → GLPI permitido;
proxy → GLPI permitido. Inspeção confirmou os vínculos de rede e zero mounts;
os quatro containers e as duas redes exclusivos do laboratório foram removidos
com ausência posterior verificada. Isso prova apenas viabilidade de roteamento
Docker, **não** bloqueio da rota pública autenticada, isolamento do token no
adaptador, operações permitidas, nem compatibilidade do Compose produtivo.

Segundo ensaio descartável em 13/10, agora com **GLPI 11.0.8 real** e MariaDB
isolados, sem portas publicadas nem dados produtivos: o GLPI ficou nas redes
privada e frontal; adaptador apenas na privada e Hub sintético apenas na
frontal. Um cliente API nativo criado pelo modelo GLPI foi limitado ao IP
privado observado do adaptador. Após habilitar a API apenas nesse laboratório,
o login sintético com App-Token retornou HTTP 200 no adaptador e 400 no Hub.
Uma sessão obtida no adaptador leu `getFullSession` ali (200), mas o replay
da mesma sessão pelo Hub retornou 400, inclusive com `X-Forwarded-For`
forjado. Login frontal sem App-Token e com cabeçalho forjado também retornou
400. Foram usados somente usuário/token sintéticos; nenhum valor de sessão
foi exibido. Os quatro containers, seus dois volumes anônimos, duas redes e
arquivos temporários exclusivos foram removidos após inspeção de vínculos,
mounts e readback de ausência. Isso comprova filtro nativo por IP de origem
para **esse cliente nesse arranjo isolado**. Ainda não testa a rota pública
autenticada/Caddy real, IP estável após recriação, os demais clientes API,
operações de objeto/entidade, credencial 106 nem aplicação no Compose atual.
Logo T03/G2 continuam bloqueados e 106 permanece desativada.

Ensaio adicional de anexação **em tempo de execução**, 13/10 06:40 UTC:
contêiner sintético sem mounts, duas redes Docker internas exclusivas do
laboratório e imagem API já presente no host. `docker network connect`
adicionou a rede privada mantendo o mesmo ID de contêiner, estado `running`
e mounts vazios; `docker network disconnect` voltou à rede frontal, também
sem recriação. Contêiner e redes foram removidos com ausência verificada.
[A documentação Docker](https://docs.docker.com/engine/network/drivers/bridge/)
descreve a anexação de contêiner em execução; a configuração durável ainda
precisa ser representada no Compose.
Isso permite estudar um canário privado sem necessariamente recriar o GLPI
e, portanto, sem acionar imediatamente o risco do volume anônimo. **Não**
prova que anexar a rede ao GLPI real é seguro: faltam teste de tráfego/SSO,
IP privado estável, filtro App-Token, rollback e registro da topologia no
Compose. Uma conexão manual fora do Compose pode desaparecer numa futura
recriação; o preflight do volume e a issue #76 continuam obrigatórios antes
de qualquer recriação ou promoção durável. Nenhuma rede/container produtivo
foi alterado neste ensaio.

Entrada executável candidata, 13/10 ~11:15 BRT, **não implantada**:
`glpi_maintenance_runtime.build_app` só inicia com URL privada, lista explícita
de um a cinco IDs de Computer, App-Token, user token e bearer em arquivos
separados; os três valores não entram no Compose ou no Git. O adaptador
continua permitindo apenas GET de Computer aprovado e devolve três campos;
`/live` indica apenas processo vivo, não saúde do GLPI. `GLPIClient` deixou de
carregar Settings quando URL e ambos os tokens foram dados explicitamente,
evitando efeitos colaterais da configuração geral no sidecar. O override
`app/docker-compose.glpi-maintenance.yml` é opt-in: acrescenta rede interna
e IP estático ao gateway, mantém GLPI em `ninf-net`, não publica porta e monta
três secrets. `docker compose config --quiet` na CLI real passou com valores
**fictícios**; o modelo resolvido preservou `ninf-net` em GLPI/gateway,
`app_glpi-state` em `/var/glpi`, rede privada `internal`, três secrets e zero
portas publicadas para o gateway. Não foi usado token real nesse ensaio,
nenhum container/rede foi criado ou alterado. Testes focados 25 PASS;
backend+escopo 486 PASS/1 SKIP, Ruff/Black PASS. MyPy do módulo passou com
o `import-untyped` preexistente de pgvector isolado na execução local.

Antes de aplicar o override: comprovar subnet sem colisão, imagem da release
contendo o entrypoint, secret files/permissions, IP estável após recriação,
filtro de cliente GLPI limitado a esse IP, rota pública autenticada negada,
Hub/worker com a credencial 106 negados mesmo usando a API direta, e matriz de
objeto/entidade 1 permitida vs. 5 negada no gateway. O override deixa a rota
nativa da identidade Hub 94 intacta; não confundir isso com isolamento geral
da API. O contrato candidato é só leitura e não cria os três ativos.

Preflight somente leitura em 13/10 ~11:20 BRT: as quatro redes bridge atuais
do host usam `172.17.0.0/16` a `172.20.0.0/16`; o candidato
`172.30.250.0/28` não colidiu com nenhuma rota IPv4 não-default observada
nem com essas redes. Isto é uma fotografia, não reserva do bloco: revalidar
imediatamente antes de criar rede, inclusive conflitos com VPN/rotas novas.
Nenhuma rede foi criada no preflight.

Publicação de imagem, 13/10 ~11:25 BRT: o workflow versionado
`.github/workflows/publish-hub-images.yml` é `workflow_dispatch`, mas a
tentativa de dispará-lo na branch de entrega retornou HTTP 404. A listagem de
workflows do repositório não o inclui, pois ele ainda não está registrado na
branch padrão `main`. Os cinco checks da branch passaram; isso **não** produz
uma imagem nova por digest. Sem publicação e verificação da imagem contendo o
entrypoint, não implantar o gateway por tag antiga, não alterar a topologia
produtiva e não reativar 106. A revisão/integração da branch já é acompanhada
na issue #67; após disponibilizar o workflow, publicar a imagem, conferir o
digest e repetir apenas o preflight afetado antes do canário.

Guard local `infra/scripts/glpi_maintenance_preflight.py`, ainda sem promoção:
antes de resolver o Compose, exige referência `@sha256` da imagem, subnet
IPv4 RFC1918 com IP de host utilizável e três arquivos regulares não vazios
sem permissões de grupo/outros. A saída contém somente códigos de resultado,
não caminhos ou segredos. Rodar no host com as variáveis do override; PASS
**não** comprova que a imagem existe no registry, que a subnet não colide
com rotas recém-criadas ou que a matriz GLPI/Hub está isolada. Esses testes
continuam obrigatórios. Cinco testes de unidade e 32 testes de infra com
`PYTHONPATH=app/backend` passaram.

Teste integrado **sintético** do entrypoint em 13/10 ~11:38 BRT: a factory
carregou três arquivos de teste e fixou URL/entidade 1; bearer incorreto foi
negado antes de criar cliente, Computer 41 da entidade 1 retornou somente os
três campos permitidos e a resposta simulada da entidade 5 foi negada com
logout em ambos os percursos. Sem contato com GLPI real, sem token real e
sem rede/container produtivo. Backend 475 PASS/1 SKIP; cinco checks do commit
`1328116` concluíram PASS, incluindo build efêmero da imagem no job SBOM.
Esse build de CI **não** publicou imagem por digest e não substitui a matriz
negativa direta nem o GO de implantação.

1. Projetar e ensaiar filtro nativo por cliente/IP ou separação de rede/rota
   mantendo UI/SSO legítimos.
   Confirmar também se a rota pública expõe `apirest.php`; bloquear o token
   técnico fora do adaptador sem interromper usuários e outras integrações.
   O Compose de raiz não é prova da topologia atual. Sem bloqueio direto,
   o adaptador não é fronteira de segurança.
2. Criar fixtures sintéticas de entidade 1 e descendente 5 fora da produção;
   exportar estado e ensaiar rollback sem alterar dados reais.
3. Testar leitura, busca, exportação, subitens e escrita via interface
   permitida; testar também requests diretos à API nativa, path encoding,
   IDs de outra entidade, sessão reaproveitada e batch. Todos os percursos
   não contratados devem negar antes da chamada upstream.
4. Demonstrar acesso autorizado à entidade 1 e negativa à 5 por todas as
   rotas expostas, com logs sem token ou payload sensível.
5. Só então decidir deployment, rotação de credencial e eventual reativação
   normal da conta 106. Uma alternativa que exija ampliar escopo da conta
   ou mudar hierarquia de entidades requer decisão humana explícita.

## Estado e reversão

Esta ADR não aprova T03, G2, ativação de 106 nem onda de três ativos. O
rollback do futuro adaptador será bloquear a rota e desativar 106; os ativos
existentes e a conta Hub 94 devem permanecer intactos.
