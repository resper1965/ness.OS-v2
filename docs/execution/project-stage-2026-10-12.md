# Zabbix — estágio de 12/10/2026

Atualização: restore terminou 12:38:46 BRT / 15:38:46 UTC.
Owner operacional: plataforma ness.; ticket GLPI 75426.

| Entrega | Estado comprovado |
| --- | --- |
| Origem | Continua sendo produção e rollback; DNS não alterado |
| Refresh definitivo | PASS: snapshot f0b19cf8 importado no destino, frontend sincronizado |
| Paridade de inventário | PASS: 325 registros (262 hosts reais + 63 protótipos), tags e templates iguais na origem/destino |
| Banco/API/frontend | Schema 7.0; API 7.0.27; HTTP 200; durabilidade=1 |
| Isolamento | Server inativo/mascarado; sem listener 10051; canais externos desligados |
| Marca | Hook nativo e assets servidos; referência de login confirmada; renderização ainda não inspecionada |
| Qualidade de coleta | Todos os hosts no escopo; causas SNMP prioritárias identificadas; não corrigidas ainda |
| SSO/API UAT | Recuperação e configuração SAML aprovadas; login nominal/MFA ainda pendentes |
| Corte produtivo | Não executado; gates/SSO, freeze final e rollback de corte ainda necessários |

Próxima sequência: recuperar acesso administrativo UAT pelo canal autorizado;
conferir provider UAT e certificado; homologar login e API mínima; corrigir
coleta em ondas de até cinco; executar critérios de corte. Dependência humana
registrada na issue #51 com instruções enviadas por e-mail. Não repetir o
restore concluído nem elevar a identidade de leitura do Hub.

Evidências detalhadas: [janela e resultado](zabbix-production-window-2026-10-12.md).
Este estágio não declara entrega total em produção nem aceita G2 por exceção.

## Recuperação autorizada — continuação de 12/10

O usuário autorizou explicitamente recuperar administração somente na UAT.
Bootstrap emergencial feito com serviços nativos CUser/CUserGroup, sem escrita
SQL direta; auditoria sob ator administrativo existente e evidência de
autorização neste registro. Criada identidade ness_uat_breakglass em grupo
local emergencial separado. Senha gerada e guardada exclusivamente em arquivo
root-only 0600 no destino. Login pela API HTTP normal, leitura administrativa
e logout aprovados. Não foi criado token permanente nem elevado o usuário Hub.
Isso desbloqueia correção SAML/API UAT; não é homologação SSO ou corte.
Remover conta/grupo emergencial após validar contas nominais e recuperação.

## SAML UAT reconciliado

Aplicado por userdirectory.update autenticado via API normal. Issuer e endpoint
obtidos do metadata HTTPS do provider UAT (ID 13); SP EntityID atualizado para
https://zabbix-uat.ness.com.br. Certificado de assinatura UAT instalado a partir
do metadata, preservando certificado e parâmetros anteriores em arquivos
root-only em restore-evidence. Preflight e repetição idempotente aprovados.
Redirecionamento público HTTP 302 agora segue /application/saml/zabbix-uat/.
Login nominal, MFA, logout federado e cenários negativos ainda não homologados.
Uma tentativa de probe público a partir da própria VPS recebeu 403; a estação
cliente recebeu o 302 esperado. Não tratar bloqueio desse probe como queda da UI.

## Inventário autenticado e correção de escopo

API administrativa host.get retornou 262 hosts. Conferência SQL por flags:
261 hosts habilitados + 1 desabilitado com flags=0; 62 protótipos habilitados
+ 1 desabilitado com flags=2. Portanto os 325 registros anteriormente chamados
de hosts incluíam 63 protótipos. O escopo continua todos os hosts reais; protótipos
são revisados como configuração LLD, não como 63 dispositivos adicionais.
O hash anterior prova igualdade de registros, mas não valida essa classificação.

Dashboards existentes preservados: 1 NOC — Visão Operacional (8 widgets),
2 Zabbix server health (8), 57 Zabbix server (1), 405 NOC — Operação e Clientes
(32). Não substituir pelo candidato genérico menor sem revisão. Próxima tarefa:
exportar dashboard 405, validar filtros/layout e produzir delta reversível.

## Entrega NOC UAT privada

Dashboard 406 criado pela API autenticada: cinco páginas e 32 widgets, privado,
com título explícito UAT/snapshot 11/10/2026/sem coleta. O original 405 foi
exportado em arquivo root-only no destino e comprovado inalterado após criação.
Filtros, tipos de widget e geometria copiados, sem substituir o NOC existente.
Preflight, quantidade de widgets e privacidade aprovados. Rollback: excluir
somente dashboard 406 via API; não restaurar banco nem substituir o original.
Renderização e aceite nominal continuam pendentes; não declarar dados atuais.

## Qualidade — baseline dos hosts reais

Leitura corrente na origem excluindo protótipos (flags 0/4): 261 hosts ativos,
1 desativado; 15 sem template diretamente vinculado. Nesta amostra existem
2.068 itens habilitados não suportados em 149 hosts ativos. Contagem varia em
produção; não comparar amostras distintas como redução causada por correção.

