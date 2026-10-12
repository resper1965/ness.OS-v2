# Zabbix — estágio de 12/10/2026

Atualização: restore terminou 12:38:46 BRT / 15:38:46 UTC.
Owner operacional: plataforma ness.; ticket GLPI 75426.

| Entrega | Estado comprovado |
| --- | --- |
| Origem | Continua sendo produção e rollback; DNS não alterado |
| Refresh definitivo | PASS: snapshot f0b19cf8 importado no destino, frontend sincronizado |
| Paridade de inventário | PASS: 325 hosts, tags e vínculos de templates iguais na origem/destino |
| Banco/API/frontend | Schema 7.0; API 7.0.27; HTTP 200; durabilidade=1 |
| Isolamento | Server inativo/mascarado; sem listener 10051; canais externos desligados |
| Marca | Hook nativo e assets servidos; referência de login confirmada; renderização ainda não inspecionada |
| Qualidade de coleta | Todos os hosts no escopo; causas SNMP prioritárias identificadas; não corrigidas ainda |
| SSO/API de escrita UAT | Bloqueados: SAML restaurado aponta à origem; acesso mínimo na #71 |
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
