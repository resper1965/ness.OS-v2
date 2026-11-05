# Runbook — identidade Fase A (autorização local no Hub)

[ADR 0015](../adr/0015-entra-id-identity-local-authorization.md). O provedor autentica; o Hub autoriza. Sem JIT.

## O que muda na promoção

Quem entrava por OIDC/JIT recebe **403** até ter o vínculo cadastrado. O login local por senha não muda.

## Cadastrar uma identidade

1. Entre no Hub por **login local por senha** com um `platform_admin` já existente (o OIDC não serve antes do primeiro vínculo).
2. O usuário local (papel e tenant) já tem de existir e estar ativo, pelo caminho de admin existente.
3. Obtenha o `sub` (ou `oid`, no Entra) da pessoa:
   - peça que tente entrar por OIDC: o 403 deixa no log do backend a linha `OIDC sem vínculo: iss='…' sub='…'` (com `iss` e `sub` entre aspas, escapados); ou
   - painel do Authentik (usuário → atributos/UID do provedor).
4. Cadastre:

```
POST /api/auth/identities
{"user_id": <id do User>, "issuer": "<iss do token>", "subject": "<sub ou oid>"}
```

Respostas: 201 ok · 403 não é `platform_admin` · 404 usuário inexistente · 409 usuário inativo ou vínculo já existe · 422 issuer/subject vazio ou longo demais.

**O `issuer` precisa ser idêntico ao `iss` do token**, inclusive barra final e maiúsculas/minúsculas. O Hub só remove espaços nas pontas; não normaliza mais nada. Copie o valor do log.

## Rollback

Cortar o acesso de uma pessoa: desative o usuário (`is_active = false`; derruba também o login local). Para só remover o vínculo OIDC:

```sql
DELETE FROM n_infraops_identities WHERE id = <id_do_vinculo>;
-- ou: WHERE issuer = '<iss>' AND subject = '<sub>';
```

Não há endpoint para listar nem remover vínculos (sugestão para a Fase B). Consulta: `SELECT id, user_id, issuer, subject, created_by_user_id, created_at FROM n_infraops_identities;`.

## Auditoria

Cada vínculo guarda `created_by_user_id` e `created_at`, e o cadastro grava uma linha de log `Identidade vinculada`.
