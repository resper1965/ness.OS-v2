# Zabbix — estágio de 12/10/2026

## Plano master — entrada única do programa

Escopo atualizado: produção completa, com liberações contínuas P1–P4 e canário
como teste inicial, não ponto final. Esta atualização é documental; nenhuma
promoção, janela ou acesso foi ativado.

[ness.OS — plano master](../superpowers/plans/2026-10-12-ness-os-plano-master.md)
reúne todas as frentes em nove fases, com sequência, dependências, aceites e
referências detalhadas. Compilação documental apenas; implementação pelo modelo
autor não autorizada e automação segue pausada. Retomar por esse documento.

## Planos atuais persistidos — execução por outro modelo

- [Authentik: identidade e experiência ness.](../superpowers/plans/2026-10-12-authentik-fluid-delivery.md).
- [Customização transversal de todos os produtos](../superpowers/plans/2026-10-12-ness-branding-cross-product-plan.md), incorporada aos planos GLPI/Zabbix e roteiro geral.

Elaboração documental apenas, usando Ponytail full. Nenhuma aplicação,
autenticação ou marca foi alterada nesta rodada; automação continua pausada.

## Plano de retomada Zabbix — Ponytail full

[Plano enxuto de liberação](../superpowers/plans/2026-10-12-zabbix-fluid-delivery.md):
seis etapas, reuso das entregas aprovadas, coleta/acesso antes do corte e
acabamento após liberação. Planejamento concluído; implementação não iniciada
pelo modelo autor, conforme instrução humana. Automação permanece pausada.
O plano substitui a sequência antiga, não os critérios de aceite. Ler também
o ledger para não repetir ondas já aprovadas.

## Retomada atual — plano completo GLPI

Plano canônico para a próxima implementação:
[GLPI no ness.OS — implementação completa](../superpowers/plans/2026-10-12-glpi-ness-os-complete-delivery.md).
Estado: implementação retomada pelo modelo executor; T03/G2 bloqueados e
conta técnica 106 inativa. O usuário determinou não executar com o modelo
autor. Na retomada, ler o handoff do plano e as evidências de
[execução GLPI](glpi-next-delivery-2026-10-12.md).
São 14 tarefas com dependências, testes, rollback e aceite; não repetir
trabalhos anteriores aprovados. Os registros abaixo preservam o histórico
Zabbix e não substituem a prioridade atual GLPI.

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

Inspeção ampliada: as cinco páginas do dashboard 406 foram navegadas e
renderizaram seus títulos/widgets sem erro de página. Logout executado.
Em 390x844, documentWidth=390 não indicou overflow, porém a captura mostrou
conteúdo cortado pela sidebar aberta e widgets fora da área visível. Portanto
o teste móvel NÃO está aprovado; ausência de overflow não prova usabilidade.
Capturas desktop/móvel fora do Git. Próximo ajuste: testar navegação com menu
recolhido e, se necessário, variante de dashboard móvel; sem editar core.
Geometria de mapas, frescor, RBAC de cliente e login SSO nominal continuam
sem aceite, mesmo que o widget renderize.

## Cavan — appliance e links separados na visualização

Leitura de 12/10 por SQL somente leitura: as últimas amostras de modelo/serial
dos hosts 10873 (AmericaNET), 10874 (Vivo) e 10977 (firewall físico) identificam
FortiGate-40F e o mesmo serial, comparado por SHA-256 sem expor o valor.
Essas amostras têm clock 1791745575–1791749438; não são prova de frescor atual.
Os três hosts têm o template FortiGate by SNMP e 319 itens reais cada um.
Macros herdadas IFNAME.MATCHES=.* e NOT_MATCHES=(^[Ll]o[0-9.]*$), sem override
de host, fazem os dois hosts de links descobrir também interfaces internas/VPN.

O cadastro chama AmericaNET de wan1, porém o item descoberto identifica `wan`
(índice 1, alias AmericaNET); Vivo é `lan3` (índice 4, alias Vivo). Não inferir
interfaces a partir do nome do host. Não apagar/mesclar hosts ou históricos.
Não restringir LLD sem revisar duração de recursos perdidos e export dos itens:
um filtro novo pode expirar itens existentes, mesmo sem templates_clear.

Painel privado 407 criado na UAT a partir de
config/zabbix/cavan-links-uat-dashboard.json: seis widgets, entrada/saída/estado
por link, mostrando horário da amostra, título explícito snapshot/sem coleta.
IDs 97682/97742/97782 pertencem a 10873/wan; 98076/98136/98176 a 10874/lan3.
Preflight conferiu IDs/host/chave, isolamento, geometria sem sobreposição;
readback confirmou seis widgets privados e dashboards 405/406 inalterados.
Evidência root-only: cavan-links-dashboard-20261012.json em restore-evidence.
Nenhum filtro LLD, template, coleta ou configuração da origem foi alterado.

