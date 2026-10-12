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
