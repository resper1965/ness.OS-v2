# Reconciliação do Issuer SAML do Zabbix — 02/09/2026

## Sintoma e causa

Depois do rollback do DNS para a origem `144.91.72.202`, o retorno SAML era
rejeitado com `Invalid issuer in the Assertion/Response`.

Os valores ativos divergiam:

- Zabbix: `https://sso.ness.com.br/application/saml/zabbix/metadata/`;
- metadata e Assertion do Authentik: `https://sso.ness.com.br`.

O problema era a comparação exata do IdP Entity ID, não a senha nem a conta do
usuário.

## Mudança reversível

A API suportada `userdirectory.update` alterou somente `idp_entityid` do
diretório SAML `1` para `https://sso.ness.com.br`. SSO, SLO, SP Entity ID,
provisionamento, SCIM, usuários e papéis não foram modificados.

Rollback: restaurar o valor anterior no mesmo diretório pela API:
`https://sso.ness.com.br/application/saml/zabbix/metadata/`.

Evidências root-only foram preservadas em
`/var/lib/ness-os/saml-evidence/issuer-reconcile-20260902T151455-0300`.

## Verificação

- API e banco do Zabbix retornam `idp_entityid=https://sso.ness.com.br`;
- o metadata público do Authentik retorna o mesmo Entity ID;
- `index_sso.php` responde 302 para o endpoint SAML do Authentik com
  `SAMLRequest`;
- nenhuma reinicialização foi necessária.

O login autenticado de ponta a ponta permanece como validação manual do
usuário, pois depende da sessão e do MFA pessoais.

## Achado operacional separado

O serviço `zabbix-server` da origem estava `inactive/masked`, e a porta 10051
era ocupada por um bridge para o destino inacessível `169.58.234.9`. O motor de
coleta foi posteriormente restaurado, com a contenção separada das notificações
inválidas, conforme `zabbix-source-reactivation-2026-09-02.md`.