Reaplicação após refresh final: autenticar pela API normal; confirmar identidade
dos seis itens acima, servidor inativo/mascarado e ausência de 10051; procurar
dashboard pelo nome exato. Se inexistente, dashboard.create com o JSON; se
existente, comparar os campos, não criar duplicata ou sobrescrever divergência.
O userid 37 é específico da recuperação UAT: escolher owner nominal aprovado
antes da promoção, não carregar cegamente este owner em produção. Rollback:
dashboard.delete somente do ID criado, após conferir nome, privacidade e seis
referências, sem tocar 405/406. A camada visual não reduz coleta duplicada.

Smoke test Edge headless isolado: seis títulos renderizaram, sem pageerror,
login local/logout executados, sem usar a aba do usuário ou salvar credenciais.
Esse teste usou o fluxo existente de navegador com parâmetros do novo painel;
não prova SSO nominal, frescor nem usabilidade móvel (overflow=false não basta).

Próxima correção de coleta: desenhar perfil de appliance em 10977 e perfil de
link em 10873/10874, preservando os históricos existentes e validando ciclos
LLD/expiração em ambiente autorizado. O erro de armazenamento não deve ser
escondido; verificar capacidade/disco aplicável antes de alterar cálculo.

## Perfil de link — proteção de histórico e correção de identificação

Leitura da origem em 12/10 15:41 BRT: net.if.discovery 46237 (template 10604),
97484 (10873), 97861 (10874) e 115599 (10977) têm lifetime_type=0/lifetime=7d
e enabled_lifetime_type=2. A API oficial 7.0 define isso como excluir recursos
perdidos após sete dias e desabilitá-los imediatamente. Portanto um filtro
IFNAME restrito aplicado diretamente pode causar exclusão posterior de itens.
Não aplicar macros de restrição sobre o template/hosts atuais sem preservação.

Etapa preparada, NÃO implementada: exportar o template real e a configuração
dos dois links; criar variante privada de transição com net.if.discovery
lifetime_type=1 (não excluir) antes de restringir descoberta; usar filtros
exatos ^wan$ em 10873 e ^lan3$ em 10874; conservar appliance completo em 10977.
Não usar wan1, não alterar índices por suposição, não editar template global.
Ensaiar troca sem templates_clear com invariância de IDs/chaves/triggers;
observar ciclos LLD autorizados e estados dos itens excluídos do filtro.
Export de IDs não é backup de histórico: nenhum delete será permitido.
Desativação/remoção de métricas duplicadas de appliance nos hosts de links
é etapa separada, exige inventário das dependências e aceite de cobertura.
Rollback retorna template/macros anteriores e valida reativação dos itens
preservados; só a troca de template, sem observar LLD, não prova esse retorno.

Correção aplicada por API normal somente UAT: name visível de 10873 passou
de "Link AmericaNet wan1" para "Link AmericaNet wan". Campo técnico host
permaneceu "Cavan Matriz Fortigate 40F Link AmericaNet wan1", para não quebrar
expressões/integrações. Configuração completa, tags, templates e IDs/chaves/
status dos itens ficaram iguais; aplicação, rollback e reaplicação passaram.
Delta versionado em config/zabbix/cavan-wan-display-name-delta.json;
antes/depois root-only cavan-wan-name-20261012.json. Reaplicar após refresh
somente se hostid/host/name anterior e interface coincidirem; caso divergente,
abortar. Rollback altera exclusivamente name para o valor anterior.

Issues 51/71 atualizadas em 15:42 BRT para substituir instruções ultrapassadas
de recuperação/configuração já executadas. E-mail de procedimento restante
enviado a Ismael com Ricardo em cópia, Gmail SENT 1a1316cace7b0677.
Permanecem abertos SSO nominal/MFA/logout/negativos e identidade técnica
permanente mínima; sessões emergenciais não equivalem a esses aceites.

## Fechamento da meta de quatro horas — preparação às 15:45 BRT

Verificação final após o delta: origem zabbix-srv01 active/enabled, listener
10051 presente; destino zbx-prd-01 inactive/masked, listener 10051 ausente.
Não houve corte DNS, ativação do destino, dupla coleta ou modificação de
templates/LLD na origem. GitHub recebeu o delta de nome em 9050565; árvore
limpa após push. Não foi repetido dump, restore ou ensaio de backup.

