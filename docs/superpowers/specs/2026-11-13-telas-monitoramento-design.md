# Telas de monitoramento do Hub — redesenho

- Data: 13/11/2026
- Pedido: Ricardo — "as interfaces não são compatíveis com um sistema de monitoramento, não trazem informação nem filtro".
- Base: código em `main` (`App.tsx`, `CoreDashboard`, `IncidentsPage`, `SecopsModule`) e dados de produção lidos em 13/11.

## O que os dados mostram (13/11, produção)

| Medida | Valor |
|---|---|
| Linhas em `n_infraops_incidents` | 128.352, todas `open` exceto 1 |
| Problemas distintos ainda ativos no Zabbix (host+trigger, `ninf_zabbix_status=problem`) | 782 (1 desastre, 11 alta, 598 média, 167 atenção, 5 info) |
| Recuperados no Zabbix, mas `open` no Hub | 49.461 |
| Sem estado da fonte e parados há mais de 7 dias | 75.325 |
| Eventos novos por dia (última semana) | ~2.000–2.600 |
| Ids de chamado GLPI distintos gravados | 127.391 |
| Incidentes atribuídos a alguém | 0 |
| Cliente com grafia duplicada | `Ness`/`NESS`, `Alupar`/`ALUPAR` |
| Ruído principal | `AppXSvc is not running` em 4 hosts GCE = ~16 mil linhas |

Conclusão: a tela não informa porque a lista mistura evento com problema. O operador precisa ver os **782 problemas ativos agrupados**, não 128 mil linhas abertas. Qualquer tela nova sobre a lista atual continua inútil.

## Princípios (todas as telas)

1. **Problema ativo é a unidade**, não o evento: agrupado por host + gatilho, com contador de recorrência.
2. **Barra de filtros fixa no topo**, igual em todas as telas: cliente, severidade, estado, período, busca livre. Filtro vive na URL (`?view=…&cliente=…&sev=4,5`) — recarregar e compartilhar mantém.
3. **Cada filtro mostra contagem** ("Alta 11", "Média 598") para o operador saber o tamanho antes de clicar.
4. **Tabela densa** (linha de 36 px, mono em números), ordenável, com a mais grave e mais antiga em cima.
5. **Frescor visível**: toda tela diz de onde veio o dado e há quanto tempo; fonte parada vira faixa âmbar, não tela vazia.
6. Atualização automática a cada 30 s sem perder rolagem nem filtro.
7. ness. design system: escuro, BlueDot só para ação/foco, severidade por cor + texto (nunca só cor).

## Telas

### 1. Visão geral (NOC)
Responde: *algum cliente está mal agora?*
- Faixa de KPIs: problemas ativos · desastre+alta · hosts afetados · eventos 24 h · fontes com falha.
- **Matriz por cliente** (linhas) × severidade (colunas), com hosts afetados, chamados abertos e o problema mais antigo. Clique na célula abre Problemas já filtrado.
- Gráfico de eventos por hora (24 h), empilhado por severidade.
- Fontes (Zabbix, GLPI, Wazuh) numa linha compacta no rodapé, com última coleta.

### 2. Monitoramento → **Problemas**
Responde: *o que está quebrado, onde, há quanto tempo?*
- Tabela: severidade · cliente · host · problema · desde (duração) · recorrências · reconhecido · chamado GLPI.
- Agrupar por: nenhum | cliente | host.
- Filtros: cliente, severidade, reconhecido sim/não, com/sem chamado, duração mínima, busca.
- Painel lateral ao clicar: histórico do mesmo host+gatilho (30 dias), análise da IA, link do chamado.

### 3. Incidentes
Responde: *qual atendimento está comigo e qual está atrasado?*
- Fila com abas e contagem: Ativos na fonte · Recuperados aguardando chamado · Encerrados.
- Filtros: cliente, severidade, responsável ("meus"), período, busca; colunas de SLA quando o contrato existir.
- Detalhe em painel lateral (não troca de tela): linha do tempo, chamado, ações.

### 4. Ativos (nova, no grupo Operação)
Responde: *como está este host?*
- Lista de hosts com cliente, problemas ativos, último evento, origem (Zabbix/GLPI).
- Detalhe do host: problemas ativos, histórico, item GLPI ligado.

### 5. Segurança
- Mantém CVE intel e triagem com a mesma barra de filtros.
- Bloco Wazuh mostra "planejado" até a Onda 2; nada de tela vazia fingindo dado.

### 6. Nuvem
- Fica como o PR #260 (já no kit), só ganha a barra de filtros comum.

## Fora do escopo
- Mudar o pipeline que abre chamado por evento (127 mil ids). É problema real, mas é do pipeline; vira issue própria.
- Edição em massa, painéis configuráveis, tema claro.

## Entrega em fases

| Fase | O que | Depende de API nova? | Quando |
|---|---|---|---|
| F1 | Barra de filtros comum + Problemas (Zabbix ao vivo via `/api/dashboard/problems`) + Incidentes com filtros que a API já aceita (status, cliente, período) | Não | Antes do cutover, só frontend |
| F2 | API: `GET /api/problems` (agregado host+gatilho do banco, com facetas), `GET /api/overview/customers` (matriz), `severity`/`q` em `/api/incidents`; normalizar grafia de cliente | Sim | Código já; promoção depois do D+2 |
| F3 | Visão geral NOC, Ativos e painéis laterais sobre a F2 | Sim | Depois do D+2 |

## Decisões do agente (revisáveis)
- "Problema ativo" = host+gatilho com `ninf_zabbix_status=problem`; o incidente continua fechando pelo GLPI (worker de resolução), sem mudar regra de negócio.
- Matriz por cliente no lugar de cartões soltos: é o padrão de NOC multi-cliente.
- Ativos entra como tela nova porque hoje não há como olhar um host.
