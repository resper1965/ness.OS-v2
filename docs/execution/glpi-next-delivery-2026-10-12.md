# GLPI — retomada operacional de 12/10/2026

## T01/issue #76 — persistência de `/var/glpi`, 13/10 08:30 BRT

Ricardo deu GO explícito para a migração produtiva com Ismael como responsável
técnico; registro na issue #76. Backup `COMPLETED` de 12/10 23:07 BRT e
checksums íntegros. Rota GLPI isolada com 503 GET/POST sem afetar Hub/SSO;
GLPI parado, volume anônimo copiado para `app_glpi-state`, comparação integral
PASS (5.780 arquivos; 8.490.431.469 bytes). Compose corrigido, somente GLPI
recriado, guard de mount PASS. UI/API internas 200, esquema do banco PASS;
rota pública reaberta ao redirect SSO anterior 302. Volume anônimo original
e configuração de rollback explícita preservados. Login nominal, perfil,
ticket e anexos ainda pendem; conta 106 continua desativada e T03/G2 não são
aprovados. Procedimento e incidente de bind mount em
`docs/operations/glpi-state-volume-cutover-2026-10-13.md`.

## T01 — backup do novo volume, 13/10 ~08:45 BRT

Após a migração, o backup noturno enumeraria `app_glpi-state`, porém poderia
marcar `COMPLETED` sem esse arquivo se a enumeração falhasse. Teste RED
reproduziu esse falso sucesso; a correção exige
`volumes/app_glpi-state.tar.gz` no conjunto de artefatos, com tamanho não
zero e entrada no `SHA256SUMS`. Teste shell GREEN e suíte infra 22 PASS com
`PYTHONPATH=app/backend`. Script produtivo anterior preservado root-only e
novo hash idêntico ao versionado; `bash -n` PASS, timer habilitado/ativo,
GLPI montado no volume esperado. **Nenhum backup novo foi executado agora**:
o primeiro conjunto agendado após a mudança ainda deve comprovar
`COMPLETED`/checksum/arquivo, sem repetir restores históricos.

## T03 — guarda da API pública, 13/10 08:36 BRT

O Caddyfile versionado com `route`/matcher para `apirest.php` foi validado e
carregado no runtime. GET públicos para quatro variantes — normal, maiúsculas,
uma e duas codificações — retornaram 403; UI GLPI=302, Hub=200, SSO=302 e API
interna GLPI=200. Somente Caddy foi recriado para reconciliar o bind mount:
hash de Compose idêntico ao serviço anterior, inode/hash do Caddyfile igual
no host e contêiner, zero reinícios; os mesmos sete testes HTTP passaram após
recriação. O rollback é o Caddyfile anterior preservado root-only. A rede
interna compartilhada Hub/worker↔GLPI permanece, portanto a conta 106 segue
inativa; filtro público não fecha T03/G2.

## T10 — limite de branding suportado, 13/10

