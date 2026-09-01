# Zabbix UAT — break-glass temporário (2026-08-26)

Uma recuperação de acesso foi autorizada para a cópia UAT restaurada, pois a
senha de uma conta administrativa existente não estava disponível.

## Controle aplicado

- Conta temporária: `ness_uat_breakglass`.
- Papel: Super Admin; grupo `Zabbix administrators`.
- Escopo: exclusivamente a nova VPS UAT; nenhuma alteração na VPS atual de
  produção.
- Senha aleatória criada localmente com permissão `0600`; não foi incluída no
  repositório nem persistida na VPS.
- Arquivo temporário de senha no servidor foi removido após a criação.

## Revogação obrigatória

Após o primeiro login nominal/OIDC homologado, desabilitar ou remover essa
conta pela interface/API suportada e apagar o segredo local. Não utilizar a
conta para operação regular ou para o corte de produção.
