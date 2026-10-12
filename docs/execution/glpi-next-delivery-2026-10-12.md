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
