# Authentik — inventário G2 somente leitura

Data: 2026-10-12 (BRT)  
Escopo: Authentik na VPS AIOps; nenhuma alteração em usuários, grupos,
políticas, tokens, MFA ou credenciais.

## Fotografia observada

| Item | Valor | Interpretação |
| --- | ---: | --- |
| Aplicações | 9 | `glpi`, `grafana`, `hub`, `n-csirt`, `n8n`, `nessops`, `wazuh`, `zabbix`, `zabbix-uat` |
| Usuários | 42 | inventário estrutural, sem exportar identidades |
| Usuários ativos | 41 | há uma identidade inativa; não foi alterada |
| Grupos | 13 | inventário estrutural |
| Grupo `platform_admin` | 3 membros ativos | Ismael (`iaraujo`), Rogerio (`rsalerno`) e Ricardo (`resper`); `akadmin` ficou excluído |
| Dispositivos TOTP | 0 | MFA TOTP não está comprovado para nenhuma identidade |
| Dispositivos WebAuthn | 0 | MFA WebAuthn não está comprovado para nenhuma identidade |
| Dispositivos de recuperação estática | 0 | códigos de recuperação não estão configurados no Authentik |

Após a fotografia inicial, a associação foi aplicada de forma transacional e
revalidada com exatamente os três membros acima. O runtime Hub recebeu a
verificação do contrato: a claim `platform_admin` é mapeada para o papel
`platform_admin` no backend. O provedor OIDC do Hub contém o mapeamento
`NESS Hub groups and tenant`.

Os contadores de MFA não excluem outros fatores que precisem de inspeção
específica, mas são suficientes para manter G2 **aberto**: a política exige
MFA e recuperação de dois custodians comprovadas.

## Saúde de runtime observada

`ninf-authentik-server` e `ninf-authentik-worker` estavam `healthy`, na versão
`2026.5.6`. Isto prova disponibilidade do processo, não prova os fluxos de
login, logout, revogação, callback nem segregação por tenant.

## Aplicações inventariadas para a matriz G2

| Aplicação | Provedor vinculado | Bindings de política | Próxima prova |
| --- | --- | ---: | --- |
| GLPI | `glpi-proxy` | 6 | login, logout e acesso negado |
| Grafana | `grafana-oidc` | 4 | OIDC, expiração e tenant negado |
| Hub | `hub-oidc` | 6 | HTTP, SSE, logout e RBAC |
| n-csirt | `n-csirt-oidc` | 1 | OIDC e autorização |
| n8n | `n8n-proxy` | 3 | proxy e revogação |
| nessops | `nessops` | 0 | revisar acesso antes de incluir no aceite |
| Wazuh | `wazuh-oidc` | 2 | manter fora do MVP; testar depois |
| Zabbix | `zabbix-saml` | 4 | SAML, logout e break-glass |
| Zabbix UAT | `zabbix-uat-saml` | 1 | SAML isolado, sem coleta/notificação |

Essa fotografia comprova o vínculo estrutural, não autorização efetiva. Em
especial, `nessops` não tem binding diretamente na aplicação e deve ter sua
rota de acesso revisada antes de entrar no aceite G2.

## MFA — configuração efetiva observada

O fluxo `default-authentication-flow` contém a etapa
`default-authentication-mfa-validation`, após identificação e senha. Ela aceita
`static`, `totp`, `webauthn`, `duo` e `sms`, porém está com
`not_configured_action=skip`. Portanto, o ambiente suporta a validação MFA sem
interromper quem ainda não cadastrou um fator; isto explica os logins atuais,
mas não equivale a MFA imposto.

Também existem, sem necessidade de criar componentes novos, os fluxos nativos:

- `default-authenticator-totp-setup`;
- `default-authenticator-webauthn-setup`;
- `default-authenticator-static-setup`.

O corte seguro é: cada um dos três custodians cadastra TOTP ou WebAuthn, obtém
e guarda os códigos estáticos sob dupla custódia, prova login com MFA e somente
depois a regra deixa de aceitar `skip` para o grupo `platform_admin`. Não foi
alterada nenhuma etapa de autenticação nesta coleta.

## Verificação do backend — 12/10

A suíte local de identidade e controle de acesso passou com **81 testes**:
`test_authentik_rbac.py`, `test_contabo_read_only_rbac.py`,
`test_core_auth.py`, `test_incidents_auth.py` e `test_tenant_secops_auth.py`.
Ela verifica regras de papel, isolamento de tenant, sessão e proteção da API;
não substitui a homologação de login com dispositivos MFA nem a recuperação
independente do cofre pelos custodians.

Em uma rodada complementar, **26 testes** de cookie de sessão, logout,
política OIDC e PKCE passaram. As verificações estáticas de readiness Authentik
e plumbing de segredos também passaram. O plano antigo cita
`test_oidc_session_lifecycle.py`, mas o arquivo existente é
`test_oidc_session_policy.py`; este foi o arquivo executado.

No runtime `ninf-api`, as rotas `/api/contabo/compute`, `/api/incidents` e
`/api/auth/me` retornaram **401** sem token, mesmo com headers
`X-Authentik-Username` e `X-Authentik-Groups` forjados. A checagem foi feita na
API interna do contêiner, não cobre o proxy público nem sessões autenticadas.

Na rodada seguinte, as mesmas três rotas foram verificadas por HTTPS em
`https://hub.ness.com.br`, com validação TLS e os mesmos headers forjados:
todas retornaram **401**. Isso estende a prova negativa ao proxy público;
login nominal, MFA e sessões autenticadas continuam sem aceite nesta rodada.

## Próxima mudança controlada

1. Cadastrar TOTP ou WebAuthn individualmente para os três custodians, gerar
   códigos de recuperação sob dupla custódia e testar revogação.
2. Impor MFA especificamente a `platform_admin` somente depois dos três testes
   positivos; preservar um break-glass documentado e testado.
3. Executar matriz de acesso positivo/negativo em Hub, Zabbix, GLPI, Psono,
   Grafana e Node-RED.

O inventário inicial não alterou MFA, políticas ou tokens. A associação nominal
posterior foi autorizada e aplicada. A documentação atual do Authentik confirma
que acesso a aplicações depende das bindings de política, grupo ou usuário;
MFA e testes de sessão/revogação continuam necessários para aprovação de G2.
