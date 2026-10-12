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
| Grupo `platform_admin` | 0 membros | não atende à regra aprovada de Ismael Araujo, Rogério Salerno e Ricardo Esper |
| Dispositivos TOTP | 0 | MFA TOTP não está comprovado para nenhuma identidade |
| Dispositivos WebAuthn | 0 | MFA WebAuthn não está comprovado para nenhuma identidade |
| Dispositivos de recuperação estática | 0 | códigos de recuperação não estão configurados no Authentik |

Os contadores de MFA não excluem outros fatores que precisem de inspeção
específica, mas são suficientes para manter G2 **aberto**: a política exige
MFA e recuperação de dois custodians comprovadas.

## Saúde de runtime observada

`ninf-authentik-server` e `ninf-authentik-worker` estavam `healthy`, na versão
`2026.5.6`. Isto prova disponibilidade do processo, não prova os fluxos de
login, logout, revogação, callback nem segregação por tenant.

## Próxima mudança controlada

1. Confirmar formalmente as três identidades nominais que receberão
   `platform_admin`; não assumir usuários pelo nome.
2. Incluir somente essas três identidades no grupo e validar a imposição no
   backend do Hub.
3. Habilitar TOTP ou WebAuthn individualmente para os custodians, gerar códigos
   de recuperação sob dupla custódia e testar revogação.
4. Executar matriz de acesso positivo/negativo em Hub, Zabbix, GLPI, Psono,
   Grafana e Node-RED.

Nenhuma dessas alterações é feita por este inventário. A documentação atual do
Authentik confirma que acesso a aplicações depende das bindings de política,
grupo ou usuário; um grupo vazio não é uma evidência de RBAC efetivo.
