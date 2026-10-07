# Reconciliação dos dashboards do Zabbix — 02/09/2026

## Problema observado

O dashboard inicial `Global view` ainda era o modelo padrão do Zabbix. Ele
continha um geomap limitado ao próprio servidor e com visão inicial em Riga,
um ranking de CPU restrito ao host do Zabbix e widgets estreitos com rolagem
horizontal. Já existia um dashboard operacional mais completo, mas estava
privado e continha outra página de mapa sem utilidade comprovada.

## Mudança aplicada

O dashboard de ID `1` foi mantido como destino inicial e transformado em
`NOC — Visão Operacional`, com uma página e oito widgets nativos:

1. saúde da plataforma;
2. disponibilidade geral;
3. problemas por severidade;
4. incidentes ativos de todos os clientes;
5. hosts com problemas;
6. fila total de coleta;
7. itens atrasados há mais de dez minutos;
8. ranking global de CPU, carga e processos.

O filtro que restringia o ranking de capacidade ao próprio servidor foi
removido. Os dois indicadores de fila usam cores semânticas e BlueDot
`#00ade8` como estado-base.

O dashboard de ID `405` passou a se chamar `NOC — Operação e Clientes`, tornou-se
público e preservou quatro páginas segmentadas: visão geral, Alupar, TBE/TNE e
clientes corporativos. A página padrão `Mapa Global`, que não tinha contexto
operacional adequado, foi removida.

Uma auditoria posterior confirmou coordenadas válidas em 248 dos 252 hosts
habilitados. Por isso, foi criada uma quinta página, `Mapa — São Paulo`, com um
geomap operacional centrado em São Paulo, SP (`-23.5505,-46.6333`, zoom `5`).
O mapa permanece fora da primeira página para não competir com os indicadores
críticos, mas permite visualizar a distribuição regional dos ativos.

Após validação das localidades, os dois links da Cavan anteriormente sem
coordenadas foram posicionados em Bacabeira, Maranhão (`-2.971,-44.316`), e o
host `esper` foi posicionado na Rua George Ohm, 230, Cidade Monções, São Paulo
(`-23.6117978,-46.6934633`). Com isso, 251 dos 252 hosts habilitados passaram a
ter coordenadas válidas; apenas `INTRANET - Producao` permanece pendente.

Os títulos visuais não incluem a assinatura `ness.`, pois o frontend nativo do
Zabbix não permite garantir Montserrat 500, lettering preto/branco e BlueDot
separado. Isso evita uma aplicação visual incompleta da marca.

## Segurança e rollback

A API suportada `dashboard.update` foi utilizada. O estado completo anterior,
os payloads aplicados e payloads de rollback estão preservados, com modo 0600,
em:

`/var/lib/ness-os/restore-evidence/dashboard-reconcile-20260902T160611-0300`

## Verificação

- dashboard inicial público: uma página, oito widgets e nenhum geomap;
- dashboard operacional público: cinco páginas, 32 widgets e um geomap;
- geomap centrado em São Paulo, sem referências ativas a Riga;
- inventário: 251 hosts com coordenadas válidas, um sem coordenadas e nenhum
  par de coordenadas inválido;
- referências de fila: itens `23272` e `23271`;
- ranking de CPU sem restrição ao host local;
- geometria dentro da grade de 72 colunas e sem sobreposição;
- nenhuma nova representação textual da marca nos títulos dos widgets.

A evidência e o estado anterior da inclusão do mapa estão preservados em:

`/var/lib/ness-os/restore-evidence/dashboard-sp-map-20260902T161023-0300`

O estado anterior e o payload de rollback das três localizações cadastradas
estão preservados em:

`/var/lib/ness-os/restore-evidence/host-location-20260902T161430-0300`

A inspeção visual final depende de recarregar a sessão autenticada no
navegador; a API, o centro do mapa e a geometria foram validados no servidor.