Entrega produtiva completa NÃO atingida na meta. Continuam pendentes:
homologação nominal SSO/MFA/negativos; gates de promoção; perfil de links
com preservação de recursos LLD; observação das correções SNMP; freeze/snapshot
final, GO, corte e D+1/D+3/D+7. Painéis/tags/nome são UAT, não evidência de
redução produtiva de erros. A continuação automática desta meta será pausada
ao atingir 15:47:35 BRT; isso não cancela a janela de 24h nem aprova o corte.
Retomada usa este cartão e deltas versionados, preserva os serviços correntes
e não recomeça pelo backup. A próxima implementação independente é a variante
LLD de transição, não a alteração direta de filtros com lifetime=7d.

## Novo plano completo e execução — 12/10 17:25–17:40 BRT

Ordem do usuário: plano inequívoco e execução até o fim para todos os ativos.
Plano versionado: docs/superpowers/plans/2026-10-12-zabbix-complete-delivery.md.
Esta ordem retoma execução; a janela até13/10 11:47:35BRT permanece, sem
dispensar gates/GO/SSO ou autorizar dupla coleta. Não repetir a migração validada.

Registro sanitizado completo em config/zabbix/asset-register-20261012.json:
262hosts reais (261ativos/1desativado),63protótipos,53ondas de até5. Estado de
avaliação:149needs_remediation,14unconfigured,98assessment_required e1disabled.
Nenhum accepted, intencionalmente: ausência de erro não prova coleta/adequação.
Protótipos ainda exigem revisão parent/rule; sua presença não é aceite LLD.
Módulo/testes versionados; RED10falhas antes da implementação e GREEN10testes.
Revisão identificou denominador ausente: corrigido por teste RED→GREEN.
A amostra atual tem1741unsupported/35849itens habilitados de hosts reais ativos,
taxa4,856%; não comparar como ganho com baselines antigas ou descontar exceções.

Template10989 FortiGate by SNMP - UAT link transition importado por API normal:
somente net.if.discovery passa a DELETE_NEVER; timeout original preservado.
Importcompare somente adições, template10604 exportado idêntico antes/depois,
variante sem hosts após ensaio. Protegidos fortigate-link-source/candidate/
importcompare-20261012.json em restore-evidence.

Ensaio UAT de10873/^wan$ e10874/^lan3$: retenção1 confirmada antes da macro;
319itens120triggers por host comIDs/chaves/status preservados; rollback devolveu
10604 e removeu somente macro de ensaio. Evidências link-transition-test-ID-
20261012.json e teste explícito versionado. Não observou coleta nem ciclos LLD;
não se declara redução de erro ou reativação em retorno de descoberta.

Revisão independente apontou retorno incompleto em falha de API: helper de
compensação agora verifica estado após resposta perdida, tenta limitadamente,
mantém DELETE_NEVER se não conseguir confirmar remoção do filtro e grava FAIL
com estado observado. Testes adversariais RED→GREEN; suíte infra57testes e3
subtestes PASS. Ensaios vivos já aprovados não foram repetidos por essa mudança.
Fonte protegida permanece ativa, destino mascarado; identidade/corte pendentes.

## Continuação integral — 12/10 18:24 BRT

Diagnóstico SNMP somente leitura na origem, sem outra coletora ou configuração:
10768 respondeu os mesmos 13 OIDs/936 valores em 21,905s com bulk10 e8,273s
com bulk25, timeout3s. Valores/comunidade não foram publicados; ferramentas
Debian extraídas em diretório protegido, sem instalação global. Evidência
root-only snmp-bulk-comparison-20261012.json. Não equivale a redução de erros
no Zabbix. Ensaio API UAT dos10768/10769 alterou apenas max_repetitions25,
preservou os demais campos de interface e voltou a10; delta reversível em
config/zabbix/snmp-bulk-25-uat-delta.json. Aplicação produtiva pendente.

Credencial bootstrap da origem id4 está desativada/expirada, verificado por
metadados sem segredo. Não foi reativada ou substituída por SQL. Issue72 e
email SENT1a131f121718e061 orientam identidade API mínima temporária para
Ismael/Ricardo; conta Hub não elevada. Usuário indicou "akadimin", mas isso
ainda não distingue entrada no cofre de conta Authentik; não existe sessão
de manutenção da origem comprovada por essa indicação.

