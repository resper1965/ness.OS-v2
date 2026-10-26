# Zabbix UAT — baseline de acesso e proposta de papéis

Data: 2026-08-26 (BRT)
Escopo: cópia restaurada na VPS `zbx-prd-01`; sem alteração de permissões.

## Estado verificado

- SAML está habilitado e JIT está desabilitado.
- O grupo `Disabled` é o grupo configurado para desprovisionamento futuro.
- O servidor Zabbix continua `inactive` e `masked`.
- A cópia restaurada contém diversos usuários no papel **Super admin**, herdados
  do ambiente anterior. Esta condição é aceitável apenas durante a UAT
  controlada; não atende ao modelo de administração restrita do ness.OS.

## Redução aplicada em 2026-08-26

- Os Super Admins humanos herdados foram reduzidos ao papel `Admin role`.
- Permanecem como Super Admin no Zabbix UAT: `iaraujo`, `rsalerno` e `resper`,
  além de `ness_uat_breakglass` (contingência temporária) e `zbxgrafana`
  (integração técnica temporariamente preservada).
- Um dump restrito (`0600`, `root:root`) do estado anterior foi salvo em
  `/var/backups/zabbix/access/` na VPS UAT.
- `zabbix-server` foi revalidado como `inactive` e `masked` após a mudança.
- O grupo Authentik `ness-os-platform-admin` contém somente os três
  identificadores nominais: `resper` (Ricardo Esper), `iaraujo` (Ismael
  Araújo) e `rsalerno` (Rogério Salerno). `akadmin` foi removido do grupo;
  a restrição SSO de plataforma está fechada.
- A conta canônica do Ricardo é `resper`, compatível com o usuário já existente
  no Zabbix. A conta duplicada `Ricardo Esper` (id 7) foi retirada do grupo e
  desativada em 2026-08-26, sem exclusão, preservando evidência e rollback.
  JIT permanece desativado.

## Modelo alvo

| Camada | Regra |
| --- | --- |
| Administração de plataforma | somente Ismael Araújo, Rogério Salerno e Ricardo Esper, autenticados pelo Authentik e com MFA obrigatório |
| Operação NOC/SOC | papéis mínimos por função; sem Super Admin por padrão |
| Integrações | contas técnicas dedicadas, escopo mínimo e tokens com expiração/rotação |
| Contingência | uma única conta break-glass, registrada, guardada fora do repositório e revogada após homologação |
| Clientes e suporte | acesso segregado por grupo/tenant e somente aos ativos autorizados |

## Sequência para aplicar, após revisão nominal

1. Confirmar os três identificadores de usuário no Authentik e no Zabbix.
2. Criar grupos de função no Zabbix: `Platform Admin`, `NOC Operator`,
   `SOC Analyst`, `Read Only` e `Integration`.
3. Associar grupos Authentik aos grupos Zabbix; manter JIT desligado durante o
   primeiro ciclo de homologação.
4. Reduzir os Super Admins herdados para o modelo alvo, um por vez, validando
   em sessão separada para evitar bloqueio administrativo.
5. Revogar `ness_uat_breakglass` e o provedor SAML temporário somente após
   evidência de login nominal dos administradores aprovados.

## UX/UI da identidade — trilha posterior

O Authentik é a porta de entrada do ness.OS e deverá receber uma camada de
experiência e identidade visual ness. após a estabilização de acesso. O escopo
inclui login, recuperação, MFA, catálogo de aplicações, mensagens e uso
mobile, sem alterar os requisitos de autenticação, os vínculos de política ou
as permissões durante o trabalho de design.

## Decisão pendente

É necessária uma revisão nominal antes de remover privilégios herdados. Não
tratar a existência de uma conta na cópia restaurada como autorização para
mantê-la na operação do ness.OS.
