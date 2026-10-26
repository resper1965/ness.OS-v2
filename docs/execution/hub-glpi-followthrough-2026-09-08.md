# Hub/GLPI — execução dos itens 2 a 5

Complemento final: [plano consolidado executado](hub-glpi-work-plan-2026-09-08.md).
A prova positiva OIDC desse plano detectou e corrigiu uma versão antiga de
`core/oidc.py` em produção; o HTTP 400 de código inválido registrado abaixo não
era suficiente para comprovar funcionamento da troca de tokens.

Data: 08/09/2026. Escopo autorizado: solução GLPI, acessos, monitoramento da
integração e reconciliação dos ativos monitorados. Gemini/faturamento não alterados.

## 2. Solução e reconhecimento idempotente

O callback autenticado passa a provocar uma consulta ao GLPI. O hub confere o
marcador do ticket, sua entidade e seu status atual, e lê `ITILSolution` pela API.
Soluções recusadas são descartadas; HTML é convertido para texto. Texto fornecido
no callback não substitui a solução oficial.

O hub salva solução e ID da solução antes do reconhecimento Zabbix. Se houver
relatório, acrescenta a solução uma única vez por ID e invalida o embedding antigo;
não depende de Gemini para concluir o fechamento. O worker serializa callbacks
por ticket e consulta o evento original antes de publicar o marcador
`[ness-glpi-resolution:<ticket_id>]`. Falha de sincronização deixa estado pendente
e segue a política de retry existente.

Prova integrada: ticket interno 1, solução GLPI 1, evento Zabbix 53615770.
Texto importado: “Validação interna: trapper sintético retornou a zero;
recuperação do evento confirmada.” O ticket interno foi reaberto e solucionado
somente para essa prova. Após dois reenvios autenticados, permaneceu exatamente
um reconhecimento com o novo marcador. Estado local `resolved`, sincronização
`synced`. Tickets reais de clientes não foram solucionados nessa validação.

## 3. Acesso e isolamento

- Listagem persistida do hub filtra incidentes pelo tenant do usuário; operador
  pode consultar todos. Tentativa de cliente selecionar outro tenant retorna 403.
- `/api/assets/cmdb` aplica a mesma restrição. Saúde global da integração é NOC.
- Verificação no endereço público do hub com três contas temporárias: Alupar,
  Cavan e NOC. Login, cookie Secure/HttpOnly/SameSite, `/me`, logout, senha errada,
  expiração, conta desativada e negação de papel forjado no JWT passaram.
- Alupar recebeu 73 incidentes e 146 ativos; Cavan recebeu 12 incidentes e 27
  ativos no instante dessa verificação. NOC recebeu a listagem global limitada
  a 100 incidentes e os 254 ativos. Todas as contas temporárias foram removidas.
- GLPI: contas temporárias com perfil Read-Only 8, restritas às entidades 1 e 8,
  abriram seus próprios tickets (HTTP 200); ticket do outro cliente retornou 403.
  Troca de entidade não autorizada foi recusada. GLPI retorna HTTP 200 com corpo
  `false` nesse caso; o cliente Python agora trata isso como recusa.
- O Computer 1, servidor Zabbix interno da Ness, tinha compartilhamento recursivo.
  Foi alterado `is_recursive: 1 → 0`, preservando entidade e cadastro. Repetição
  do teste confirmou que clientes não conseguem consultar esse ativo interno.
- Nenhuma conta temporária GLPI permaneceu cadastrada após as provas.

Limite: verificações autenticadas HTTP/API foram executadas; a jornada visual
com SSO humano não foi reexecutada porque a ferramenta informou que não há
navegador disponível. Não se declara homologação completa de MFA ou do Authentik.

## 4. Monitoramento contínuo

O indicador antigo considerava Redis acessível como worker saudável. Agora:

- verifica leituras autenticadas GLPI/Zabbix;
- consulta consumidores Celery, com timeout, e tamanhos das filas;
- registra retries e falhas finais de ingestão/resolução em ledger Redis limitado
  a 1.000 registros, com retenção de 30 dias e sem payloads/credenciais;
- acusa incidente sem ticket por mais de cinco minutos e resolução pendente;
- expõe resultado a operadores em `/api/dashboard/pipeline-status` e no portal.

Timer `ness-hub-integration-monitor.timer`: a cada minuto; relatório protegido em
`/var/lib/ness-os/hub-integration/status.json`; falha gera saída não zero na unit
systemd. Sem ativação de WhatsApp, push ou e-mail.

Última verificação registrada: dois workers, consumidores nas três filas,
filas vazias, zero falhas finais/retries registrados, zero incidentes v1 sem
ticket e zero resoluções pendentes. Isso verifica a integração, não a disponibilidade
da IA: a cota Gemini continua sendo uma pendência separada.

## 5. Inventário e vínculos

- GLPI possuía 239 registros e o hub apenas um registro legado.
- Importação administrativa pela camada de modelos GLPI criou 17 registros
  faltantes: 16 Computer (86–101) e NetworkEquipment 156 (firewall Cavan).
- Reconciliação usa exclusivamente ID Zabbix e entidade exata. Não usa IP
  compartilhado nem semelhança de nomes para unir ativos de clientes.
- **254 ativos reconciliados no hub**, todos com responsável identificado por
  metadado existente ou equipe operacional padrão infraops/NOC.
- Criados vínculos de responsabilidade apenas onde não havia responsável:
  equipes por entidade, não recursivas, sem membros nem permissões novas para
  usuários; grupo infraops 13 preservado na entidade interna. Responsáveis
  previamente informados, inclusive tags de owner Cavan, preservados.