Módulo nativo ness_mobile31 habilitado somente UAT, sem editar core:
infra/zabbix/modules/ness_mobile/. CSS somente leitura móvel ≤600px;
desktop/edit mantêm grid nativo. Teste Edge390x844 passou geometria, texto
sem corte, alcance do último widget, desktop, modo edição e logout. Leitura
API posterior confirmou layouts405/406/407 intactos. Capturas fora do Git.
Escopo testado: primeira página406 (11widgets) e407 (6widgets), não todos
os perfis/páginas. Rollback module.update id31 status0; não remover core.

Registro renovado por mudança de schema para incluir frescor das pulsações
agent.ping/icmpping/system.uptime, nunca valores. Observação21:24:03UTC:
262reais/63protótipos/53ondas;185FRESH,1STALE,76UNKNOWN;24sem itens de pulso.
Intervalo flexível/macro, dependente sem intervalo resolvido, clock ausente/
futuro e unsupported permanecem UNKNOWN. Frescor não é disponibilidade ou
aceite. Erros atuais1849/35847habilitados=5,158%; nenhuma melhora atribuída
às mudanças UAT. Source SQL é transação read-only com clocks indexados.

Testes do frescor RED25→GREEN25; integração registro RED2→GREEN38.
Suíte infra84testes+3subtestes PASS. Teste amplo do helper encontrou72falhas
backend por dependência pywebpush ausente (339pass/1skip), sem relação com
estes scripts; não instalar dependências fora do escopo Zabbix para mascarar
essa limitação. Não houve novo backup, restore ou corte DNS.

Continuação reativada a cada10min até13/10 11:47:35BRT, respeitando janela,
gates e silêncio sem mudança. Próximos trabalhos: revisão de63protótipos,
causas/intervalos por host, evidências por onda e acesso normal de origem;
SSO nominal/MFA/negativos, coleta corrigida e corte continuam pendentes.

### Protótipos e acesso — continuação após 18:24 BRT

Registro por ID agora contém parent_hostid/ruleid/status/flags sanitizados de
todos os63protótipos:63referências válidas a regras flags1, nenhuma órfã;
51pais são templates status3 e12pais hosts ativos status0; regras habilitadas.
Isso valida vínculos de configuração, não execução LLD, credenciais ou
descoberta recente. Chaves/macros da regra não entram no registro público.
Testes de parent/regra e ausência de referência RED2→GREEN15 no registro.

Leitura normal de metadados confirmou username akadmin na origem, roleid3;
não existe username akadimin. Nenhuma senha lida/redefinida, nenhum token
reativado. A indicação do nome não produz uma sessão normal autenticada:
acesso produtivo continua dependente do percurso protegido da issue72.
Entrega anterior publicada em7c4fd58; continuação do registro segue abaixo.

### Trilha abreviada para liberar — ordem posterior do usuário

Prioridade ajustada: acesso/SSO/gates e causas críticas de coleta precedem
corte; mapas/polimento não essenciais depois; D+1/D+3/D+7 pós-liberação.
Não dispensados metas de qualidade, GO, ausência de dupla coleta ou rollback.
Leitura de nomes/permissões no percurso /etc/ness-os da origem continua
mostrando somente zabbix-cutover-bootstrap.env0600 para Zabbix; nenhuma nova
credencial de manutenção disponível nesse percurso. Não reativar token
desativado nem redefinir conta akadmin em produção. Bloqueioissue72 permanece.
Não houve backup/restore ou novo ensaio UAT repetido nesta retomada.

### URL de manutenção da origem confirmada — 12/10 18:35 BRT

Apache da origem declara ServerName zabbix.ness.com.br; DNS atual resolve
144.91.72.202 e HTTPS /index.php respondeu200 com validaçãoTLS normal.
Percurso correto para criar acesso mínimo: https://zabbix.ness.com.br/,
não zabbix-uat.ness.com.br. Resposta pública não prova login/API nem muda
o bloqueioissue72. Não houve criação de token ou escrita de configuração.

### Acesso de manutenção entregue pelo usuário

Usuário gerou token na origem e entregou arquivo local fora do repositório.
Transferência SSH concluída para /etc/ness-os/zabbix-maintenance.token,
root:root0600; cópia temporária remota removida. Nenhum valor publicado.
HTTPS/API normal host.get e hostinterface.get PASS:10768/10769 ativos,
interfacesSNMP116/117. Bloqueio de autenticação de leitura superado para o
piloto; permissão de escrita, identidade/expiração e escopo negativo ainda
devem ser verificados. Não aplicar em massa nem considerarG2 aprovado por
esse teste. Próximo passo: conferir privilégios e precondições do delta bulk25,
aplicar somente primeiro host e observar três ciclos antes do segundo.

### Primeira correção na origem — 12/10 18:45 BRT

