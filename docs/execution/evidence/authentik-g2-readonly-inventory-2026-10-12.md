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