- Serviço GLPI 94/perfil 12 ganhou somente leitura de Computer, NetworkEquipment
  e Group. Permissões de User e Location usadas durante a investigação foram
  revertidas a zero. Sem concessão de escrita de inventário ao serviço.
- **113 tickets existentes receberam vínculo nativo ao ativo**, sem sobrescrever
  vínculos anteriores. Criação futura já inclui `items_id` e verifica a entidade.
  Tickets reais 117–121 demonstraram vínculos automáticos corretos após a mudança.
- Timer `ness-hub-cmdb-sync.timer`: reconcilia a cada hora, sem criar nem apagar
  ativos GLPI. Relatório: `/var/lib/ness-os/hub-integration/cmdb.json`.
- Portal de incidentes mostra ativo, responsável e solução oficial.
- Tipo `unknown` acrescentado ao enum PostgreSQL/Python: ausência de evidência
  sobre SO não é convertida em uma afirmação de que o ativo roda Linux.

Exceções explícitas:

1. Host **10899**, link Mundivox: responsável confirmou **Ness** após a implantação.
   NetworkEquipment 130 corrigido da entidade Alupar (1) para Ness (0), sem
   compartilhamento recursivo, com equipe infraops 13. Nome de exibição corrigido
   no GLPI e no Zabbix; nome técnico e ID Zabbix preservados. Reconciliação
   verificada com **255 ativos** no hub, incluindo esse ativo. Snapshot anterior
   em `hub-followthrough-20260908/host10899-before.json` no diretório de rollback
   do hub e `/var/lib/ness-os/hub-rollout/host10899-before.json` no Zabbix.
   Não havia incidentes locais desse host
   nem tickets vinculados ao ativo no momento da correção.
2. Host **10962** (`esper`): sem cliente, continua excluído.
3. Host **10978**: teste sintético, não representa equipamento de CMDB.

Essa reconciliação cobre identidades monitoradas e vínculos operacionais. Não
foi ativado GLPI Agent nem descoberta de hardware. A consolidação física dos
testes WAN e a migração de classificações históricas Cavan continuam sendo
mudanças separadas; nenhum histórico foi eliminado.

## Verificação e recuperação

Backend: **201 testes aprovados**, incluindo resolução, reentrega, recusa de
entidade, seleção exata de ativo, isolamento de cliente, worker ausente e falha
final visível. Ruff passou nos arquivos afetados. Build remoto do frontend
aprovado e imagem implantada. O typecheck global preexistente continua fora
desta declaração de aprovação.

Backup: `/opt/n-infraops/rollback/hub-followthrough-20260908/`, protegido para root.
Contém `app-before.tar.gz`, planos de reconciliação, registros dos objetos/vínculos
criados, snapshot `root-asset-before.json` e log de build. Imagem anterior:
`ness-frontend:rollback-followthrough-20260908`.

Rollback operacional: parar/desabilitar os dois timers; restaurar módulos
afetados e imagem anterior, depois recriar/reiniciar somente os serviços
necessários. **Preservar a compatibilidade do enum `AssetType.UNKNOWN` mesmo
ao restaurar código anterior**, pois registros reconciliados já podem usar o
novo valor. A expansão SQL não deve ser revertida reclassificando SO sem evidência.

Preservar os tickets, soluções e ativos já produzidos. Se for necessário reverter
vínculos/grupos/ativos, usar exclusivamente os IDs dos manifestos e a camada
nativa GLPI, após conferir referências criadas desde a implantação. Não executar
exclusão em massa por nome. A antiga visibilidade recursiva do servidor interno
não deve ser restaurada como parte de um rollback genérico.

## Complemento SSO — 08/09/2026, 20:06 UTC

Implantado no callback OIDC: contas locais desativadas não recebem sessão;
identidades de cliente precisam de `tenant_id` textual, normalizado para
minúsculas; token de acesso não substitui um ID token ausente.

No provider Authentik `hub-ness`, o mapeamento de escopo `groups` agora envia
também o atributo `tenant_id`. Foi criado o mapeamento exclusivo
`NESS Hub groups and tenant` (27b28d8f-0b77-4239-9f4f-2a16d11c45f6), mantendo o
mapeamento antigo disponível aos demais providers. A expressão antiga usava
`ak_groups`, ainda funcional nesta versão, mas depreciado; a nova usa `groups`.
A expressão foi avaliada com sucesso para os 37 usuários internos ativos.

O usuário confirmou que as três contas com vínculo Cavan/Alupar e grupo `noc`
são operadores da Ness, autorizados a visualizar todos os clientes. Suas
associações e permissões foram preservadas; o vínculo de cliente não restringe
um papel operacional NOC.

Verificação: **207 testes aprovados**, Ruff aprovado nos dois arquivos desta
alteração e importação do módulo aprovada no container antes do reinício da API.
Discovery OIDC público retornou 200; código inválido retornou 400 sem cookie;
`/api/auth/me` anônimo retornou 401. Após reinício: Zabbix/GLPI saudáveis,
dois workers, filas vazias, zero falhas/retries, zero incidentes sem ticket
há mais de cinco minutos e zero resoluções pendentes.

Backup: `/opt/n-infraops/rollback/hub-sso-20260908/`, com `auth.py` anterior e
`provider-before.json` contendo os IDs dos mapeamentos anteriores. Para reverter,
restaurar somente esse módulo, reiniciar a API e restaurar as associações do
provider pelos IDs do snapshot, preservando os outros providers.

Pendente: login interativo completo com conta humana/MFA no navegador; as
verificações acima não substituem essa etapa e não emitiram sessão humana.
