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
