# ADR 0020 — fronteira de entidade para manutenção GLPI

- Status: proposta; acesso produtivo bloqueado até ensaio negativo completo
- Data: 13/10/2026
- Escopo: identidade `svc_ness_maintenance` (106), perfil 13, entidade Alupar (1)

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
Uma requisição pública não autenticada a `n-ticket.ness.com.br/apirest.php`
foi encaminhada ao fluxo Authentik. Isso não prova bloqueio para usuário
autenticado ou portador de token; a rota pública exige teste negativo próprio.
O diagnóstico sem credenciais `infra/scripts/glpi_network_boundary_probe.py`
retornou `BLOCKED_DIRECT_PATH`, com uma rede compartilhada. O comando não
emite `PASS`, mesmo que as redes venham a ser separadas; a fronteira requer
prova de rotas, identidade e objetos. Três testes locais passaram.

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
