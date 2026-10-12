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
