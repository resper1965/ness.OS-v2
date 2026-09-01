# Zabbix UAT — baseline de polimento operacional

Data: 2026-08-26 (BRT)
Escopo: inventário somente-leitura da cópia restaurada em `zbx-prd-01`.

## Proteções confirmadas

- `zabbix-server` permanece `masked` e `inactive`.
- Ações e tipos de mídia permanecem desabilitados.
- Nenhuma coleta, notificação, template ou objeto de produção foi alterado por
  este diagnóstico.

## Fotografia inicial

| Indicador | Quantidade |
| --- | ---: |
| Hosts cadastrados | 611 |
| Hosts habilitados | 249 |
| Grupos de hosts | 240 |
| Grupos sem hosts | 49 |
| Itens habilitados | 18.189 |
| Triggers habilitados | 6.355 |
| Problemas sem resolução histórica | 1.985 |
| Hosts sem tags | 254 |
| Mapas | 1 (`Local network`) |
| Hosts em manutenção | 0 |

### Distribuição dos problemas históricos abertos

| Severidade | Quantidade |
| --- | ---: |
| Não classificado | 1.446 |
| Informação | 6 |
| Atenção | 220 |
| Média | 281 |
| Alta | 24 |
| Desastre | 8 |

Esses problemas são estado herdado da restauração: não devem produzir
notificação enquanto a coleta estiver inativa, nem devem ser apagados em lote.

## Diagnóstico

- A árvore de grupos mistura cliente, localidade, tipo de ativo e plataforma.
  Exemplos recorrentes: `[ Alupar ]`, `[ Alupar ] [ Matriz ]` e
  `[ Alupar ] [ Matriz ] [ Servidor ]`.
- Há 49 grupos vazios e 254 hosts sem tags, o que impede leitura executiva e
  filtragem operacional consistentes.
- Um único mapa não é suficiente para representar cliente, região e serviços.
- O ambiente tem capacidade para ser tratado por ondas; 249 hosts habilitados
  não justificam ativação imediata dos 611 registros restaurados.

## Plano de polimento antes da coleta

1. **Modelo e saneamento semântico.** Definir convenção de hostname, owner,
   cliente, serviço, ambiente, criticidade, localidade e tipo de ativo. Não
   remover grupos ainda; marcar os 49 vazios como candidatos à quarentena.
2. **Piloto controlado.** Escolher um cliente/localidade e no máximo 25 hosts;
   preencher tags e owners, revisar templates e classificar os problemas
   históricos desse subconjunto.
3. **Mapas e visão executiva.** Criar mapas por cliente/região/serviço usando
   dados validados no piloto, e não a topologia inteira restaurada.
4. **Ruído e incidentes.** Revisar triggers por severidade, dependência e
   janela de manutenção. Alerta só será encaminhado quando houver regra de
   correlação/qualificação para incidente.
5. **Expansão por ondas.** Replicar o padrão para os demais ativos somente
   após aceite do piloto. A ativação de coleta continua sendo uma decisão
   separada, com janela e rollback.

## Piloto definido

- Cliente/localidade: **Cavan — Matriz**.
- Classificação organizacional: **cliente/tenant**.
- Ambiente: **produção**.
- Escopo: os 14 hosts habilitados da localidade, cobrindo servidores,
  virtualização, firewall/rede e o proxy Zabbix.
- Owner operacional: **Ricardo Esper**.
- Conectividade: AmericaNet (WAN1) é o link preferencial; Vivo (LAN3) compõe
  balanceamento ativo, não contingência passiva.
- Regra de severidade aprovada: indisponibilidade de um link é **Atenção**;
  indisponibilidade simultânea dos dois é **Crítica**. A regra será criada por
  correlação/dependência, sem notificações nesta fase de UAT.
- Mapas aprovados: duas visões separadas — infraestrutura física/conectividade
  e serviços de negócio.

## Hipótese funcional do piloto

Classificação inferida pelos nomes técnicos e templates atuais; será corrigida
quando houver informação de negócio melhor.