Token entregue corresponde aoid6 da conta nominalresper, tipoSuperadmin,
sem expiração inicial. Identidade confirmada em memória por hash, sem publicar
segredo/hash. ViaAPI normal, expires_at limitado a13/10 11:47:35BRT e lido de
volta; conta/role não alterados. Acesso fora do piloto existe: privilégio
mínimo NÃO aceito, pendência deG2; uso operacional restringido aos IDs do
delta autorizado, não à conta Hub. Token5 svc_ninfraops_api não foi modificado.

Origem10768/interface116 passou precondiçõesv2/bulk1/reps10; export antes
root-only source-bulk25-10768-20261012.json em /var/lib/ness-os/diagnostics/.
API alterou somente details.max_repetitions25, readback confirmou os demais
campos intactos,717itens304triggers preservados. Antes497unsupported, master
85756unsupported,504dependentes, intervalo1m. Host10769/interface117 segue10.

Observação real iniciada na unidade systemd
ness-zabbix-bulk25-observe-10768-20261012.service: consulta de clocks/estado
sem valores brutos, exige três clocks pós-alteração com master suportado e
sem piora dos unsupported. Limite10min; falha retorna10 viaAPI normal e
confirma readback. Não relançar unidade por timeout de consulta; acompanhar
o mesmo job/evidência. Não aplicar segundo host enquanto primeiro não passar.
Status neste registro: APPLIED_OBSERVATION_PENDING, não redução comprovada.

### Correção do observador, não dos templates compartilhados

Primeira unidade terminou OBSERVATION_ERROR:AssertionError e retornou bulk10,
readbackPASS. Mestre85756 tem history0: não haveria três clocks persistidos.
Além disso LLD adicionou itens durante recuperação: igualdade exata de IDs
era critério incorreto; agora exige todos os anteriores presentes e aceita
adições, nunca remoção. Leitura intermediária master0/340unsupported mostrou
melhora temporária, mas não aprovação; após retorno10 voltou master1.

Helper zabbix-snmp-observation.py/teste:3casos RED→GREEN para LLD aditivo,
perda de item, clocks únicos novos e recusa de clocks ausentes/antigos/falha.
Nova unidade justificada por bug demonstrado, não timeout de observação:
ness-zabbix-bulk25-observe-10768-v2-20261012.service. Evidência root-only
source-bulk25-10768-v2-20261012.json. Reaplicação somente10768/interface116;
retenção temporária history1h somente item mestre85756, viaAPI normal e
confirmada, permite medir clocks reais. Finally restaura history0; falha
também devolve bulk10 e confirma. Não imprime valores brutos. Não iniciar
terceira unidade/reaplicar enquanto esta estiver rodando. Host10769 intacto.
Critério de aplicação continua pendente até resultado terminal e cleanupPASS.

### Primeira melhora produtiva comprovada e segunda observação

10768 unidadev2 terminou THREE_CYCLES_PASS_FIRST_HOST_ONLY:
clocks1791841884/1791841943/1791842004, master0, unsupported349/1/1,
referência497antes da primeira alteração. Original history0 restauradoPASS,
cleanupsemfalha, bulk25 mantido. Redução observada496/497=99,80% neste host,
não taxa global ou aceite dos demais ativos. LLD adicionou recursos, nenhum
ID original foi removido. Helper e suíteinfra89testes+3subtestes PASS;
não repetidos restore/backups. Contexto/testes publicados emf3d67bf.

Após resultado terminal/cleanup, segundo10769/interface117 iniciou somente
delta bulk25 e retenção temporária1h no mestre85977. Unidade independente
ness-zabbix-bulk25-observe-10769-20261012.service; evidência root-only
source-bulk25-10769-20261012.json. Mesmos guards/3ciclos/10min/rollback10 e
finallyhistory0. Antes de ampliar novamente, acompanhar este job, não
recriá-lo; nunca considerar processo running como PASS. Origem continua
única coletora; DNS e destino inalterados; SSO/gates seguem pendentes.

### Onda SNMP produtiva concluída — dois hosts, não o capítulo inteiro

10769 concluiu THREE_CYCLES_PASS_SECOND_HOST: clocks1791842105/2165/2225,
master0, unsupported340/7/1; history0 restauradoPASS, cleanupsemfalha,
bulk25 mantido. Readback final dos dois confirmou details preservados exceto
max_repetitions, interfaces disponíveis1 e todos os717IDsitens/304triggerIDs
originais presentes. LLD acrescentou18itens/8triggers por host:735/312agora,
nada apagado; não são dispositivos adicionais. Redução994→2=99,80% somente
nos dois hosts, após ciclos reais; não atribuir outras variações da frota.

