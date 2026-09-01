# Auditoria de acesso e scripts — Zabbix

> Data: 21/08/2026
> Método: consulta somente leitura ao banco e à configuração, sem exibir senhas, IDs de sessão, valores de token ou comandos.

## Resultado executivo

A contenção impede execução dos scripts no servidor porque `EnableGlobalScripts=0` está ativo. A conta padrão `Admin` não possui sessões nem tokens, recebeu senha aleatória irrecuperável e foi associada formalmente ao grupo `Disabled` em 21/08/2026.

Existem 14 contas com `Super admin role`, número incompatível com menor privilégio. Entre elas estão contas pessoais, `akadmin` e a integração `zbxgrafana`. Nenhuma redução em massa será feita sem confirmar função e owner de cada identidade.

## Scripts

- 61 scripts no total: três padrões e 58 customizados associados ao incidente.
- Os 58 customizados têm `execute_on=1`, portanto destinam a execução ao Zabbix Server.
- Os 58 comandos customizados foram neutralizados para `true` depois de nova preservação forense; a validação posterior confirmou o mesmo SHA-256 para todos.
- A evidência original já preserva os 58 registros e passou novamente no `SHA256SUMS`.
- Enquanto `EnableGlobalScripts=0` permanecer ativo, a execução no servidor fica bloqueada; manter comandos hostis no banco ainda cria risco caso a opção seja revertida.

A contenção final foi executada por [`../../infra/scripts/zabbix-incident-final-containment.sh`](../../infra/scripts/zabbix-incident-final-containment.sh). O preflight e os checksums passaram; nova evidência root-only foi preservada antes da neutralização e da associação de `Admin` ao grupo `Disabled`.

## Contas de maior privilégio observadas

- `Admin` — padrão comprometida; deve permanecer formalmente desabilitada.
- `resper` — owner atual; o token `intranet` foi rastreado e desabilitado em 21/08/2026.
- `rsalerno`, `iaraujo` — responsáveis nominais aprovados, mas o uso cotidiano não deve exigir Super Admin.
- `agsilva` — permanece em `User role`, conforme período de observação aprovado.
- `akadmin` — identidade administrativa ligada ao Authentik; definir se é bootstrap, break-glass ou conta cotidiana.
- `zbxgrafana` — integração; deve migrar para papel API somente leitura e host groups necessários.
- `asilva`, `fxavier`, `galves`, `gferreira`, `jmachado`, `sbuoni`, `tgoncalves`, `tsouza` — confirmar owner, função atual e necessidade de privilégio máximo.

## Decisões aprovadas em 21/08/2026

- Limite de duas identidades `Super admin` exclusivamente break-glass, com MFA, segredo no Passbolt e teste periódico.
- Ricardo (`resper`), Rogério (`rsalerno`) e Ismael (`iaraujo`) usarão papéis administrativos limitados no trabalho diário.
- Agnaldo (`agsilva`) permanece em `User role` durante o período de observação.
- O token `resper/intranet` foi correlacionado a quatro chamadas à API feitas por Python 3.13, originadas de `179.191.71.196` em 19/08/2026. Como também estava exposto em código e não havia consumidor permanente aprovado, sua revogação foi autorizada e concluída.

## Ações necessárias

1. Confirmar quais das contas pessoais acima ainda pertencem à equipe e precisam de acesso administrativo.
2. Nomear as duas identidades break-glass e criar/testar o papel diário de Ricardo, Rogério e Ismael sem acesso irrestrito a scripts, autenticação e configuração global.
3. Criar papel dedicado de leitura para Grafana e substituir credenciais após teste.
4. Definir o papel futuro de `akadmin` depois de concluir a homologação Authentik.

## Ferramenta reproduzível

O inventário foi gerado por [`../../infra/scripts/zabbix-security-state-report.sh`](../../infra/scripts/zabbix-security-state-report.sh). O script executa apenas `SELECT`, não mostra segredos e pode ser reutilizado antes/depois de cada mudança de acesso.