| Ativos | Função inferida | Visão inicial |
| --- | --- | --- |
| AmericaNet WAN1 e Vivo LAN3 | conectividade do firewall em balanceamento | infraestrutura |
| `SW01-SP-Core` | comutação/core da Matriz | infraestrutura |
| `ESXI01`, `ESXI02`, `ESXI03` | hosts de virtualização | infraestrutura e dependência dos serviços |
| `CL-AD02`, `VMAD01` | diretório/identidade; `VMAD01` também pode prover arquivos | serviços |
| `VMAPP01`, `VMAPP02`, `VMAPH01` | aplicações internas | serviços |
| `VMSQLP01` | banco de dados | serviços |
| `VMRDS01` | acesso remoto | serviços |
| `Proxy Zabbix` | componente local de monitoramento | infraestrutura |

`SW01-SP-Core` usa atualmente um template FortiGate por HTTP, apesar do nome
indicar switch. O template é uma inconsistência a ser revisada no piloto, sem
substituição automática.

O piloto permanece limitado a esse recorte. Qualquer expansão ou ativação de
coleta será tratada como decisão separada.

## Diretriz de referência do tenant

Cavan é o tenant-referência do ness.OS. O piloto não se limita ao
monitoramento: deve estabelecer o padrão reutilizável de operação, SecOps,
ITSM/GLPI, portal executivo, inventário, runbooks, relatórios e experiência
do cliente. Cada entrega deverá manter segregação por tenant e não pressupor
acesso aos demais clientes.

Até a entrada em operação, o tenant será conduzido internamente pela ness.,
com **Ismael Araújo** como responsável técnico. Não serão criados usuários do
cliente nem compartilhados painéis externos antes da definição formal dos
responsáveis da Cavan.

Quando habilitado, o perfil padrão do cliente será **somente leitura**:
consulta de saúde, serviços, ativos e relatórios do próprio tenant. Operação,
reconhecimento de eventos, alterações de inventário, ações e abertura técnica
de tickets permanecem responsabilidades da ness.

## Etiquetagem aplicada

Em 2026-08-26, os 14 hosts do piloto receberam, via API do Zabbix, as tags
`tenant=cavan`, `site=matriz`, `environment=production`,
`owner=ricardo-esper` e `pilot=true`, além de `role` e `criticality` por
função. Os dois links receberam `connectivity=load-balanced`; AmericaNet foi
marcado como `link_preference=primary` e Vivo como `active`.

- Infraestrutura crítica: conectividade, core, hosts ESXi e diretório/arquivos.
- Serviços altos: aplicações, banco, acesso remoto e proxy de monitoramento.
- Confirmação pós-gravação: 14 hosts etiquetados e acessíveis no recorte da
  API; ações, mídia e `zabbix-server` continuam desabilitados.

## Mapas UAT criados

Dois mapas com 14 elementos e 13 relações cada foram criados sem alterar a
coleta:

- `[ Cavan ] [ Matriz ] - Infraestrutura UAT` (id 2): camada de conectividade,
  core, hosts físicos/virtuais e proxy de monitoramento para uso interno.
- `[ Cavan ] [ Matriz ] - Servicos UAT` (id 3): mesma topologia com rótulos de
  conectividade, identidade/arquivos, aplicações, banco e acesso remoto; esta
  é a base da visão orientada a serviços do futuro portal do cliente.

### Integração técnica temporária

- Conta: `ness-os-integracoes`.
- Grupo de acesso: `ness-os-cavan-matriz-pilot-api`, com escrita somente no
  grupo do piloto e leitura dos grupos de templates necessários.
- Token: `cavan-matriz-pilot-write`, válido até 2026-09-25. Seu valor está em
  arquivo protegido (`root:root`, `0600`) fora do repositório e não é exposto
  nesta documentação.
- A restauração continha gatilhos de auditoria com o definer MariaDB ausente
  `usrzabbix@localhost`. O usuário técnico local foi restaurado, sem acesso
  remoto e limitado ao banco `dbzabbix`, para permitir que a auditoria de
  alterações volte a funcionar.