Resíduos explícitos:10768/item85776 e10769/item85997, vfs.fs.pfree,
DIVISION_BY_ZERO. Não substituir por0/100% nem desabilitar para maquiar meta;
confirmar capacidade/aplicabilidade e tratar conforme modelo/contrato.
Nova amostra sanitizada da frota após mudança:749unsupported/35905habilitados
de hosts reais ativos=2,086%; ainda acima de0,5%. Registro completo atualizado
porque houve mudança produtiva real, sem repetir dump/restore/backup.

Unidades de observação terminaram; não relançar ou refazer onda aprovada.
Próxima prioridade: causas restantes por famílias (agentes/VMware/calculados)
e SSO/gates, não maps/polimento. G2 leastprivilege/nominalMFA não aprovado;
token6temporário continua limitado à janela. Origem única coletora e destino
mascarado; corteDNS não realizado. Janela e GO continuam pré-requisitos.

### Próxima onda: compatibilidade de agentes e VMware — 12/10 após19hBRT

Leitura de causas restantes:117perf_counter_en em9hosts;67vfs.fs.pfree,
40system.sw.os,30system.swap.free; seis hosts VMware com erros de parâmetro.
10787/10788/10789/10790/10792/10793 não têm HV.UUID próprio; não há macro
global configurada. Suas descobertas estãounsupported e sem históricoJSON.
UUIDs de outros hosts existentes não têm correspondência inequívoca de IP
com esses seis: não copiar pelo nome nem inventar identificador. Coleta/UUID
porvSphere autoritativo ainda necessário; nenhuma macroVMware alterada.

Oito agentes do lote10696/97/98/99/10700/10703/10704/10705 são monitorados
pelo proxy1. Consulta TCP direta da origem a10696 expirou; isso não é prova
de falha do agente, pois rota correta éproxy1. Proxy comunicou há7s na
consulta. Última versão registrada10696 é3.2.6, amostra~8h antiga: não
afirmar versão atual pela fotografia. Diagnóstico ocorre na coleta normal.

Probe temporário120217 em10696, mesmo contador original com chave
perf_counter em vez deperf_counter_en, recebeu três clocks2798/2857/2917
(prefixo179184), valor numérico finito e state0. Unidade
ness-zabbix-agent-compatibility-10696-20261012 terminou
COMPATIBILITY_ONE_COUNTER_THREE_CYCLES_PASS; probe desativado viaAPI,
histórico preservado, itens/templates originais intocados. Isso comprova
um contador compatível, não corrige os117unsupported automaticamente.

Iniciados os outros12contadores do mesmo host como diagnósticos tag
scope=maintenance_probe, sem triggers, intervalo1m/history1h/trends0.
Unidade ness-zabbix-agent-compatibility-full-10696-20261012; JSONroot-only
/var/lib/ness-os/diagnostics/agent-compatibility-full-10696-20261012.json.
Exige três clocks pós-criação numéricos/state0 por item, limite10min;
finally desativa somente os12probes novos e preserva dados. Não relançar.
Não trocar template/chaves existentes antes de provar todos os contadores
e ensaiar preservação de IDs/histórico emUAT. Pendentes continuam originais,
sem ocultarerro/zerovalores para meta. Jobrodando não equivale aPASS.

### Resultado do lote de compatibilidade — 12/10 após19:20BRT

Unidade full10696 terminou FULL_COMPATIBILITY_NOT_PROVEN:
os12probes não receberam histórico float/uint durante10min; cleanup
ALL_PROBES_DISABLED_HISTORY_PRESERVED confirmado viaAPI e SQLstatus1.
Nenhum item/template original foi alterado, nem117erros marcados resolvidos.
Probe único anterior continua com comprovação limitada de um contador, não
extrapolar para os12. Interface do agente apareceavailable1, mas isso não
comprova que novas definições foram recebidas/executadas pelo proxy.

Proxy1 versão70028, compatibility1, state2ONLINE, última comunicação~3s.
Native CheckNow foi solicitado uma vez paraos12: tasks50–61 status3done;
isso é ackde tarefa, não sucesso de coleta. Refresh de configuração do
proxy solicitado uma vez porAPI task.create tipo2/request.proxyids:[1],
task62; sem reiniciar serviço. Ainda não comprovou propagação das12definições.
Primeira chamada CheckNow com request.itemids foi rejeitada sem efeitos;
payload correto request.itemid em array foi confirmado na fontePHP7.0.27.