GLPI 11.0.8 instalado tem diretório persistente `_themes` vazio. A
[documentação oficial de paletas](https://glpi-user-documentation.readthedocs.io/fr/latest/advanced/custom_palettes.html)
permite SCSS por tema sem editar core; a
[FAQ oficial](https://help.glpi-project.org/faq/glpi/general_setup)
também documenta CSS por entidade. Já a substituição suportada de logos,
favicon e imagem de login requer o
[plugin Branding](https://help.glpi-project.org/faq/plugins/branding),
disponível em Cloud/assinatura Basic; não há prova de licença, instalação nem
ativo de logo aprovado neste runtime. Não instalar plugin, trocar arquivos
core, inventar logo ou aplicar paleta global sem ensaio visual/contraste e
rollback. Preparar primeiro paleta ness. por entidade e inspecionar render
desktop/móvel quando houver sessão nominal.

Em 13/10 ~10:45 BRT, `config/glpi/ness-light.scss`, manifesto e
`docs/operations/glpi-ness-experience.md` foram versionados. O arquivo foi
instalado em `/var/glpi/files/_themes` com hash local/remoto igual e
permissões `644:33:33`; ninguém foi migrado para o tema. GET público do login
seguiu 302 para SSO. O seletor é exclusivo do tema e não troca logo/ativo do
GLPI. Inspeção visual e piloto nominal ainda pendentes, logo T10 não aceito.

## T04 — backlog sem ticket, 13/10 07:55 UTC

Consulta agregada somente leitura no PostgreSQL do Hub, com transação
`READ ONLY`, classificou 159 incidentes sem `deskmanager_ticket_id`:

- 29 criados em 13/10: 28 com ativo e um sem ativo; todos têm identificador
  de evento Zabbix e última ação GLPI `ticket_failed`.
- 115 criados de 25/09 a 12/10: todos com ativo e identificador de evento,
  mas sem qualquer ação registrada em `n_infraops_incident_actions`.
  Cada um tem `alert_count=1` e duração observada de zero dias.
- 15 criados em 10/07: sem identificador de evento e sem ação registrada;
  11 têm ativo e quatro não.

O fluxo atual `process_alert_v1` tenta o ticket antes de persistir o
incidente e registra falha/sucesso como ação. Portanto, a ausência de ação
nos 130 registros anteriores não prova que o GLPI nunca criou ticket:
podem ser anteriores à auditoria atual, de fluxo/release diferente ou
representar vínculo local perdido. Nenhum replay, ticket ou ativo foi criado.
O monitor `incident_health` já acusa incidentes com evento sem ticket após
cinco minutos; a classificação acrescenta causa/idade à contagem existente,
não é evidência de saúde.

Próximo passo seguro: relatório reproduzível por cursor e busca remota
somente leitura pelo marcador idempotente, verificando entidade e vínculo
antes de propor lote de correção. Manter a conta técnica 106 inativa e
nenhuma escrita enquanto T03 não provar isolamento nativo da rota direta.

Uma amostra cronológica dos três primeiros registros do grupo de 115 foi
consultada pela API GLPI com sessão temporária e marcador completo, na
entidade correspondente. Resultado: zero tickets encontrados, três buscas
sem resultado, zero erro; sessão encerrada. Isso não permite extrapolar
para os outros 112 nem autoriza criação automática. A busca remota deve
continuar por cursor e tratar explicitamente acesso negado e marcador
duplicado antes de qualquer escrita.

O verificador `infra/scripts/glpi_backlog_reconcile.py` formaliza essa busca
somente leitura: até cinco registros por página, cursor por ID, transação
PostgreSQL `READ ONLY`, sessão GLPI encerrada e saída agregada sem
fingerprint/ticket/tenant. Um erro ou cliente sem entidade mapeada conserva o
cursor para revisão, sem interpretar 403 como ausência. Vinte e três páginas
de cinco foram executadas no runtime para o grupo histórico: 115 marcadores
ausentes na entidade mapeada, zero encontrados, zero erros, cursor final
75304; uma página seguinte vazia confirmou o fim. Nenhuma escrita ocorreu.
Três testes RED→GREEN, Ruff, Black e suíte infra/backend 482 PASS, 1 SKIP.
Isso não autoriza criar tickets: T03 ainda bloqueia a identidade técnica;
os 29 `ticket_failed` recentes e 15 registros sem evento exigem
classificação própria, sem replay em massa.

Leitura complementar dos 29 recentes: a última ação GLPI de todos contém
somente `error=RuntimeError`; o registro não distingue autorização, transporte
ou validação. Seis lotes de até cinco buscaram o marcador completo na
entidade mapeada: 29 ausentes, zero encontrados, zero erros de consulta e
zero entidades sem mapeamento. Não houve tentativa de criação. A causa da
falha original continua desconhecida; a ausência remota não libera replay
com a identidade técnica 106 desativada e T03 pendente. Os 15 legados sem
evento permanecem em quarentena de reconciliação, pois não têm identidade
de origem suficiente para criação idempotente.

## T12 — estado dos plugins, 13/10 06:45 UTC

`php /var/www/glpi/bin/console plugin:list --format=json --no-interaction`
foi executado no contêiner produtivo somente para leitura. Retornou dez
registros (`fields`, `credit`, `escalade`, `formcreator`, `gantt`, `nessai`,
`oauthimap`, `singlesignon`, `customlogin`, `tag`), todos com estado nativo
`Erro / para limpar`. As três localizações verificadas de código de plugins
(`/var/www/glpi/plugins`, `/var/www/glpi/marketplace`,
`/var/glpi/marketplace`) não contêm entradas. Não confundir esses dez
registros com o aviso visual histórico de sete atualizações disponíveis;
um não mede o outro. Não houve instalação, limpeza, ativação ou upgrade.

O código-fonte de `nessai` **existe no repositório**, em `plugins/nessai`,
versão 1.0.0 com requisito declarado GLPI ≥11.0; ele não está nos diretórios
do contêiner produtivo. A leitura do endpoint revelou ausência de verificação
de `Ticket::canViewItem()` antes de obter conteúdo/acompanhamentos e chamar
o provedor de IA. Um teste isolado RED demonstrou leitura indevida iniciada;
a correção local agora responde 403 antes de acessar banco/IA quando o ticket
não é visível. O teste GREEN e lint PHP passaram; nenhuma instalação/deploy
do plugin ocorreu. O listener CSRF da versão GLPI instalada exige o cabeçalho
`X-Glpi-Csrf-Token` em AJAX; o JavaScript enviava token somente no corpo.
Teste RED→GREEN com a requisição real construída pelo código acrescentou o
cabeçalho, preservando o corpo por compatibilidade. Typecheck/lint do frontend
passaram (um aviso existente). Isso não prova o POST HTTP end-to-end,
compatibilidade integral nem sanitização adequada para envio ao provedor
externo.
Dois testes RED→GREEN adicionais corrigiram a resposta vazia: a classe do
assistente entrega `text`, mas o endpoint lia `response`; o endpoint agora
publica `response` a partir de `text`, e o JavaScript prioriza esse campo
em vez de inserir o objeto JSON inteiro no editor. Testes PHP de leitura
negada/permitida, lint PHP, teste JS, typecheck/lint e backend 460 PASS,
1 SKIP. Tudo ainda é código não implantado.

Próximo: identificar a proveniência e compatibilidade dos demais pacotes com
GLPI 11, em especial `customlogin` e `singlesignon`, antes de
reintroduzir código ou limpar registro. O SSO via proxy/Authentik e o core
GLPI devem ser testados separadamente; estado de plugin não prova sua falha.
Não executar os sete upgrades em bloco nem reconstruir o contêiner enquanto
o volume anônimo `/var/glpi` e o rollback da issue #76 não estiverem
resolvidos.

### Revisão de plugins e duplicidade, 13/10 ~10:00 BRT

Auditoria nativa somente de leitura, reproduzível com
`infra/scripts/glpi_plugin_data_audit.php` e
`infra/scripts/glpi_duplicate_user_audit.php` dentro do contêiner GLPI.
Há 10 registros de plugin, mas nenhum diretório de código nos locais de
plugins/marketplace já verificados; o CLI os apresenta como indisponíveis.
Restam 24 tabelas de extensão: `escalade` contém 1 configuração e 24
vínculos de usuário; `nessai` contém 1 configuração; as demais tabelas
listadas têm zero linhas. Nenhum plugin foi desinstalado. Decisão: preservar
os registros e dados, porque o comando nativo `plugin:uninstall` depende do
script de desinstalação ausente; limpeza direta do banco não é um rollback
seguro e não melhora a execução (o código já não está carregado). Antes de
qualquer retirada futura, obter código/versão compatível, export específico
dos dados, dependências de SSO/formulários e ensaio de rollback. Em especial,
não limpar `customlogin`/`singlesignon` por inferência de que o proxy SSO os
substituiu.

Usuários não excluídos: 78, dos quais 75 ativos. Permanecem 34 grupos com
nome de login duplicado, 33 com ambas as contas ativas. Cada grupo tem
exatamente dois IDs e tipos de autenticação distintos: 17 pares `0+3` e 17
pares `1+3`; não há e-mail compartilhado por IDs diferentes. Dos 68
cadastros nesses grupos, só um registra login anterior e ele já está
inativo; todos têm ao menos um vínculo de perfil, nenhum vínculo em
`glpi_tickets_users` ou `glpi_itilfollowups`, e apenas um vínculo de grupo.
Essas leituras reduzem o risco de histórico de tickets, mas **não provam**
qual identidade deve permanecer nem que outras referências estejam vazias.
Não houve desativação/renomeação adicional. A issue #77 continua como trilha
de reconciliação por grupos, com conta canônica comprovada, export,
rollback e login nominal após cada onda de até cinco.

### Dedupe controlada, 13/10 ~10:30 BRT

A comparação de `glpi_profiles_users` revelou que **nenhum** dos 34 pares
tem grants idênticos. Nos 33 pares ativo/ativo, o cadastro legado tem
`Technician` (perfil 6; alguns também `Self-Service`), enquanto o cadastro
LDAP tem `Observer` (perfil 2). Portanto não há regra segura para desativar
em massa ou copiar o perfil antigo para o LDAP: a primeira opção pode
retirar atendimento técnico; a segunda pode elevar privilégio. A decisão
por par está solicitada na issue #77, sem nomes/e-mails públicos.

O único par com legado já inativo, IDs 8/93, foi reconciliado por API nativa
com `infra/scripts/glpi_dedupe_inactive.py`. Precondições, ensaio dry-run,
export completo anterior root-only `0600`, PUT apenas de `name` e `is_active`
inalterado, readback do LDAP e sessão encerrada passaram. Auditoria
independente: 34 → 33 colisões, todas as 33 restantes ativo/ativo; usuários
ativos continuam 75. Nenhum perfil, grupo, ticket ou e-mail foi alterado.
O arquivo anterior fica em
`/opt/n-infraops/rollback/glpi-dedupe-20261013/user8-before.json` no host;
retorno usa PUT nativo do nome/status guardados nele, não SQL.

Uma instrução por e-mail a Ismael/Ricardo foi tentada, mas Gmail retornou
HTTP 403 por quota temporária. Não presumir envio; conferir Sent antes de
repetir. O comentário da issue #77 contém requisito e passos sem PII.

## T07 — preflight de inventário, 13/10 06:18 UTC

Relatórios existentes executados via `ssh ... bash -s`, sem instalar script nem
alterar GLPI. A consulta agregada somente leitura retornou
`enabled_inventory=0`, sete registros de agentes com último contato em julho
de 2026, seis registros com padrão de varredura `SLEEP(` e nenhum desses seis
vinculado a ativo; os sete têm versão vazia e módulo de inventário de computador
desabilitado. A API interna `/Inventory` e `/front/inventory.php` respondeu 403
em GET a partir do container Hub. Na rota pública, GET sem sessão para
`/front/inventory.php` redirecionou ao Authentik (302). Esses GETs não são
prova de que um POST legítimo do agente falharia, nem identificam a configuração
dos endpoints; nenhum agente foi instalado, reiniciado ou ativado.

Ruling: não tratar os sete registros antigos como sete agentes operacionais nem
abrir exceção pública sem autenticação própria. T07 começa por identidade dos
cinco ativos internos elegíveis, configuração real do agente/servidor e teste
isolado de submissão; só então habilitar a coleta e expandir em ondas. Custo se
errado: diagnóstico mais lento, evitando expor uma rota de ingestão sem controle.

Leitura adicional em 13/10 06:33 UTC, sem instalação ou alteração: nos três
VPS conhecidos da plataforma — aplicação/GLPI, Zabbix origem e Zabbix destino
— `command -v glpi-agent` não localizou executável; as unidades systemd
retornaram `inactive`, `inactive` e `not-found`, respectivamente. Isso não
prova ausência de pacote em todos os caminhos nem define cinco candidatos.
Não iniciar um agente nesses nós antes de identificar a entidade/ativo
canônico, provar a rota autenticada de inventário em isolamento e registrar
o estado de rollback. A documentação oficial do GLPI Agent foi consultada
para fixar a preparação; nenhuma versão ou parâmetro de instalação foi
escolhido neste preflight.

## Retomada do plano master — 13/10 UTC

Cliente compartilhado do Hub passou a confirmar `getActiveEntities` após
`changeActiveEntities`. HTTP 200 com entidade efetiva diferente, escopo
recursivo ou formato inesperado é recusado e a sessão é encerrada. Teste
RED/green da divergência e da resposta com metadados adicionais; suíte backend
em ambiente isolado com dependências declaradas: 413 PASS, 1 SKIP. Código local
somente; conta 106 permanece inativa. Essa proteção do consumidor não resolve
o acesso direto da identidade técnica à API nativa: T02 ainda exige política
de grants/concorrência e T03 exige fronteira suportada antes do lote de ativos.

Incremento T04: busca idempotente por marcador deixou de examinar somente
`range=0-1`; percorre páginas até o total informado, inclusive quando a API
limita o tamanho retornado, e recusa Content-Range malformado. Testes RED/green
dos três casos; suíte backend 416 PASS, 1 SKIP. Ainda falta provar concorrência,
timeout após POST e reconciliação do backlog; nenhuma migração, ticket ou
deploy produtivo foi executado por essa alteração.

Incremento T04: 401/403 no cliente GLPI são classificados como recusa
permanente; o worker registra estado `blocked` após a trilha de persistência
do incidente e não consome novas tentativas automáticas. Falhas transitórias
continuam com retry. Testes RED/green para consulta, seleção, recurso/lista e
worker; suíte backend 420 PASS, 1 SKIP. Falta testar a jornada real/concorrência
e implantar após fechar gates aplicáveis.

## Plano canônico de continuidade

Consultar [GLPI no ness.OS — implementação completa](../superpowers/plans/2026-10-12-glpi-ness-os-complete-delivery.md)
para a sequência completa de 14 tarefas, customização, implantação, testes,
rollback e critérios de encerramento. Plano concluído e persistido; execução
não iniciada. Por instrução humana, o modelo autor não deve implementá-lo.
A retomada por outro modelo deve seguir o handoff e conferir as evidências
mais recentes ao final deste registro, especialmente a conta 106 desativada
após falha de isolamento. Heartbeats antigos não autorizam reativação.

Usuário solicitou terminar Zabbix e começar GLPI. Transição de foco não
aprova corte: origem continua única coletora; destino mascarado. SSO/MFA
nominal (issue 51), diagnóstico local do proxy (issue 73), qualidade da
frota, freeze/GO/corte e D+1/D+3/D+7 continuam pendentes. Zabbix não entregue.

## Observado agora

SSH no servidor existente 144.91.115.242 aprovado. Consulta agregada somente
leitura no banco GLPI em 12/10 após 22:48 UTC: 12 entidades, 103 computadores
e 153 equipamentos de rede não excluídos; 76114 tickets não excluídos
(não significa abertos), 7 registros de agentes, 8 SLAs com definition_time
nulo; notificações globais 0. Consulta exit 0.

Não houve escrita, criação de tickets ou envio externo. Registros de agentes
não comprovam inventário recente. Evidências de setembro são históricas.

## Sequência executável

1. Reusar catálogo, projeto e runbooks; não recriar objetos existentes.
2. Apurar crescimento dos tickets por data, origem e entidade; verificar
   duplicação pelo marcador persistente do Hub antes de concluir causa.
3. Reconciliar 262 hosts reais Zabbix com ativos GLPI por identificador externo
   estável; reportar ausentes, duplicados e tenant divergente sem inferir pelo
   nome nem contar protótipos como dispositivos.
4. Verificar frescor dos agentes, identidade técnica e isolamento de entidades.
   Ler verificadores antes de usar: fixtures que criam usuários não são leitura.
5. Corrigir somente casos inequívocos em lotes de cinco: estado anterior,
   precondição, API/modelo nativo, readback, idempotência e rollback.
6. Provar ticket sintético, três replays e resolução sem canais externos;
   preservar registros reais. Falha/retry não pode gerar duplicatas.
7. SLA depende da unidade contratual aprovada: não inventar prazos para
   eliminar nulos; dependência humana em issue/email sem cobrança repetida.

Aceite exige menor privilégio, isolamento, inventário qualificado e fluxo
idempotente atual. Processo running ou testes históricos não aprovam gate.

## Auditoria corrente — 12/10/2026 22:51 UTC

Consultas agregadas somente leitura, exit 0; nenhuma configuração ou registro
alterado. Totais variam durante ingestão: 76119 tickets não excluídos nesta
amostra, todos criados por userid 94; 76118 estado 1 (novo), um estado 5.
76118 possuem marcador Hub. Agrupamento pelo marcador completo extraído
por REGEXP_SUBSTR encontrou zero grupos duplicados. Isso não comprova ausência
de duplicidade semântica entre eventos distintos nem teste de retry/replay.

Criações por data: 06/10 2326; 07/10 2213; 08/10 2600; 09/10 2302;
10/10 2344; 11/10 2301; 12/10 1964 até a consulta. Volume significativo
e backlog novo exigem análise da política evento/incidente/ticket; não apagar
ou resolver em massa nem desligar ingestão para maquiar o resultado.

Achados confirmados:

- 646 tickets com marcador Hub sem vínculo de ativo;
- zero tickets marcados sem acompanhamento;
- zero tickets não excluídos com SLA de atendimento/resolução atribuído;
- sete agentes registrados, nenhum last_contact nas últimas 24 horas,
  nenhum last_contact nulo (não comprova serviço parado ou causa);
- campo otherserial vazio em todos os computadores/equipamentos de rede.
  Não é prova de ausência de vínculo: mapeamento existente está no Hub e
  deve ser consultado antes de qualquer escrita nesse campo.

Próxima entrega: conciliar identificadores do Hub com GLPI e registro Zabbix,
quantificar causas dos 646 vínculos ausentes e correlacionar backlog com eventos
distintos. Não repetir esta auditoria sem alteração relevante. SLA continua
dependência contratual; nenhuma duração presumida.

## Reconciliação do Hub — 12/10/2026 após 23:00 UTC

Leitura via modelos SQLAlchemy existentes, sem escrever: 255 ativos com
source=zabbix+glpi, zero host IDs duplicados, todos com glpi_item_id,
glpi_itemtype e glpi_entity_id preenchidos. Isso não comprova existência ou
entidade correta de cada referência no GLPI; readback cruzado ainda pendente.

76250 incidentes de origem Zabbix consultados; 646 sem asset_id e 115 sem
ticket na amostra. Não classificar os 115 como falha definitiva sem verificar
idade, estado, fila/retry e política de exclusão. Contagens são concorrentes.

Os 646 sem asset_id estão exatamente nestes host IDs:

| Host ID | Incidentes sem ativo |
| --- | ---: |
| 10983 | 532 |
| 10984 | 111 |
| 10987 | 2 |
| 10978 (sintético) | 1 |

Registro Zabbix datado 21:58 UTC confirma os três primeiros como hosts reais
ativos; o quarto é o trapper sintético conhecido. Não inferir tenant pelo nome
visível: confirmar grupos/mapeamento autorizado antes de criar ativos ou
reparar tickets. Igualdade da contagem 646 no Hub e GLPI é indício consistente,
não substitui comparação dos ticket IDs linha a linha.

Primeira consulta de diagnóstico falhou por referência a Asset.host_id
inexistente; corrigida para Asset.zabbix_host_id conforme modelo, sem efeitos
de escrita. Consultas corrigidas exit 0. Próximo passo: readback das 255
referências GLPI e classificação autorizada dos três hosts sem vínculo, antes
de qualquer lote de correção. Não repetir auditoria ampla de tickets.

## Readback cruzado e escopo confirmado — 12/10 após 23:10 UTC

Comparação em memória entre referências do Hub e tabelas GLPI, somente leitura:
255/255 ativos existem, não estão excluídos e têm a entidade esperada; marcador
Zabbix de cada referência é único e corresponde ao mesmo item. Zero divergências
de marcador/referência. GLPI tem 259 host IDs marcados ativos no total, sem
duplicação desses IDs. Os quatro adicionais exigem classificação separada,
não exclusão automática. Nenhum dos três hosts 10983/10984/10987 possui marcador
GLPI: lacuna confirmada, não mera ausência de otherserial.

API normal da origem confirma os três como flags0/status0; grupos autorizados
22 ([ Alupar ]) e 26 (servidores) presentes nos três. 10983/10984 também no24
(Matriz); 10983/10987 no42 e10984 no61 (grupos de servidores virtuais).
Templates Windows10081 nos dois primeiros, Linux10001 no terceiro. Tags vazias.
Cliente dos incidentes Alupar coincide com grupos autorizados e resolução nativa
resolve_glpi_entity_id para entidade1; não deduzido apenas do nome do host.

Lote candidato: três Computer na entidade1, identidade externa pelo marcador
Zabbix Host ID, sem inventar serial/hardware/owner/criticidade. Aplicação ainda
pendente: export anterior, comparação de qualquer registro sem marcador para
evitar duplicata física, criação por modelo/API nativo, atualização do vínculo
Hub pelo caminho existente, readback e rollback. Não executar antigo aplicador
sem rever essas precondições; três registros criados isoladamente não corrigem
automaticamente os645 tickets/incidentes anteriores.

## Preparação do aplicador restrito — 12/10 após 23:20 UTC

Reutilizado app.integrations.cmdb_sync, que antes aplicava a frota inteira.
Novo argumento opcional --hostids limita consulta e processamento a um até
cinco IDs únicos positivos; lista vazia/inválida/repetida/maior é recusada.
Resposta Zabbix com conjunto diferente do solicitado aborta antes de abrir
sessão GLPI. Execução sem argumento preserva comportamento anterior do timer.
Não houve deploy nem execução --apply nesta etapa.

TDD do guard de escopo: seis falhas observadas antes da implementação; sete
casos aprovados depois. Suíte infra completa: 96 passed + 3 subtests.
Suíte geral: 339 passed, 1 skipped, 72 failed na família
test_alert_glpi_idempotency por pywebpush ausente, como observado antes.
Não equivale a suite geral verde. Teste do guard puro não comprova integração
API/banco, escopo de update real ou rollback produtivo.

Próxima execução: validar candidatos sem marcador (nome serve somente como
detector de ambiguidade, nunca identidade), registrar estado anterior e
ensaiar percurso restrito em dry-run com retorno sanitizado. Não publicar nem
aplicar reconciliador amplo para reparar apenas os três hosts.

## Ensaio integrado restrito — 12/10 após 23:30 UTC

Código candidato dc5de8f executado em memória no container ninf-api existente,
sem substituir arquivo/imagem e sem --apply. Clientes normais Zabbix/GLPI e
dependências reais do runtime: dry-run exit0, mapped_assets0, linked_incidents0,
exatamente três gaps missing_glpi na entidade1 para10983/10984/10987.
Sessão GLPI encerrada pelo finally existente. Nenhuma atualização de ativos
ou incidentes; timer/reconciliador instalado permanece inalterado.

Detector de ambiguidade separado comparou nomes normalizados completos e
último componente de host/name Zabbix com Computer/NetworkEquipment GLPI,
incluindo excluídos e demais entidades: zero candidatos para os três.
Isso reduz risco de recriar registro sem marcador, mas nome não prova identidade
física nem substitui inventário por serial; itens serão identidades monitoradas,
nunca hardware certificado. Não exportadas descrições/serial/IP/credenciais.

Pendência de aplicação: registrar export protegido e plano de reversão,
validar aplicador nativo de criação (comentário do script antigo fixa data
2026-09-08 e deve ser corrigido antes de nova aplicação), então criar lote3,
ensaiar/aplicar atualização Hub restrita e reparar vínculos por ticket com
precondição de entidade/fingerprint. Não contar este dry-run como implantação.

## Preflight de escrita — 12/10 após 23:40 UTC

API normal getActiveProfile confirmou perfil12/computer=1: somente leitura.
Constantes lidas no runtime nativo: READ1, CREATE4, DELETE8. Nenhum POST foi
feito, ativo criado, perfil elevado ou superadmin reutilizado. Sessões fechadas.
Primeira leitura retornou campos nulos porque resposta usa active_profile;
schema corrigido antes da conclusão de direitos. Não tratar nulos como negação.

Nova dependência issue74: identidade temporária separada de manutenção,
Computer READ+CREATE+DELETE13 na entidade1 não recursiva, sem PURGE/admin.
Não modificar userid94/perfil12. O perfil limita entidade, não objetos:
executor restringe lote3 e rollback exclusivamente aos novosIDs. Credencial
apenas no cofre/arquivo root0600; nenhuma credencial por chat/email/Git.
Email de instrução enviado a Ismael com Ricardo em cópia, SENT1a1327f99024873b.
Não repetir cobrança nem tentar criação pelo modelo callAsSystem para
contornar os direitos da identidade de integração. Lote ainda não aplicado.

Enquanto isso, próximo trabalho independente: classificar os115 incidentes
sem ticket por idade/estado/causa e o backlog por evento/trigger, ou concluir
testes de escopo/rollback isolados. Não repetir contagem ampla já comprovada,
não apagar/resolver chamados em massa nem alterar SLAs sem contrato aprovado.

## Retomada humana e delegação de configuração

Usuário solicitou assumir configuração e resolver gaps. Leitura corrente:
perfil ness-maintenance-alupar13 existe, computer=1059, demais direitos não
nulos ausentes na consulta. Dicionário nativo Computer::getRights confirma:
1059=READ1+UPDATE2+READNOTE32+VIEWOWNED1024; não inclui CREATE4/DELETE8.
Necessário restringir computer a13 (READ1+CREATE4+DELETE8) antes de uso.
Não confundir ID13 do perfil com máscara13 de direitos.

Usuário svc_ness_maintenance106 ativo existe, mas consulta de Profile_User
não encontrou associação de perfil/entidade. Acesso técnico não resolvido.
Não houve criação/alteração pelo agente, nem troca de senha ou elevaçãoHub94.

Controle da sessão Windows não disponível (node_repl ausente), Browser Use
sem conexão com sessão humana na última verificação. Screenshot não é sessão
de API. Implementação administrativa depende de credencial administrativa
normal e protegida, ou de concluir perfil/vínculo/token nominalmente no GLPI;
autorização humana já foi dada, mas não fornece autenticação técnica.
Não contornar restrição via SQL ou callAsSystem para escrever configuração.

### Credencial disponibilizada e primeira correção por API

Usuário forneceu arquivo local de token sem conteúdo no chat. Transferido para
/etc/ness-os/glpi-maintenance.token root0600, temporário de transferência
removido. Login API normal confirmou userid58/perfil4; sessão encerrada.
Não imprimir token, incluir em argumentos/logs ou reusar no runtime Hub.

Snapshot protegido em /opt/n-infraops/rollback/glpi-maintenance-20261012/
profile-before.json: perfil13,computer1059,user106,sem bindings observadas.
Primeira execução abortou antes de escrita porque GET User106 foi403;
GET Profile13 funciona. Essa negação não foi contornada por SQL/modelo system.

Correção explícita do perfil13 via PUT Profile/13 com campo nativo _computer:
READ1+CREATE4+DELETE8; GET normal confirmou computer13. Demais direitos não
alterados; contaHub94/perfil12 intactos. API nativa Profile_User para associação
userid106/perfil13/entidade1/não-recursiva retornou400; nenhuma associação
aprovada nesta rodada. Sessão finally encerrada, nenhum ativo criado.
Preservada correção segura do perfil, sem alegar identidade pronta.

Próximo passo: diagnosticar contrato/escopo ativo da associação e confirmar
estado antes de nova tentativa; não repetir PUT da correção já comprovada.
Não gerar credencial do usuário106 até autorização de entidade válida.
Token administrativo temporário continua protegido somente para esta mudança,
com revogação ao término; ainda não revogado porque execução não concluída.

### Associação corrigida — sessão e cache de entidades

Admin58 tem perfil4 na raiz0 recursivo; User106 pertence à raiz0 mas não
tinha autorização. Código nativo Profile_User::canCreateItem exige leitura
do usuário e acesso à entidade. Sessão API com todas entidades selecionadas
refletia apenas IDs0/1/2/3, embora hierarquia SQL somente leitura tenha12
entidades válidas sob0/1. Esse cache impedia canViewAllEntities e GET User106.

Comando oficial cache:clear --context=core --no-interaction executado;
retornou exit1/Falha ao esvaziar o cache. Não marcar limpeza completa PASS.
Na sessão API nova, seleção autorizada de todas entidades passou a refletir12,
GET User106 passou e associação POST Profile_User retornou201:
binding125,userid106,perfil13,entidade1,não-recursivo; GET normal confirmou
todos os campos. Sessão finalmente encerrada. Isso prova reparo do percurso
e associação, não sucesso integral do comando de cache. Não repetir limpeza
sem diagnóstico específico de sua falha parcial.

ContaHub94/perfil12 preservados; não houve SQL de configuração ou callAsSystem.
Próximo passo: credencial separada do usuário106 por API normal e testes de
entidade permitida/negada, depois lote3. Nenhum ativo ainda criado.

### Credencial técnica e falha real de isolamento

Token106 gerado via PUT normal User/106/_regenerate_api_token; sessão admin
fechada. Campo nativo é cifrado em repouso: tentativa inicial de leitura
esperando40 caracteres falhou; não regenerado. GLPIKey nativo decifrou somente
para arquivo root0600 /etc/ness-os/glpi-alupar-maintenance.token, sem saída de
valor, argumento ou alteração de cifragem no banco. Login técnico106/perfil13/
computer13 PASS; sessões encerradas.

Teste negativo não passou. ChangeActiveEntities para0 retorna200 mas continua1;
para5(subentidadeAluparPE) retorna200 e muda efetivamente para5; para8 mantém5.
Computer de entidade5: GET antes da troca403, após troca200/entities_id5.
Assim, não alegar isolamento não-recursivo pelo binding125/is_recursive0.
Nenhum ativo criado, alterado ou copiado nos testes; saída somente status/IDs.

Contenção por API normal: desativação exclusivamente userid106, readback
is_active0 PASS. ContaHub94/perfil12 e usuário administrativo58 intactos.
Não reativar manutenção até diagnóstico de seleção de entidades nativa e
teste negativo passar. Tokens permanecem protegidos; nenhum segredo no Git.
Próximo passo: localizar causa na seleção de entidades/API e corrigir com
regressão/rollback, sem declarar G2 ou lote3 aprovado. Criação continua pendente.

### Causa identificada — seleção nativa de descendentes

Session::changeActiveEntities na instalação permite seleção quando o ID
é a própria entidade ou descendente; se pedido is_recursive=false, condição
(!$is_recursive || $val['is_recursive']) autoriza mesmo binding não recursivo.
Depois haveAccessToEntity confia nas entidades ativas da sessão. Isso explica
GET Computer da entidade5 passar após seleção, sem mudar Profile_User125.
Não foi problema de payload ignorado, token incorreto ou privilégio do Hub.

Código oficial tag11.0.11 inspecionado contém a mesma condição. Não afirmar
que upgrade sozinho resolve, nem rotular como CVE/vulnerabilidade upstream
sem avaliação da semântica suportada e reprodução na versão atual. É um gap
comprovado em relação ao requisito do projeto de acesso somente entidade1.
Fonte: https://github.com/glpi-project/glpi/blob/11.0.11/src/Session.php

Contenção mantém106 inativo. Próxima implementação independente: guard no
cliente do Hub que confira grants e entidade efetiva antes de operação, com
regressão de seleção silenciosa/fallback. Isso evita erro do nosso consumidor,
mas não corrige uso direto de token na API nativa; não reativar106 nem aprovar
G2 por esse guard. Solução definitiva exige caminho suportado de autorização
estrita (plugin/gateway isolado ou desenho de entidades aprovado), export,
ensaio e rollback; não editar core ou mover entidades/tickets em massa.

### Execução independente — confiabilidade da entrega de tickets

O cliente do Hub agora verifica a entidade efetiva, percorre páginas da
busca do marcador e trata 401/403 como recusa permanente. Uma mudança ainda
não promovida distingue transporte/429/5xx e agenda retry exponencial
limitado para falha transitória. A seleção de entidade também trata queda de
transporte e fecha a sessão. Testes backend: 423 PASS, 1 SKIP. Isso não
substitui o isolamento da API nativa nem reativa o usuário 106.

Consulta agregada e somente leitura do banco do Hub: 159 incidentes sem
ticket, divididos em 115 antigos sem falha registrada, 29 recentes com
falha de entrega não classificada e 15 sem ID de evento. Os 29 recentes
surgiram em 13/10 02:00 UTC; logs sanitizados mostraram 116 `ConnectError`
do GLPI. O probe `glpi_readiness` voltou a ready/dry-run, sem testar escrita.
O classificador paginado somente leitura retornou os mesmos 159 no Hub em
13/10 02:20 UTC, cursor 76656 e sem página adicional. Sua saída agrega as
classes sem IDs nem payloads; status da fila Celery não é inferido pelo banco.
Testes de classificação: 3 PASS. Não houve replay, alteração de ticket ou
deploy. A próxima unidade é um ensaio idempotente restrito;
não inferir que os 115 antigos são seguros para replay automático.

Ensaio unitário adicional de timeout após POST: a resposta é perdida, mas o
ticket fica pesquisável; o replay o reutiliza sem novo POST. Suíte backend:
426 PASS, 1 SKIP. Depois de 12 retries transitórios, o worker grava ação
`ticket_retry_exhausted` sem payload e mantém a tarefa falha; o classificador
reporta essa classe separadamente. Isto não prova corrida entre workers ou consistência
imediata da busca GLPI; ainda falta teste concorrente e canário real.

Serialização entre workers foi implementada na release candidata com
`pg_advisory_xact_lock(bigint)` por entidade+fingerprint, adquirido antes da
busca e liberado com o fim da transação. Timeout de lock de 15 s vira falha
transitória, sem POST. Dois workers simulados produziram um POST e sonda no
PostgreSQL real confirmou espera serializada sem escrita. Suíte backend:
428 PASS, 1 SKIP. Isto não garante que um POST cuja resposta se perdeu já
estará pesquisável imediatamente no GLPI; canário real e gate de produção
seguem pendentes. GH Actions não iniciou os cinco jobs do commit 80ee26c
por faturamento/limite da conta (annotation do job 115098127227); issue 67
já contém ação humana. Não foi feito deploy nem replay.

Estado posterior: usuário tornou o repositório público e os cinco jobs do
PR #64 passaram a iniciar. No commit `5a68c63`, secret scan, frontend e SBOM
passaram; backend parou em seis arquivos sem Black e lint no import de
`blake2b`. Formatação, import e anotação MyPy corrigidos; Black `--check .`,
flake8 estrito, Ruff lint/format, MyPy e 428 testes passaram localmente.
Checks remotos da nova revisão ainda devem ser confirmados antes de G0.

# NessAI — erro HTTP do assistente (13/10)

O endpoint do plugin versionado agora devolve erro genérico HTTP 500 quando
uma exceção interna ocorre, sem repassar a mensagem do provedor ao navegador.
Parâmetro inválido continua HTTP 400. Teste sintético RED→GREEN, teste de
resposta autorizada, negação de ticket e lint PHP passaram em contêiner
isolado. O plugin **não está implantado**; a resposta de erro produzida
normalmente por `callLLM`, a pesquisa KB entre entidades e a política de
dados enviados à IA ainda precisam de revisão antes de qualquer ativação.

O assistente também deixou de concatenar a mensagem interna de uma falha ao
descriptografar a chave na resposta. Teste sintético RED→GREEN e lint PHP
passaram; erros HTTP do provedor ainda requerem sanitização independente.

### T12 — ness. AI: configuração de provedor não exposta (13/10 07:37 UTC)

Teste sintético RED demonstrou que um valor inválido de `llm_provider` aparecia na resposta ao operador. A preparação da requisição agora retorna erro genérico e registra apenas a classe da exceção. Cinco testes PHP do plugin e lint do arquivo alterado passaram em contêiner descartável sem rede; o plugin **não** foi instalado nem ativado. Permanecem bloqueios de privacidade do prompt, KB por tenant, erros HTTP externos e validação integrada. T03/G2 e a conta 106 não mudam.

### T12 — ness. AI: erros HTTP e JSON do provedor (13/10 07:45 UTC)

Um provedor HTTP local sintético reproduziu dois vazamentos: mensagem do erro 429 enviada ao operador e corpo JSON inválido copiado ao log. Os dois casos falharam antes da correção e passaram depois; resposta e log agora incluem só a classe de falha/status, sem texto externo. Seis testes PHP do plugin, lint dos arquivos afetados e backend 460 PASS/1 SKIP (25 avisos preexistentes) foram executados. O plugin continua fora do runtime. Ainda faltam revisão de dados enviados à IA, KB por tenant, transporte/parse de sucesso e validação integrada; T03/106 não mudam.
