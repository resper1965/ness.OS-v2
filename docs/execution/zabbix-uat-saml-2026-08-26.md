# Zabbix UAT — SAML com Authentik

Data: 2026-08-26 (BRT)
Escopo: `zabbix-uat.ness.com.br` na VPS `zbx-prd-01`.

## Resultado

- O aplicativo Authentik **Zabbix UAT** está associado ao provedor definitivo
  `zabbix-uat-saml` e restrito ao grupo de administração de plataforma.
- O frontend Zabbix UAT foi configurado contra os metadados publicados pelo
  Authentik. O certificado público do IdP foi instalado em
  `/usr/share/zabbix/conf/certs/idp.crt`, com permissão `0640` e proprietário
  `root:www-data`.
- A entrada por **logon único (SAML)** foi testada de ponta a ponta: Zabbix →
  Authentik → Zabbix, chegando ao dashboard autenticado.
- SAML está habilitado, mas JIT e SCIM permanecem desabilitados. Assim, nesta
  fase o usuário precisa existir previamente no Zabbix e o login local segue
  disponível como contingência.
- `zabbix-server` continua `inactive` e `masked`; esta atividade não iniciou
  coleta, proxies, agentes, ações nem notificações.

## Parâmetros efetivos

| Campo | Valor |
| --- | --- |
| IdP entity ID | `https://sso.ness.com.br/application/saml/zabbix-uat/metadata/` |
| SSO service URL | `https://sso.ness.com.br/application/saml/zabbix-uat/` |
| SLO | não configurado nesta fase |
| Atributo de usuário | `http://schemas.goauthentik.io/2021/02/saml/username` |
| SP entity ID | `https://zabbix-uat.ness.com.br` |
| Assinatura de asserção | habilitada |
| JIT / SCIM | desabilitados |

## Rollback e pendências controladas

- Um dump restrito (`0600`, `root:root`) do estado anterior foi preservado em
  `/var/backups/zabbix/saml/` na VPS UAT.
- Preservar a conta `ness_uat_breakglass` exclusivamente até a homologação
  nominal e a confirmação do corte de acesso. A conta não deve ser usada na
  operação regular.
- Preservar o provedor Authentik `zabbix-uat-saml-temporary` somente como
  rollback até a validação final. Depois, removê-lo com aprovação explícita e
  registrar a revogação.
- Antes de JIT, definir mapeamento de grupos Authentik para papéis/grupos do
  Zabbix e um grupo de desprovisionamento. Não habilitar provisionamento por
  conveniência.