Não recriar probes ou repetir consulta TCP da origem por timeout; investigar
configuração/cache/execução no proxy usando diagnóstico nativo e percurso
autorizado. Não culpar o agente ou trocar template antes de evidência.
UUIDsVMware continuam sem fonte autoritativa; não escrever macros por nome.
Os dois hostsSNMP já aceitos não foram revertidos/refeitos. Corte não feito.

### Diagnóstico nativo do proxy e dependência local — 12/10 19:42BRT

Task65 diagnóstico porAPI respondeu status-1: estatística solicitada não
suportada; não interpretar como incompatibilidade de versão. Pedido corrigido
task67/historycache padrão respondeustatus0 com dados estruturados:1item/
1valor no buffer, memória data~64MiB praticamente livre naquele instante.
Isso confirma caminho de diagnóstico e ausência de congestionamento nessa
amostra, não conteúdo da configuração ou execução das12definições. Não
repetir requestsestatísticos já aprovados sem nova necessidade.

Leitura limitada de últimas2500linhas do log da origem não encontrou as
categorias conhecidas de erro de configuração deproxy/cache/banco. Ausência
dessas mensagens não comprova funcionamento. Não exportados logs/valores.
Nenhum percursoSSH deproxy encontrado nos arquivos operacionais pesquisados;
scripts existentes só apontam servidores centrais, não o produtorlocal.

Dependência novaissue73: diagnóstico de leitura no equipamento doproxy1,
owner técnicoIsmael e acessoRicardo, comandos de versão/serviço/frequências
sem segredos; revisar logs localmente19:05–19:25BRT, não enviar dadosbrutos
porGitHub/chat/email. Não pedir outrotoken ou reativarprobes. Nenhuma
mudança de configuraçãopersistente/serviço/DNS/coleta foi feita nesta etapa.
Instruções novas enviadas a Ismael com Ricardo emcópia, GmailSENT
1a13248a44509e7e. Não repetir cobrança; continuar causas independentes
enquanto o acesso/relatório local daissue73 não chega.

### Authentik — prioridade renovada após GLPI

Usuário solicitou análise global, ajuste e customização ness. antes de seguir
GLPI. Guia e fotografia atual em
docs/operations/authentik-ness-implementation-guide-2026-10-12.md.
Brand sso.ness.com.br atualizada transacionalmente: título ness. | acesso,
CSS versionado config/authentik/ness-access.css, fluxo inicial Acesse sua conta.
Snapshot root0600 no servidor144.91.115.242:
/opt/n-infraops/rollback/authentik-global-20261012/before.json.
Logo/favicon/providers/MFA/grupos/callbacks preservados, sem restart/core edit.

Tela pública1440/390px, input, título, ausência de overflow, botões48px,
BlueDot/texto preto/sem gradiente e reduced-motion PASS em navegador isolado.
API Authentik sem sessão e headers forjados403; GLPI com headers forjados302
paraSSO. Não são provas de sessão autenticada/cross-tenant/backend direto.
Inventário atual reafirma zeroTOTP/WebAuthn/static e validaçãoMFA skip.
Não impor deny global enquanto administradores sem fator/recuperação.
Provider GLPI12proxy efetivo,8OIDC nãoefetivo;legados e callbacks documentados.
G2,SSO nominal/MFA,admin UX,logo/fonte vetorial e tradução integral pendentes.
GLPI issue74 de identidade mínima permanece; nenhum ativo criado.
Zabbix origem única coletora/destino mascarado continuam preservados.

### Checkpoint GLPI — 13/10/2026, 11:10 BRT

- O volume `/var/glpi` foi fixado em `app_glpi-state`, com original preservado;
  o smoke nominal e anexos da issue #76 ainda precisam de aceite.
- A borda pública da API GLPI nega variantes normais/codificadas; Hub e GLPI
  ainda compartilham rede. A conta técnica 106 continua desativada, T03/G2
  bloqueados e nenhum dos ativos 10983/10984/10987 foi criado.
- Uma duplicidade inativa foi reconciliada por API normal; restam 33 pares
  ativo/ativo com grants divergentes. A decisão nominal está na issue #77;
  instruções foram enviadas a Ismael/Ricardo, Gmail SENT
  `1a1358e9cee46cc8`. Não houve dedupe em massa.
- A paleta nativa `ness.` foi instalada no volume persistente, reconhecida pelo
  GLPI, mas não selecionada. Aceite visual em 390/1440/200% e jornadas na
  issue #78, e-mail SENT `1a1358d9c349355a`. T10 não aprovado.
