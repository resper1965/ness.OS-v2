# GLPI — retomada operacional de 12/10/2026

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