Tags ausentes nos 262 hosts reais: criticality=262, service=262, tenant=243,
site=243, technology=243, owner=243, role=243, environment=242, scope=242.
Tags de protótipos não serão tomadas como cadastro dos dispositivos reais.
Ausência de template não comprova incompatibilidade; exige verificar coleta
local e descoberta. O próximo pacote precisa classificar esses 15 hosts e
qualificar fontes dos atributos antes de qualquer alteração de tenant.

## Primeira onda de qualidade aplicada na UAT

Classificação dos 15 hosts sem template: 14 não possuem nenhum item (12 APs
Unifi Alupar, um VMware04 Alupar e esper); o host sintético 10978 possui um
item trapper e não exige template apenas para satisfazer contador.

Hosts 10740–10744 receberam somente collection_state=unconfigured na UAT,
preservando todas as tags anteriores. Tenant/owner/criticidade não inferidos;
nenhum template, item, histórico ou estado de habilitação alterado. Preflight
com ausência de itens/templates, aplicação, rollback, reaplicação e repetição
idempotente aprovados pela API normal. Pacote anterior/posterior protegido:
/var/lib/ness-os/restore-evidence/unconfigured-wave-1-20261012.json.

Reaplicar este delta via script versionado após qualquer refresh final que
substitua a configuração UAT; nunca presumir que sobrevive ao restore. A tag
expõe lacuna de cobertura, não corrige coleta ou reduz itens não suportados.

Ondas 2 e 3 concluídas pelo mesmo script: 10745–10749 e
10750/10751/10791/10962. Total de 14 hosts sem itens sinalizados; 10978
sintético excluído. Ambos os lotes passaram preflight, aplicação, rollback e
reaplicação. Seis testes do mecanismo/escopo aprovados; arquivos root-only
unconfigured-wave-2-20261012.json e unconfigured-wave-3-20261012.json
preservam antes/depois. Nenhum host foi habilitado/desabilitado, nenhum template
foi vinculado, e a origem não recebeu essas alterações.

## Variante SNMP isolada preparada e importada

Masters 85756/85977 confirmados como herança de net.if.walk 46234, no template
10604 FortiGate by SNMP. Export real gerou variante 10988:
FortiGate by SNMP - UAT walk 5s. Copiados 55 itens e nove regras LLD; somente
o timeout de net.if.walk passou a 5s. UUIDs dos novos objetos renovados e
referências de template reescritas, preservando grupos e export original.

TDD da transformação: três testes falharam antes da implementação e passaram;
suíte Python de infraestrutura: 40 testes e três subtestes aprovados. A execução
por diretório inicialmente não descobriu arquivos test-*.py; a seleção explícita
correta executou a suíte. Não foi repetida a suíte de backend ou backup.

Importcompare aprovou apenas adições; import via API normal com updateExisting
desligado. Export do template 10604 permaneceu idêntico antes/depois, variante
sem hosts vinculados e timeout 5s confirmado. Arquivos de export/candidato/
comparação/resultado root-only em restore-evidence, sem credenciais no Git.
Rollback do preparo: excluir apenas 10988 depois de comprovar ausência de
hosts vinculados. Próxima etapa: ensaio de vínculo em host UAT com preservação
de IDs/histórico e rollback. Não há coleta ativa ou redução comprovada de erros;
5s é hipótese de teste, não tuning produtivo aprovado.

Ensaio de vínculo em um host UAT (10768) concluído: preflight, troca de 10604
para 10988 sem templates_clear, timeout herdado 5s e retorno a 10604 aprovados.
IDs/chaves dos 717 itens, IDs dos 304 triggers e status do host preservados
antes/depois/rollback. Evidência root-only snmp-variant-link-test-20261012.json;
integração versionada em infra/tests/verify-zabbix-snmp-variant-live.py.
Variante continua sem vínculo produtivo e o host terminou no template original.
Esse ensaio não iniciou Zabbix nem verificou resposta SNMP; não prova redução
dos 992 erros dependentes ou ganho por timeout. Não repetir o ensaio aprovado
sem mudança relevante. Próxima etapa é definir observação de coleta autorizada
sem dupla coleta antes de promover tuning para hosts reais.

## NOC — smoke test de navegador isolado

Microsoft Edge headless em contexto novo: login local emergencial, abertura
do dashboard 406 e logout executados. Sem usar/mudar a aba do usuário, sem
salvar senha/cookies/trace. Frontend renderizou pt-BR, logo oficial no sidebar,
cinco abas e layout legível na primeira página, sem pageerror registrado ou
erro de conexão ao banco. Teste versionado em
infra/tests/verify-zabbix-noc-browser.cjs; captura fica fora do Git.

Limite: somente conta emergencial e viewport desktop 1600x1000; não prova SSO
nominal, MFA, RBAC de cliente, móvel ou renderização das cinco páginas. Dados
são do snapshot, como informa o título. O widget de disponibilidade exibiu
259 hosts elegíveis ao widget, não os 261 habilitados do cadastro. Há três
hosts sem interface: esper, INTRANET - Producao e o sintético UAT. O widget
também representa agente ativo, portanto ausência de interface por si só não
define exclusão. Não usar o total desse widget como cobertura completa do
cadastro. Este smoke test não aprova gate produtivo.