- O sincronizador CMDB ganhou guard fail-closed para não reatribuir um ativo
  existente a outro cliente/entidade/ID GLPI. Testes 474 PASS/1 SKIP,
  sem deploy nem escrita de ativos. Os cinco jobs do commit `9e49063`
  (backend, frontend, lint/tipos, secret scan, SBOM) passaram; G0 global
  permanece pendente de release/rollback/aprovação.
- Zabbix não sofreu mutação nesta etapa: origem segue coletora única e destino
  mascarado. A janela anterior termina às 11:47:35 BRT; não usar autorização
  ou token expirado para mudar essa frente depois do prazo.

### Checkpoint GLPI T03 — 13/10/2026, 11:30 BRT

- Gateway privado candidato versionado, não implantado. Compose opt-in validado
  na CLI produtiva com valores fictícios; nenhuma rede, contêiner, token ou
  conta GLPI produtiva foi alterada. Conta 106 segue inativa e os três ativos
  Alupar continuam não criados.
- Preflight local exige imagem por digest, subnet RFC1918/IP utilizável e três
  arquivos de segredo regulares, não vazios e sem permissão de grupo/outros;
  32 testes de infraestrutura passaram. A subnet candidata não colidiu com
  rotas/bridges vistas no preflight somente leitura, mas precisa de nova
  checagem antes de criar rede.
- `publish-hub-images.yml` da branch retornou HTTP 404 ao tentar dispatch:
  não está registrado na branch padrão. Issue #67 atualizada. Os checks da
  branch não equivalem a imagem publicada. Sem digest verificado e matriz
  negativa Hub/rota pública/entidade descendente/rollback, T03 e G2 seguem
  bloqueados. Ver ADR 0020 e ledger do master.
- Os cinco checks de `1328116` fecharam PASS; build do SBOM é efêmero e não
  publica digest. Teste da factory com tokens sintéticos passou para bearer
  errado, entidade 1 permitida, entidade 5 negada e logout; backend 475 PASS,
  1 SKIP. GLPI produtivo permaneceu intocado.

### Incremento independente GLPI T04 — 13/10/2026, 11:46 BRT

- O reconciliador histórico já completou 115+29 marcadores por leitura; não
  foi reexecutado. Revisão do cliente encontrou falso fim possível quando o
  GLPI omitia `Content-Range` numa página curta. O código agora falha fechado,
  em vez de declarar ticket ausente e arriscar duplicata.
- Teste RED→GREEN e fixture ajustada ao contrato documentado do GLPI 11;
  backend 476 PASS/1 SKIP. Alteração apenas na branch, sem replay, escrita ou
  deploy. A documentação oficial de paginação é `apirest.md` do GLPI 11.
- Após 11:47:35 BRT a autorização de mutação Zabbix expira; nenhuma mudança
  nessa frente ocorreu neste checkpoint. Origem permanece coletora única.

### Janela Zabbix renovada — 13/10/2026, 11:53 BRT

- O usuário ampliou a janela anterior por 48 horas. Novo limite adotado:
  **15/10/2026 11:47:35 BRT**, contado do vencimento anterior. A automação
  do plano master foi atualizada com esse prazo, mantendo GLPI como ferramenta
  principal e Zabbix sem mutação neste registro.
- A credencial temporária de manutenção venceu em 13/10 às 11:47:35 BRT;
  a ampliação não a renova. Sem credencial válida e gates/GO/freeze/rollback,
  não ativar destino, fazer dupla coleta nem cortar DNS.
- O Backend CI de `da7e865` falhou no fixture do fluxo integrado: a resposta
  simulada de Ticket não trazia `Content-Range`, agora obrigatório. Fixture
  corrigida com total real; backend local 476 PASS/1 SKIP, Ruff/Black PASS.
  Os cinco workflows de `fa56a9f` terminaram PASS no SHA exato: Backend CI,
  Frontend CI, Lint & Type Check, Secret scan e Build image SBOMs. Isso valida
  a branch, não publica imagem por digest nem promove o runtime produtivo.
  Nenhum runtime produtivo foi alterado.

### GLPI T04 — consistência da paginação, 13/10/2026

- Teste RED mostrou que `Content-Range: 0-0/0` junto de uma página não vazia
  era aceito como fim da busca; a ausência do marcador poderia ser declarada
  sem prova. A busca agora confere início, fim, tamanho da página e total
  informado, falhando fechado quando divergirem. Sete testes focados PASS;
  Black/Ruff PASS. A suíte local teve 406 PASS, 1 SKIP e 72 falhas por
  `pywebpush` ausente neste Python; a dependência consta em `requirements.txt`.
  Aguardar CI completo no commit desta alteração. Sem replay/deploy ou escrita
  no GLPI; a conta técnica 106 continua desativada.
